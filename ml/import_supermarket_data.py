"""Import the supplied supermarket catalog and complete daily sales panel."""
import argparse
import os
from pathlib import Path
import sys

import pandas as pd
from sqlalchemy import func, insert


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sales-csv", required=True, type=Path)
    parser.add_argument("--catalog-csv", required=True, type=Path)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--business-id", type=int, default=1)
    args = parser.parse_args()
    os.environ["DATABASE_URL"] = args.database_url

    from app.db import SessionLocal
    from app.models import Business, Category, Product, Sale, Supplier

    sales = pd.read_csv(args.sales_csv, parse_dates=["date"])
    catalog = pd.read_csv(args.catalog_csv, dtype={"Product_ID": str})
    sales["SKU"] = sales["SKU"].astype(str).str.strip()
    catalog["Product_ID"] = catalog["Product_ID"].astype(str).str.strip()
    if sales.duplicated(["date", "SKU"]).any():
        raise ValueError("Sales file has duplicate SKU/date rows")
    if set(sales["SKU"]) != set(catalog["Product_ID"]):
        raise ValueError("Sales and catalog files do not contain the same SKUs")

    db = SessionLocal()
    try:
        business = db.get(Business, args.business_id)
        if not business:
            raise ValueError(f"Business {args.business_id} does not exist in the target database")

        sku_list = catalog["Product_ID"].tolist()
        existing = db.query(Product).filter(
            Product.business_id == business.id, Product.sku.in_(sku_list)
        ).all()
        if existing:
            existing_ids = [product.id for product in existing]
            present_sales = db.query(func.count(Sale.id)).filter(
                Sale.product_id.in_(existing_ids),
                Sale.date >= sales["date"].min().date(),
                Sale.date <= sales["date"].max().date(),
            ).scalar()
            if len(existing) == len(sku_list) and present_sales == len(sales):
                print(f"Dataset already imported: {len(existing)} products, {present_sales} sales rows.")
                return
            raise ValueError(
                "Some dataset SKUs or sales already exist in the target database; "
                "use a fresh database to avoid duplicate or partial imports"
            )

        categories = {
            row.name: row
            for row in db.query(Category).filter(Category.business_id == business.id).all()
        }
        for name in sorted(catalog["Category"].astype(str).unique()):
            if name not in categories:
                row = Category(
                    business_id=business.id,
                    name=name,
                    is_grocery=name not in {"Household", "Personal Care", "Baby Care", "Pooja / Indian household"},
                )
                db.add(row)
                categories[name] = row
        db.flush()

        suppliers = {
            row.name: row
            for row in db.query(Supplier).filter(Supplier.business_id == business.id).all()
        }
        for name in sorted(catalog["Supplier"].astype(str).unique()):
            if name not in suppliers:
                row = Supplier(business_id=business.id, name=name, lead_time_days=3)
                db.add(row)
                suppliers[name] = row
        db.flush()

        products = []
        for row in catalog.to_dict(orient="records"):
            stock = int(row["Quantity_in_Stock"])
            reorder = int(row["Reorder_Level"])
            products.append(Product(
                business_id=business.id,
                sku=str(row["Product_ID"]),
                name=str(row["Product_Name"]),
                category_id=categories[str(row["Category"])].id,
                supplier_id=suppliers[str(row["Supplier"])].id,
                unit="pack",
                price=float(row["Selling_Price_INR"]),
                current_stock=stock,
                minimum_stock=reorder,
                maximum_stock=max(stock, reorder * 3),
                reorder_point=reorder,
                safety_stock=0,
                lead_time_days=3,
            ))
        db.add_all(products)
        db.flush()
        product_ids = {product.sku: product.id for product in products}

        sales = sales.copy()
        sales["product_id"] = sales["SKU"].map(product_ids).astype(int)
        sales["revenue"] = sales["quantity_sold"] * sales["selling_price"]
        columns = ["date", "product_id", "quantity_sold", "selling_price", "promotion_flag", "holiday_flag", "revenue"]
        for start in range(0, len(sales), 20000):
            part = sales.iloc[start:start + 20000]
            records = []
            for row in part[columns].itertuples(index=False, name=None):
                day, product_id, quantity, price, promotion, holiday, revenue = row
                records.append({
                    "business_id": business.id,
                    "date": day.date(),
                    "product_id": product_id,
                    "quantity_sold": int(quantity),
                    "unit_price": float(price),
                    "discount": 0.0,
                    "promotion": bool(promotion),
                    "holiday": bool(holiday),
                    "channel": "store",
                    "location": "Indian Supermarket",
                    "revenue": float(revenue),
                })
            db.execute(insert(Sale), records)
        db.commit()
        print(f"Imported {len(products)} products and {len(sales)} dated sales rows into business {business.id}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
