from __future__ import annotations
from typing import Any, Dict, List, Optional
from .utils import _get, _as_json, _join

__all__ = ["flatten_place"]

# Map Google enum strings to compact integers while keeping the enum too.

_PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

# addressComponents.type -> column name (pick one per group)

_ADDR_TYPE_TO_COL = {
    "street_number": "addr_street_number",
    "route": "addr_route",
    "sublocality_level_1": "addr_sublocality",
    "sublocality": "addr_sublocality",
    "locality": "addr_locality",
    "administrative_area_level_2": "addr_admin_area2",
    "administrative_area_level_1": "addr_admin_area1",
    "country": "addr_country",
    "postal_code": "addr_postal_code",
    "postal_code_suffix": "addr_postal_code_suffix",
}


# --- helpers ---------------------------------------------------------------


def _expand_address_components(ac_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(ac_list, list):
        return out
    for comp in ac_list:
        types = comp.get("types", []) or []
        long_text = comp.get("longText") or comp.get("long_name")
        short_text = comp.get("shortText") or comp.get("short_name")
        for t in types:
            col = _ADDR_TYPE_TO_COL.get(t)
            if not col:
                continue
            # prefer longText; fall back to shortText
            out.setdefault(col, long_text or short_text)
            # country code is useful too
            if t == "country":
                out.setdefault("addr_country_code", short_text)
    return out

def _expand_hours(prefix: str, hours: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(hours, dict):
        return out
    # common: openNow + weekdayDescriptions + nextCloseTime
    if "openNow" in hours:
        out[f"{prefix}_open_now"] = bool(hours.get("openNow"))
    if "weekdayDescriptions" in hours:
        out[f"{prefix}_weekday_desc"] = _join(hours.get("weekdayDescriptions"), " | ")
    if "nextCloseTime" in hours:
        out[f"{prefix}_next_close_time"] = hours.get("nextCloseTime")
    # keep the raw periods as JSON if present
    if "periods" in hours:
        out[f"{prefix}_periods_json"] = _as_json(hours.get("periods"))
    return out

def _expand_price_range(pr: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(pr, dict):
        return out
    start = pr.get("startPrice") or {}
    out["price_start_units"] = start.get("units")
    out["price_start_currency"] = start.get("currencyCode")
    return out

def _expand_viewport(vp: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(vp, dict):
        return out
    low = vp.get("low") or {}
    high = vp.get("high") or {}
    out["viewport_low_lat"]  = low.get("latitude")
    out["viewport_low_lng"]  = low.get("longitude")
    out["viewport_high_lat"] = high.get("latitude")
    out["viewport_high_lng"] = high.get("longitude")
    return out

def _expand_plus_code(pc: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(pc, dict):
        return out
    out["pluscode_global"]   = pc.get("globalCode")
    out["pluscode_compound"] = pc.get("compoundCode")
    return out



# --- main flattener --------------------------------------------------------

def flatten_place(p: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
    """
    Flatten a Google Places (v1) result into analysis-friendly columns.
    - Respects the requested `fields` list (expects 'places.*' names).
    - Expands common nested objects into dedicated columns.
    - Falls back to JSON strings for unknown dicts/lists.
    """
    out: Dict[str, Any] = {}

    # Normalize field list (strip + ensure 'places.' prefix handling)
    norm_fields = [f.strip() for f in fields if f and f.strip()]
    # Provide a quick membership test that tolerates presence/absence of 'places.' prefix
    def _want(key: str) -> bool:
        return (key in norm_fields) or (("places." + key) in norm_fields)

    # --- straightforward scalar/known fields
    if _want("id"):                    out["id"] = p.get("id")
    if _want("name"):                  out["resource_name"] = p.get("name")  # e.g., 'places/...'
    if _want("displayName"):           out["display_name"] = _get(p, "displayName.text")
    if _want("formattedAddress"):      out["formatted_address"] = p.get("formattedAddress")
    if _want("shortFormattedAddress"): out["short_address"] = p.get("shortFormattedAddress")
    if _want("primaryType"):           out["primary_type"] = p.get("primaryType")
    if _want("primaryTypeDisplayName"):out["primary_type_display"] = _get(p, "primaryTypeDisplayName.text")
    if _want("internationalPhoneNumber"): out["phone"] = p.get("internationalPhoneNumber")
    if _want("websiteUri"):            out["website"] = p.get("websiteUri")
    if _want("googleMapsUri"):         out["gmap_url"] = p.get("googleMapsUri")
    if _want("businessStatus"):        out["business_status"] = p.get("businessStatus")
    if _want("pureServiceAreaBusiness"): out["is_service_area_only"] = p.get("pureServiceAreaBusiness")

    # rating + counts
    if _want("rating"):            out["rating"] = p.get("rating")
    if _want("userRatingCount"):   out["user_ratings_total"] = p.get("userRatingCount")

    # types (list)
    if _want("types"):
        types = p.get("types")
        out["types"] = _join(types, ",")

    # location (lat/lng)
    if _want("location"):
        out["lat"] = _get(p, "location.latitude")
        out["lng"] = _get(p, "location.longitude")

    # viewport
    if _want("viewport"):
        out.update(_expand_viewport(p.get("viewport")))

    # plusCode
    if _want("plusCode"):
        out.update(_expand_plus_code(p.get("plusCode")))

    # price level enum + numeric
    if _want("priceLevel"):
        lvl = p.get("priceLevel")
        out["price_level"] = lvl
        out["price_level_num"] = _PRICE_LEVEL_MAP.get(lvl, None)

    # priceRange structured startPrice
    if _want("priceRange"):
        out.update(_expand_price_range(p.get("priceRange")))

    # opening hours (current + regular)
    if _want("currentOpeningHours"):
        out.update(_expand_hours("current_hours", p.get("currentOpeningHours")))
    if _want("regularOpeningHours"):
        out.update(_expand_hours("regular_hours", p.get("regularOpeningHours")))

    # containingPlaces (list) – keep lightweight summary
    if _want("containingPlaces"):
        cp = p.get("containingPlaces")
        # try names if present; otherwise JSON
        if isinstance(cp, list):
            names = []
            for c in cp:
                nm = _get(c, "displayName.text") or c.get("id") or c.get("name")
                if nm: names.append(nm)
            out["containing_places"] = _join(names, ";")
            if not names:
                out["containing_places_json"] = _as_json(cp)
        else:
            out["containing_places_json"] = _as_json(cp)

    # address components (expand)
    if _want("addressComponents"):
        out.update(_expand_address_components(p.get("addressComponents")))

    # reviews + reviewSummary
    if _want("reviews"):
        revs = p.get("reviews")
        if isinstance(revs, list):
            out["review_count"] = len(revs)
            # keep a compact digest of up to 3 texts (safe for CSV)
            texts = []
            for r in revs[:3]:
                txt = _get(r, "text.text") or _get(r, "originalText.text")
                if txt: texts.append(txt.replace("\n", " ").strip())
            out["reviews_sample"] = _join(texts, " || ")
            # keep raw JSON for full fidelity if needed downstream
            out["reviews_json"] = _as_json(revs)
        else:
            out["reviews_json"] = _as_json(revs)

    if _want("reviewSummary"):
        rs = p.get("reviewSummary")
        # keep as JSON; structure varies
        out["review_summary_json"] = _as_json(rs)

    # addressComponents sometimes requested + formattedAddress absent:
    # already expanded; nothing else to do here.

    # --- catch-all: for any requested field we didn’t explicitly expand,
    #     provide a JSON column so nothing “vanishes”.
    requested_keys = {f.replace("places.", "") for f in norm_fields}
    materialized = set(k for k in [
        "id","name","displayName","formattedAddress","shortFormattedAddress","primaryType",
        "primaryTypeDisplayName","internationalPhoneNumber","websiteUri","googleMapsUri",
        "businessStatus","pureServiceAreaBusiness","rating","userRatingCount","types",
        "location","viewport","plusCode","priceLevel","priceRange","currentOpeningHours",
        "regularOpeningHours","containingPlaces","addressComponents","reviews","reviewSummary",
    ] if _want(k))
    for k in (requested_keys - materialized):
        val = _get(p, k)
        if isinstance(val, dict) or isinstance(val, list):
            out[f"{k}_json"] = _as_json(val)
        else:
            out[k] = val

    return out