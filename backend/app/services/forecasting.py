from datetime import date, timedelta
import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Forecast, Product, Sale
from .forecast_model import load_model_bundle, predict_sku_day


def average_daily_sales(db: Session, product_id: int, lookback: int = 28) -> float:
    start = date.today() - timedelta(days=lookback)
    total = db.query(func.coalesce(func.sum(Sale.quantity_sold), 0)).filter(
        Sale.product_id == product_id,
        Sale.date >= start,
    ).scalar()
    return float(total or 0) / lookback


def _trained_product_forecast(db: Session, product: Product, horizon_days: int):
    bundle = load_model_bundle()
    if not bundle or product.sku not in bundle["sku_codes"]:
        return None

    today = date.today()
    rows = db.query(Sale.date, func.sum(Sale.quantity_sold)).filter(
        Sale.product_id == product.id,
        Sale.date >= today - timedelta(days=60),
        Sale.date <= today,
    ).group_by(Sale.date).order_by(Sale.date).all()
    if not rows:
        return None
    observed = {day: float(quantity) for day, quantity in rows}
    latest = max(observed)
    if (today - latest).days > 7:
        return None

    history_start = latest - timedelta(days=27)
    history_dates = [history_start + timedelta(days=offset) for offset in range(28)]
    if any(day not in observed for day in history_dates):
        return None
    history = [observed[day] for day in history_dates]
    category = product.category.name if product.category else ""

    # Bring the observed history to today before forecasting future dates.
    while latest < today:
        target = latest + timedelta(days=1)
        prediction = predict_sku_day(bundle, product.sku, category, float(product.price), target, history)
        if prediction is None:
            return None
        history.append(prediction)
        history = history[-28:]
        latest = target

    model_horizon = min(horizon_days, int(bundle.get("horizon_days", 7)))
    generated = []
    for offset in range(1, model_horizon + 1):
        target = today + timedelta(days=offset)
        prediction = predict_sku_day(bundle, product.sku, category, float(product.price), target, history)
        if prediction is None:
            return None
        generated.append((target, prediction))
        history.append(prediction)
        history = history[-28:]
    return generated, bundle["model_name"], bundle["version"]


def forecast_product(db: Session, product: Product, horizon_days: int = 7, persist: bool = True) -> list[Forecast]:
    trained = _trained_product_forecast(db, product, horizon_days)
    if trained:
        model_predictions, trained_name, trained_version = trained
        predictions = [
            (target, quantity, trained_name, trained_version)
            for target, quantity in model_predictions
        ]
        fallback_start = len(model_predictions) + 1
    else:
        predictions = []
        fallback_start = 1

    if not trained or len(predictions) < horizon_days:
        velocity = average_daily_sales(db, product.id)
        for offset in range(fallback_start, horizon_days + 1):
            target = date.today() + timedelta(days=offset)
            weekend_factor = 1.12 if target.weekday() in (5, 6) else 0.96
            predictions.append((target, max(0.0, round(velocity * weekend_factor, 2)), "seasonal_baseline", "v1"))

    dates = [target for target, _, _, _ in predictions]
    existing_rows = db.query(Forecast).filter(
        Forecast.product_id == product.id,
        Forecast.forecast_date.in_(dates),
    ).all()
    desired_keys = {(target, model_name) for target, _, model_name, _ in predictions}
    existing = {
        (row.forecast_date, row.model_name): row
        for row in existing_rows
    }
    for key, row in existing.items():
        if key not in desired_keys:
            db.delete(row)
    generated = []
    for target, predicted, model_name, version in predictions:
        row = existing.get((target, model_name))
        if row is None:
            row = Forecast(
                business_id=product.business_id,
                product_id=product.id,
                forecast_date=target,
                predicted_quantity=round(predicted, 2),
                model_name=model_name,
                model_version=version,
                horizon_days=horizon_days,
            )
            if persist:
                db.add(row)
        else:
            row.predicted_quantity = round(predicted, 2)
            row.horizon_days = horizon_days
        generated.append(row)
    if persist:
        db.commit()
        for row in generated:
            db.refresh(row)
    return generated


def forecast_sum(db: Session, product: Product, days: int) -> int:
    rows = forecast_product(db, product, max(days, 1))
    return int(math.ceil(sum(row.predicted_quantity for row in rows[:days])))
