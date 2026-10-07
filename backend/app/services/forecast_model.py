from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from datetime import date
import math
from typing import Any

try:
    import joblib
except ImportError:  # pragma: no cover
    joblib = None

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = Path(os.environ.get("STOCKWISE_MODEL_DIR", ROOT / "ml" / "artifacts"))
ARTIFACT_PATH = MODEL_DIR / "indian_supermarket_xgb.joblib"
FEATURES = (
    "sku_code",
    "category_code",
    "price",
    "day_of_week",
    "doy_sin",
    "doy_cos",
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_28",
    "rolling_7",
    "rolling_28",
)


@lru_cache(maxsize=1)
def load_model_bundle() -> dict | None:
    if joblib is None or not ARTIFACT_PATH.exists():
        return None
    return joblib.load(ARTIFACT_PATH)


def feature_row(
    sku_code: int,
    category_code: int,
    price: float,
    target_date: date,
    history: list[float],
) -> Any | None:
    if np is None or len(history) < 28:
        return None
    angle = 2 * math.pi * (target_date.timetuple().tm_yday - 1) / 365.25
    return np.asarray(
        [[
            sku_code,
            category_code,
            price,
            target_date.weekday(),
            math.sin(angle),
            math.cos(angle),
            history[-1],
            history[-7],
            history[-14],
            history[-28],
            sum(history[-7:]) / 7,
            sum(history[-28:]) / 28,
        ]],
        dtype=np.float32,
    )


def predict_sku_day(
    bundle: dict,
    sku: str,
    category: str,
    price: float,
    target_date: date,
    history: list[float],
) -> float | None:
    sku_code = bundle["sku_codes"].get(sku)
    category_code = bundle["category_codes"].get(category)
    if sku_code is None or category_code is None:
        return None
    row = feature_row(sku_code, category_code, price, target_date, history)
    if row is None:
        return None
    prediction = float(bundle["model"].predict(row)[0])
    return max(0.0, prediction)
