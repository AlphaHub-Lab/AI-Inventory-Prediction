"""
Universal Store Configuration & Capability Engine
Provides business-type-aware feature toggles, unit definitions, validation rules,
and identity models for:
- Grocery
- Medical / Pharmacy
- Stationery
- Food / Restaurant / Food Business
- Dairy
- Clothing / Apparel
- Others / General Retail
"""

from typing import Any, Dict, List, Optional

STORE_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "grocery": {
        "business_type": "grocery",
        "display_name": "Grocery Supermarket",
        "features": {
            "weight": True,
            "volume": True,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": False,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["kg", "g", "L", "ml", "packet", "piece", "box", "bag", "pouch"],
        "allow_decimal_quantity": True,
        "quantity_step": 0.5,
        "expiry_warning_days": 14,
        "identity_fields": ["product_name", "pack_size", "unit"],
    },
    "medical": {
        "business_type": "medical",
        "display_name": "Medical / Pharmacy",
        "features": {
            "weight": False,
            "volume": False,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": True,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": True,
            "dosage_form": True,
            "strength": True,
            "manufacturer": True,
        },
        "default_units": ["strip", "box", "bottle", "vial", "pack", "piece", "tube", "ampoule"],
        "allow_decimal_quantity": False,
        "quantity_step": 1.0,
        "expiry_warning_days": 60,
        "identity_fields": ["product_name", "strength", "dosage_form", "pack_size", "batch_number"],
    },
    "stationery": {
        "business_type": "stationery",
        "display_name": "Stationery & Office Supplies",
        "features": {
            "weight": False,
            "volume": False,
            "pack_size": True,
            "expiry": False,
            "batch": False,
            "serial_number": False,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["piece", "pack", "box", "dozen", "set", "ream", "bundle"],
        "allow_decimal_quantity": False,
        "quantity_step": 1.0,
        "expiry_warning_days": 0,
        "identity_fields": ["product_name", "pack_size", "unit"],
    },
    "restaurant": {
        "business_type": "restaurant",
        "display_name": "Food / Restaurant / Hospitality",
        "features": {
            "weight": True,
            "volume": True,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": False,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["kg", "g", "L", "ml", "bag", "can", "box", "carton", "packet"],
        "allow_decimal_quantity": True,
        "quantity_step": 0.5,
        "expiry_warning_days": 7,
        "identity_fields": ["product_name", "unit"],
    },
    "food": {
        "business_type": "food",
        "display_name": "Food Business & Provisions",
        "features": {
            "weight": True,
            "volume": True,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": False,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["kg", "g", "L", "ml", "bag", "box", "packet", "pouch"],
        "allow_decimal_quantity": True,
        "quantity_step": 0.5,
        "expiry_warning_days": 7,
        "identity_fields": ["product_name", "unit"],
    },
    "dairy": {
        "business_type": "dairy",
        "display_name": "Dairy & Cold Chain",
        "features": {
            "weight": True,
            "volume": True,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": False,
            "size": False,
            "color": False,
            "style": False,
            "variants": False,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["packet", "pouch", "bottle", "cup", "tin", "kg", "L"],
        "allow_decimal_quantity": True,
        "quantity_step": 1.0,
        "expiry_warning_days": 3,
        "identity_fields": ["product_name", "pack_size", "unit"],
    },
    "clothing": {
        "business_type": "clothing",
        "display_name": "Clothing & Apparel",
        "features": {
            "weight": False,
            "volume": False,
            "pack_size": False,
            "expiry": False,
            "batch": False,
            "serial_number": False,
            "size": True,
            "color": True,
            "style": True,
            "variants": True,
            "custom_attributes": False,
            "prescription": False,
        },
        "default_units": ["piece", "pair", "set", "pack"],
        "allow_decimal_quantity": False,
        "quantity_step": 1.0,
        "expiry_warning_days": 0,
        "identity_fields": ["product_name", "size", "color", "style", "variant_name"],
    },
    "others": {
        "business_type": "others",
        "display_name": "General Retail / Specialty",
        "features": {
            "weight": True,
            "volume": True,
            "pack_size": True,
            "expiry": True,
            "batch": True,
            "serial_number": True,
            "size": True,
            "color": True,
            "style": True,
            "variants": True,
            "custom_attributes": True,
            "prescription": False,
        },
        "default_units": ["piece", "unit", "box", "pack", "set", "kg", "meter", "pair"],
        "allow_decimal_quantity": True,
        "quantity_step": 1.0,
        "expiry_warning_days": 30,
        "identity_fields": ["product_name", "sku"],
    },
}


def normalize_business_type(raw_type: Optional[str]) -> str:
    """Normalize store type string into standard canonical key."""
    if not raw_type:
        return "grocery"
    cleaned = raw_type.lower().strip()
    if cleaned in STORE_CAPABILITIES:
        return cleaned
    if "pharm" in cleaned or "med" in cleaned:
        return "medical"
    if "cloth" in cleaned or "apparel" in cleaned or "fashion" in cleaned:
        return "clothing"
    if "stat" in cleaned or "station" in cleaned:
        return "stationery"
    if "dairy" in cleaned or "milk" in cleaned:
        return "dairy"
    if "rest" in cleaned or "cafe" in cleaned or "hotel" in cleaned or "food" in cleaned:
        return "restaurant"
    return "others"


def get_store_capability(raw_type: Optional[str]) -> Dict[str, Any]:
    """Retrieve full capability descriptor for given business type."""
    norm = normalize_business_type(raw_type)
    cap = dict(STORE_CAPABILITIES.get(norm, STORE_CAPABILITIES["others"]))
    # Provide friendly aliases for frontend and API consistency
    cap["name"] = cap.get("display_name", norm.capitalize())
    cap["units"] = cap.get("default_units", ["unit"])
    cap["allow_decimals"] = cap.get("allow_decimal_quantity", True)
    return cap


def validate_store_item_quantity(raw_type: Optional[str], quantity: float) -> float:
    """Validates quantity according to store capability rules."""
    cap = get_store_capability(raw_type)
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0.")
    if not cap["allow_decimal_quantity"]:
        return float(int(quantity))
    return round(quantity, 3)
