"""Normalization shared by both parsers, so the comparison isolates HTML parsing.

Input is the raw per-page extraction dict both parsers produce. Output keeps
only public listing facts. Free text is reduced to keyword flags and numbers;
no sentence, seller field, or identifier survives except a salted listing ref.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from decimal import Decimal

CURRENCY_TOKENS = {"US$": "USD", "RD$": "DOP"}
MONEY = re.compile(r"^\s*(US\$|RD\$)\s*([\d,]+(?:\.\d+)?)\s*(?:/\s*(Mes))?\s*$", re.I)
QUANTITY = re.compile(r"^\s*(N/D|[\d,]+(?:\.\d+)?)\s*([A-Za-z0-9²]+)?\s*$")
TEXT_FLAGS = {
    "down_payment": r"\binicial\b",
    "financing": r"financ|\bcuotas?\b|\bbanco\b",
    "negotiable": r"negociable",
    "damage": r"chocad|\bchoque\b|salvage|rebuil|reconstru|inundad|flood",
    "import_history": r"importad|carfax|autocheck|titulo limpio|clean title|version americana",
    "pre_construction": r"en planos?\b|pre-?\s?venta|en construccion|\bentrega\b|fideicomiso",
    "reservation_or_installments": r"separa(?:s|cion)?\b|\bcuotas?\b|contra entrega",
    "furnished": r"amueblad|full furnished|furnished",
    "short_term_rental": r"airbnb|renta corta|rentas cortas|short term",
    "tax_incentive": r"confotur|bono (?:primera )?vivienda|bono itbis",
    "maintenance_fee": r"mantenimiento",
}
TEXT_ROOMS = re.compile(r"(\d+)\s*(?:habitaci|hab\b|dormitor)")
TEXT_AREA = re.compile(r"(\d[\d.,]*)\s*(?:m2|m²|mt2|mts2|mts|metros)")
TEXT_MILEAGE = re.compile(r"(\d[\d.,]*)\s*(?:km|kms|kilometros|millas|mi\b)")


def fold(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", stripped).strip().lower()


def to_decimal(token: str) -> Decimal:
    return Decimal(token.replace(",", ""))


def money(text: str | None) -> dict | None:
    match = MONEY.match(text or "")
    if not match:
        return None
    return {
        "currency": CURRENCY_TOKENS[match.group(1).upper()],
        "amount": str(to_decimal(match.group(2))),
        "period": "month" if match.group(3) else None,
    }


def quantity(text: str | None) -> dict:
    match = QUANTITY.match(text or "")
    if not match:
        return {"raw_shape": re.sub(r"\d", "9", text or ""), "value": None, "unit": None}
    value = None if match.group(1).upper() == "N/D" else str(to_decimal(match.group(1)))
    return {
        "value": value,
        "unit": (match.group(2) or "").lower() or None,
        "missing_marker": match.group(1).upper() == "N/D",
    }


def ticks_to_utc(ticks: str | None) -> str | None:
    if not ticks or not ticks.isdigit():
        return None
    moment = datetime(1, 1, 1, tzinfo=timezone.utc) + timedelta(
        microseconds=int(ticks) // 10
    )
    return moment.isoformat(timespec="minutes")


def listing_ref(site: str, listing_id: str | None, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{site}:{listing_id}".encode()).hexdigest()[:10]


def text_facts(text: str | None) -> dict:
    folded = fold(text or "")
    return {
        "present": bool(folded),
        "flags": {
            name: bool(re.search(pattern, folded)) for name, pattern in TEXT_FLAGS.items()
        },
        "room_counts": sorted({int(n) for n in TEXT_ROOMS.findall(folded)}),
        "areas": sorted(
            {
                str(to_decimal(n.rstrip(".,")))
                for n in TEXT_AREA.findall(folded)
                if re.search(r"\d", n)
            }
        ),
        "mileages": sorted(
            {
                str(to_decimal(n.replace(".", "").rstrip(",")))
                for n in TEXT_MILEAGE.findall(folded)
            }
        ),
        "replacement_char_runs": len(re.findall(r"\?{2,}", text or "")),
    }


def normalize(raw: dict, salt: str) -> dict:
    site = raw["site"]
    specs = {fold(k).rstrip(":"): v for k, v in raw["specs"].items()}
    prices = []
    for label, text in raw["prices"]:
        parsed = money(text)
        prices.append(
            {
                "label": fold(label).rstrip(":") if label else None,
                "parsed": parsed,
                "raw_shape": re.sub(r"\d", "9", text),
            }
        )
    js = raw["js"]
    main = js.get("adPriceMainCurrency")
    implied_rate = None
    usd = [
        p["parsed"]
        for p in prices
        if p["parsed"]
        and p["parsed"]["currency"] == "USD"
        and p["parsed"]["period"] is None
    ]
    if main and usd and len(prices) == 1:
        implied_rate = str(
            (Decimal(main) / Decimal(usd[0]["amount"])).quantize(Decimal("0.0001"))
        )
    record = {
        "site": site,
        "ref": listing_ref(site, raw["listing_id"], salt),
        "title_present": bool(raw["title"]),
        "prices": prices,
        "site_main_currency_amount_present": main is not None,
        "implied_usd_to_main_rate": implied_rate,
        "ad_key_utc": ticks_to_utc(js.get("adKey")),
        "spec_labels": sorted(specs),
        "features": raw["features"],
        "amenity_count": len(raw["amenities"]),
        "visits": raw["visits"],
        "text": raw.get("ad_text_facts") or text_facts(raw["ad_text"]),
        "meta_description_present": bool(raw["meta_description"]),
    }
    if site == "supercarros":
        record |= {
            "title": raw["title"],
            "year_in_title": (
                re.match(r"^\s*(\d{4})\b", raw["title"] or "") or [None, None]
            )[1],
            "site_taxonomy_ids": {
                k: js.get(k) for k in ("adBrand", "adModel", "adCategory", "adFuel")
            },
            "is_new_flag": js.get("adIsNew"),
            "car_age_years": js.get("adCarAge"),
            "mileage": quantity(specs.get("uso")),
            "condition": specs.get("condicion"),
            "body_type": specs.get("tipo"),
            "fuel": specs.get("combustible"),
            "transmission": specs.get("transmision"),
            "traction": specs.get("traccion"),
            "import_spec_accessory": any(
                fold(a) == "version americana" for a in raw["amenities"]
            ),
            "province": raw["seller_city"].split(",")[-1].strip()
            if raw["seller_city"]
            else None,
            "dealer_inventory_link": raw["dealer_link"],
            "meta_mileage": (
                re.search(r"([\d,.]+)\s*(Mi|Km)\.?\s*$", raw["meta_description"] or "")
                or [None]
            )[0],
        }
    else:
        record |= {
            "title_shape": re.sub(r",.*$", ", <sector>", raw["title"] or ""),
            "condition": specs.get("condicion"),
            "current_use": specs.get("uso actual"),
            "built_area": quantity(specs.get("construccion")),
            "land_area": quantity(specs.get("terreno")),
            "floor": specs.get("nivel/piso"),
            "year_built": specs.get("ano construccion"),
            "location": specs.get("localizacion"),
            "rooms": {
                key: next(
                    (
                        m.group(1)
                        for f in raw["features"]
                        if (m := re.match(rf"^([\d.]+)\s+{pattern}", fold(f)))
                    ),
                    None,
                )
                for key, pattern in (
                    ("bedrooms", "habitaci"),
                    ("bathrooms", "bano"),
                    ("parking", "parqueo"),
                )
            },
            "object_type": js.get("adObjectType"),
        }
    return record
