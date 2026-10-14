from datetime import date
from sqlalchemy.orm import Session
from .forecasting import average_daily_sales, forecast_sum
from ..models import ExpiryAlert, Product, ReorderRecommendation, WastePrediction


def evaluate_expiry(db: Session, product: Product) -> ExpiryAlert | None:
    if not product.expiry_date:
        return None
    remaining = (product.expiry_date - date.today()).days
    if remaining < 0:
        severity, action = "expired", "Remove from sale and record compliant disposal or donation."
    elif remaining <= 1:
        severity, action = "within_1_day", "Prioritize selling immediately or donate if eligible."
    elif remaining <= 3:
        severity, action = "within_3_days", "Apply targeted discount and prioritize selling."
    elif remaining <= 7:
        severity, action = "within_7_days", "Monitor closely and consider a promotion."
    else:
        return None
    alert = db.query(ExpiryAlert).filter_by(product_id=product.id, expiry_date=product.expiry_date, status="open").first()
    if not alert:
        alert = ExpiryAlert(business_id=product.business_id, product_id=product.id, severity=severity, expiry_date=product.expiry_date, recommendation=action)
        db.add(alert)
    return alert


def evaluate_waste(db: Session, product: Product) -> WastePrediction | None:
    if not product.expiry_date:
        return None
    shelf_days = max(0, (product.expiry_date - date.today()).days)
    demand = int(round(average_daily_sales(db, product.id) * shelf_days))
    stock_val = float(product.current_stock or 0)
    at_risk = max(0.0, stock_val - demand)
    if at_risk <= 0:
        risk = "LOW"
    elif stock_val and at_risk / stock_val >= .5:
        risk = "HIGH"
    else:
        risk = "MEDIUM"
    action = {"LOW": "Continue monitoring sell-through.", "MEDIUM": "Promote or transfer stock to improve sell-through.", "HIGH": "Stop ordering; discount, prioritize selling, transfer, or donate if eligible."}[risk]
    estimated_val = round(float(at_risk) * float(product.price or 0), 2)
    existing = db.query(WastePrediction).filter_by(product_id=product.id, calculated_for=date.today()).first()
    if existing:
        existing.risk_level, existing.units_at_risk, existing.estimated_value, existing.recommendation = risk, int(at_risk), estimated_val, action
        return existing
    prediction = WastePrediction(business_id=product.business_id, product_id=product.id, risk_level=risk, units_at_risk=int(at_risk), estimated_value=estimated_val, recommendation=action)
    db.add(prediction)
    return prediction


def build_reorder(db: Session, product: Product) -> ReorderRecommendation:
    lead_demand = forecast_sum(db, product, max(1, product.lead_time_days))
    stock_val = float(product.current_stock or 0)
    calculated = max(0, lead_demand + (product.safety_stock or 0) - stock_val)
    quantity = min(calculated, max(0, (product.maximum_stock or 0) - stock_val)) if product.maximum_stock else calculated
    explanation = f"Recommended {int(quantity)} {product.unit}(s): forecast demand during the {product.lead_time_days}-day supplier lead time is {lead_demand}, safety stock is {product.safety_stock}, and current stock is {product.current_stock}."
    row = db.query(ReorderRecommendation).filter_by(product_id=product.id, status="draft").first()
    if row:
        row.forecast_demand, row.recommended_quantity, row.explanation = lead_demand, int(quantity), explanation
        return row
    row = ReorderRecommendation(business_id=product.business_id, product_id=product.id, forecast_demand=lead_demand, recommended_quantity=int(quantity), explanation=explanation)
    db.add(row)
    return row


def refresh_operational_insights(db: Session) -> None:
    for product in db.query(Product).filter(Product.status == "active").all():
        evaluate_expiry(db, product)
        evaluate_waste(db, product)
        if not product.is_weight_based and (product.reorder_point or 0) > 0 and float(product.current_stock or 0) * 5 < float(product.reorder_point or 0):
            build_reorder(db, product)
    db.commit()
