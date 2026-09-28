"""Train and validate a recursive, SKU-aware demand model from imported daily sales."""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.forecast_model import ARTIFACT_PATH, FEATURES, feature_row, load_model_bundle  # noqa: E402


def load_database_data(database_url: str, business_id: int, sku_prefix: str):
    os.environ["DATABASE_URL"] = database_url
    from app.db import SessionLocal
    from app.models import Category, Product, Sale

    db = SessionLocal()
    try:
        sales_rows = db.query(Sale.date, Product.sku, Sale.quantity_sold).join(
            Product, Sale.product_id == Product.id
        ).filter(
            Sale.business_id == business_id,
            Product.business_id == business_id,
            Product.sku.like(f"{sku_prefix}%"),
        ).order_by(Sale.date, Product.sku).all()
        catalog_rows = db.query(Product.sku, Category.name, Product.price).join(
            Category, Product.category_id == Category.id
        ).filter(
            Product.business_id == business_id,
            Product.sku.like(f"{sku_prefix}%"),
        ).all()
    finally:
        db.close()

    if not sales_rows or not catalog_rows:
        raise RuntimeError(f"No sales/catalog rows found for business {business_id} and SKU prefix {sku_prefix!r}")
    sales = pd.DataFrame(sales_rows, columns=["date", "SKU", "quantity_sold"])
    sales["date"] = pd.to_datetime(sales["date"])
    catalog = pd.DataFrame(catalog_rows, columns=["SKU", "category", "price"])
    if sales.duplicated(["date", "SKU"]).any():
        raise ValueError("Database sales contain duplicate SKU/date rows")
    coverage = sales.groupby("SKU")["date"].nunique()
    if coverage.nunique() != 1 or coverage.iloc[0] < 56:
        raise ValueError("Each SKU needs a consistent daily history of at least 56 days")
    if set(sales["SKU"]) != set(catalog["SKU"]):
        raise ValueError("Sales and product catalog contain different SKU sets")
    return sales, catalog


def make_training_frame(sales: pd.DataFrame, catalog: pd.DataFrame):
    sku_codes = {sku: code for code, sku in enumerate(sorted(catalog["SKU"].unique()))}
    categories = sorted(catalog["category"].astype(str).unique())
    category_codes = {name: code for code, name in enumerate(categories)}
    catalog = catalog.copy()
    catalog["sku_code"] = catalog["SKU"].map(sku_codes).astype(np.int32)
    catalog["category_code"] = catalog["category"].map(category_codes).astype(np.int16)

    frame = sales[["date", "SKU", "quantity_sold"]].merge(
        catalog[["SKU", "sku_code", "category_code", "price"]], on="SKU", validate="many_to_one"
    )
    frame = frame.sort_values(["SKU", "date"], kind="stable").reset_index(drop=True)
    grouped = frame.groupby("SKU", sort=False)["quantity_sold"]
    frame["day_of_week"] = frame["date"].dt.dayofweek
    annual_angle = 2 * np.pi * (frame["date"].dt.dayofyear - 1) / 365.25
    frame["doy_sin"] = np.sin(annual_angle)
    frame["doy_cos"] = np.cos(annual_angle)
    for lag in (1, 7, 14, 28):
        frame[f"lag_{lag}"] = grouped.shift(lag)
    for window in (7, 28):
        frame[f"rolling_{window}"] = grouped.transform(
            lambda values: values.shift(1).rolling(window, min_periods=window).mean()
        )
    frame = frame.dropna(subset=list(FEATURES)).reset_index(drop=True)
    return frame, catalog, sku_codes, category_codes


def make_model(seed: int = 20260926):
    return XGBRegressor(
        n_estimators=350,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        min_child_weight=10,
        reg_lambda=5,
        objective="count:poisson",
        eval_metric="mae",
        tree_method="hist",
        max_bin=128,
        n_jobs=max(1, min(8, (os.cpu_count() or 2) - 1)),
        random_state=seed,
    )


def score(actual: list[float], predicted: list[float]) -> dict:
    y = np.asarray(actual, dtype=float)
    p = np.maximum(0, np.asarray(predicted, dtype=float))
    nonzero = y > 0
    return {
        "mae": float(mean_absolute_error(y, p)),
        "rmse": float(mean_squared_error(y, p) ** 0.5),
        "mape": float(np.mean(np.abs((y[nonzero] - p[nonzero]) / y[nonzero])) * 100) if nonzero.any() else 0.0,
        "wape": float(np.abs(y - p).sum() / max(float(y.sum()), 1.0) * 100),
        "r2": float(r2_score(y, p)),
    }


def rolling_seasonal(history: list[float]) -> float:
    return max(0.0, float(np.mean([history[-lag] for lag in (7, 14, 21, 28)])))


def validate_recursive(model, sales, catalog, sku_codes, category_codes, frame, block_days: int):
    panel = sales.pivot(index="date", columns="SKU", values="quantity_sold").sort_index()
    if panel.isna().any().any():
        raise ValueError("Validation requires a complete daily panel for every SKU")
    catalog = catalog.set_index("SKU")
    skus = list(panel.columns)
    first_test_index = len(panel.index) - 28
    if first_test_index < 56:
        raise ValueError("At least 56 training dates before the 28-day holdout are required")
    cutoff = panel.index[first_test_index - 1]
    training = frame[frame["date"] <= cutoff]
    if training.empty:
        raise ValueError("No training rows remain before the validation period")
    model.fit(training[list(FEATURES)].to_numpy(dtype=np.float32), training["quantity_sold"].to_numpy())

    actual_all, model_all, baseline_all = [], [], []
    for block_start in range(first_test_index, len(panel.index), block_days):
        block_end = min(block_start + block_days, len(panel.index))
        origin = block_start - 1
        model_histories = {
            sku: panel[sku].iloc[origin - 27:origin + 1].astype(float).tolist()
            for sku in skus
        }
        baseline_histories = {sku: values.copy() for sku, values in model_histories.items()}
        for row_index in range(block_start, block_end):
            target_date = panel.index[row_index].date()
            rows = [
                feature_row(
                    sku_codes[sku],
                    category_codes[str(catalog.loc[sku, "category"])],
                    float(catalog.loc[sku, "price"]),
                    target_date,
                    model_histories[sku],
                )
                for sku in skus
            ]
            predictions = np.maximum(0.0, model.predict(np.vstack(rows)))
            baseline = np.asarray([rolling_seasonal(baseline_histories[sku]) for sku in skus])
            actual = panel.iloc[row_index].reindex(skus).to_numpy(dtype=float)
            actual_all.extend(actual.tolist())
            model_all.extend(predictions.tolist())
            baseline_all.extend(baseline.tolist())
            for index, sku in enumerate(skus):
                model_histories[sku].append(float(predictions[index]))
                model_histories[sku] = model_histories[sku][-28:]
                baseline_histories[sku].append(float(baseline[index]))
                baseline_histories[sku] = baseline_histories[sku][-28:]
    return cutoff.date(), score(actual_all, model_all), score(actual_all, baseline_all)


def persist_model_runs(database_url: str, business_id: int, results: dict, train_start: date, train_end: date):
    os.environ["DATABASE_URL"] = database_url
    from app.db import SessionLocal
    from app.models import ModelRun

    db = SessionLocal()
    try:
        db.query(ModelRun).filter(
            ModelRun.business_id == business_id,
            ModelRun.version == "indian-12m-v1",
            ModelRun.model_name.in_(list(results)),
        ).delete(synchronize_session=False)
        for name, metrics in results.items():
            db.add(ModelRun(
                business_id=business_id,
                model_name=name,
                version="indian-12m-v1",
                train_start=train_start,
                train_end=train_end,
                mae=metrics["scores"]["mae"],
                rmse=metrics["scores"]["rmse"],
                mape=metrics["scores"]["mape"],
                r2=metrics["scores"]["r2"],
                horizon_days=metrics["horizon_days"],
            ))
        db.commit()
    finally:
        db.close()


def train(database_url: str, business_id: int = 1, sku_prefix: str = "SKU-") -> list[dict]:
    sales, catalog = load_database_data(database_url, business_id, sku_prefix)
    frame, catalog_codes, sku_codes, category_codes = make_training_frame(sales, catalog)
    validation_model = make_model()
    cutoff, model_scores_7, baseline_scores_7 = validate_recursive(
        validation_model, sales, catalog_codes, sku_codes, category_codes, frame, 7
    )
    _, model_scores_28, baseline_scores_28 = validate_recursive(
        make_model(), sales, catalog_codes, sku_codes, category_codes, frame, 28
    )

    final_model = make_model()
    final_model.fit(frame[list(FEATURES)].to_numpy(dtype=np.float32), frame["quantity_sold"].to_numpy())
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": final_model,
        "model_name": "xgboost_recursive_28d",
        "version": "indian-12m-v1",
        "features": list(FEATURES),
        "sku_codes": sku_codes,
        "category_codes": category_codes,
        "train_start": str(frame["date"].min().date()),
        "train_end": str(sales["date"].max().date()),
        "horizon_days": 28,
    }
    temporary = ARTIFACT_PATH.with_suffix(ARTIFACT_PATH.suffix + ".tmp")
    joblib.dump(bundle, temporary, compress=3)
    temporary.replace(ARTIFACT_PATH)
    load_model_bundle.cache_clear()

    metrics = {
        "rows": int(len(sales)),
        "sku_count": int(sales["SKU"].nunique()),
        "date_start": str(sales["date"].min().date()),
        "date_end": str(sales["date"].max().date()),
        "validation_cutoff": str(cutoff),
        "validation_horizons_days": [7, 28],
        "validation_window_days": 28,
        "seasonal_naive_7d": baseline_scores_7,
        "xgboost_recursive_7d": model_scores_7,
        "seasonal_naive_28d": baseline_scores_28,
        "xgboost_recursive_28d": model_scores_28,
        "artifact": str(ARTIFACT_PATH),
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    ARTIFACT_PATH.with_name("training_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    validation = {
        "seasonal_naive_7d": {"horizon_days": 7, "scores": baseline_scores_7},
        "xgboost_recursive_7d": {"horizon_days": 7, "scores": model_scores_7},
        "seasonal_naive_28d": {"horizon_days": 28, "scores": baseline_scores_28},
        "xgboost_recursive_28d": {"horizon_days": 28, "scores": model_scores_28},
    }
    persist_model_runs(database_url, business_id, validation, frame["date"].min().date(), cutoff)
    return [{"model": name, **result["scores"], "horizon_days": result["horizon_days"]} for name, result in validation.items()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--business-id", type=int, default=1)
    parser.add_argument("--sku-prefix", default="SKU-")
    args = parser.parse_args()
    print(json.dumps(train(args.database_url, args.business_id, args.sku_prefix), indent=2))


if __name__ == "__main__":
    main()
