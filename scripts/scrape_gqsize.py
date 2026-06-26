#!/usr/bin/env python3
"""Scrape GQSize collection products into dashboard-ready files."""

from __future__ import annotations

import csv
import html
import json
import re
import statistics
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_URL = "https://gqsize.com"
COLLECTION_URL = f"{BASE_URL}/collections/all"
PRODUCTS_URL = f"{COLLECTION_URL}/products.json?limit=250"
RECOMMENDATION_COLLECTIONS = {
    "new": ("สินค้าใหม่", "new-arrivals"),
    "bestseller": ("สินค้าขายดี", "bestsellers"),
    "bearsize": ("ไซส์หมี", "bearsize"),
    "scrubs": ("ชุดสครับ", "promed"),
}
FUNCTION_COLLECTIONS = {
    "Underwear": "underwear",
}
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


FUNCTION_RULES = [
    ("Suits & Jackets", ["suit", "jacket", "blazer", "แจ็กเก็ต", "สูท"]),
    ("Tops", ["shirt", "polo", "t-shirt", "tank", "sleeves", "sleeveless", "jersey", "hoodie", "underscrub", "oxford", "เสื้อ"]),
    ("Bottoms", ["pants", "jeans", "shorts", "trousers", "chino", "กางเกง"]),
    ("Underwear", ["boxer", "underwear", "trunk"]),
]

NON_CLOTHING_TYPES = {
    "Biker Mask",
    "Cap",
    "Lanyard",
    "Light Shaver",
    "Mask",
    "PPLR_HIDDEN_PRODUCT",
    "SMART Clean",
    "Scrub Bear Gift",
    "Sock Every day",
    "Sock Work Day",
}

NON_CLOTHING_TITLE_KEYWORDS = [
    "baseball cap",
    "canvas tote",
    "foldable mirror",
    "heat patch",
    "lanyard",
    "light shaver",
    "smart clean",
    "sock",
    "wearable love",
]

SERIES_RULES = [
    "Cool Tech",
    "Smellblock",
    "Perfect",
    "Minimal",
    "GQWhite",
    "Pro MED",
    "ProMED",
    "Performance",
    "Smart",
    "GQMax",
    "Summer",
    "Sport",
    "Bear Size",
]

INNOVATION_RULES = [
    ("COOL TECH", "Cooling", "ช่วยจัดการความร้อนและเพิ่มความสบายขณะสวมใส่",
     [r"cool\s*tech", r"เย็นสบาย", r"สัมผัสเย็น"]),
    ("SMELLBLOCK", "Odor control", "ช่วยลดหรือควบคุมกลิ่นไม่พึงประสงค์",
     [r"smell\s*block", r"smellblock", r"anti[-\s]?odor", r"ลดกลิ่น", r"ระงับกลิ่น"]),
    ("Water & Stain Repellent", "Protection", "ช่วยสะท้อนน้ำ ลดการเกาะของคราบ และดูแลรักษาง่าย",
     [r"repeltech", r"สะท้อนน้ำ", r"กันน้ำ", r"กันเปื้อน", r"คราบ.*ล้างออกง่าย"]),
    ("Wrinkle Resistant", "Easy care", "ช่วยลดรอยยับและลดภาระในการรีด",
     [r"wrinkleless", r"wrinkle[-\s]?free", r"ไม่ยับ", r"ลดรอยยับ", r"รีดง่าย"]),
    ("UV Protection", "Protection", "ช่วยปกป้องผิวจากรังสี UV ตามคำอธิบายของสินค้า",
     [r"uv\s*protect", r"ป้องกัน\s*uv", r"กัน\s*uv", r"สะท้อน\s*uv"]),
    ("BAC-OFF / Antibacterial", "Hygiene", "ช่วยลดการสะสมหรือการเติบโตของแบคทีเรีย",
     [r"bac[-\s]?off", r"anti[-\s]?bacterial", r"antibacterial", r"ยับยั้งแบคทีเรีย", r"ต้านแบคทีเรีย"]),
    ("Breathable / Ventilation", "Comfort", "ช่วยระบายอากาศและเพิ่มความสบายระหว่างใช้งาน",
     [r"ระบายอากาศ", r"หายใจสะดวก", r"breathable", r"ventilation"]),
    ("Quick Dry", "Performance", "ช่วยให้ผ้าแห้งเร็ว เหมาะกับการใช้งานต่อเนื่อง",
     [r"quick\s*dry", r"แห้งไว", r"แห้งเร็ว"]),
    ("Stretch Fabric", "Mobility", "เพิ่มความยืดหยุ่นและความคล่องตัวในการเคลื่อนไหว",
     [r"ผ้ายืด", r"ยืดหยุ่น", r"\bstretch\b", r"4[-\s]?way"]),
    ("PM2.5 Filtration", "Protection", "ออกแบบเพื่อช่วยกรองฝุ่น PM2.5",
     [r"pm\s*2\.?5", r"pm2\.?5", r"กรองฝุ่น"]),
    ("Washable & Reusable", "Sustainability", "ซักและนำกลับมาใช้ซ้ำได้ตามคำอธิบายของสินค้า",
     [r"ซัก.*ใช้ซ้ำ", r"ซักและใส่ซ้ำ", r"washable", r"reusable"]),
    ("EXTRA EGG ROOM", "Ergonomic design", "เพิ่มพื้นที่และความสบายด้วยโครงสร้างเฉพาะจุด",
     [r"extra\s*egg\s*room", r"egg\s*room"]),
    ("ON-THE-MOVE POCKET", "Functional design", "เพิ่มช่องเก็บของที่ออกแบบเพื่อการเคลื่อนไหว",
     [r"on[-\s]?the[-\s]?move\s*pocket"]),
    ("GQ POUCH / Easy Access", "Functional design", "ออกแบบช่องหรือจุดเปิดให้ใช้งานสะดวกขึ้น",
     [r"gq\s*pouch", r"easy\s*access"]),
    ("Inclusive Size Design", "Fit innovation", "พัฒนาแพตเทิร์นเพื่อรองรับสรีระและช่วงไซซ์ที่กว้างขึ้น",
     [r"bear\s*size", r"ไซซ์ใหญ่"]),
    ("Multi-pocket Design", "Functional design", "เพิ่มพื้นที่จัดเก็บด้วยการออกแบบหลายกระเป๋า",
     [r"[5-9]\s*กระเป๋า", r"multi[-\s]?pocket"]),
]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            ),
            "Accept": "application/json,text/html,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_material_from_page(handle: str) -> str:
    page_html = fetch_text(f"{BASE_URL}/products/{handle}")
    plain_text = strip_html(page_html)
    match = re.search(
        r"\bFabric\s+(.*?)(?=\s+ควรทำดูแลรักษา|\s+วิธีที่แนะนำในการดูแลรักษา|\s+Care\b)",
        plain_text,
        flags=re.I,
    )
    if not match:
        return ""
    material = re.sub(r"\s+", " ", match.group(1)).strip(" -|,.;")
    return material if len(material) <= 600 else ""


def fetch_materials(products: list[dict[str, Any]]) -> dict[str, str]:
    handles = [product.get("handle") for product in products if product.get("handle")]
    materials: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(extract_material_from_page, handle): handle
            for handle in handles
        }
        for future in as_completed(futures):
            handle = futures[future]
            try:
                materials[handle] = future.result()
            except Exception:
                materials[handle] = ""
    return materials


def material_for_color(material: str, color: str) -> str:
    if not material:
        return "ไม่ระบุ"
    clauses = re.findall(
        r"(?:^|-\s*)สี\s+(.+?):\s*(.*?)(?=\s+-\s*สี\s+|$)",
        material,
        flags=re.I,
    )
    if clauses:
        normalized_color = color.strip().lower()
        for color_names, composition in clauses:
            names = [
                name.strip().lower()
                for name in re.split(r"\s*[|,/]\s*", color_names)
            ]
            if normalized_color in names:
                return composition.strip(" -|,.;")
    return material


def money(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_series(title: str, product_type: str, tags: list[str]) -> str:
    haystack = " ".join([title, product_type, *tags]).lower()
    for series in SERIES_RULES:
        if series.lower().replace(" ", "") in haystack.replace(" ", ""):
            return "ProMED" if series == "Pro MED" else series
    return "Other"


def infer_function(title: str, product_type: str, tags: list[str], description: str = "") -> str:
    haystack = " ".join([title, product_type, description, *tags]).lower()
    for group, keywords in FUNCTION_RULES:
        if any(keyword in haystack for keyword in keywords):
            return group
    return "Other"


def infer_brand(title: str, product_type: str, tags: list[str]) -> str:
    haystack = " ".join([title, product_type, *tags]).lower()
    if "the good day lab" in haystack:
        return "The Good Day Lab"
    if "pro med" in haystack or "promed" in haystack or "scrub" in haystack:
        return "GQ Pro MED"
    if "bear size" in haystack:
        return "GQ Bear Size"
    return "GQ"


def is_clothing(product: dict[str, Any]) -> bool:
    product_type = (product.get("product_type") or "").strip()
    title = product.get("title", "").lower()
    if product_type in NON_CLOTHING_TYPES:
        return False
    return not any(keyword in title for keyword in NON_CLOTHING_TITLE_KEYWORDS)


def exclusion_reason(product: dict[str, Any]) -> str | None:
    product_type = (product.get("product_type") or "").strip()
    title = product.get("title", "").lower()
    if product_type == "PPLR_HIDDEN_PRODUCT":
        return "Hidden personalization item"
    if product_type in NON_CLOTHING_TYPES:
        return f"Non-clothing product type: {product_type}"
    matched = next(
        (keyword for keyword in NON_CLOTHING_TITLE_KEYWORDS if keyword in title),
        None,
    )
    if matched:
        return f"Non-clothing title keyword: {matched}"
    return None


def storefront_product_handles() -> set[str]:
    handles: set[str] = set()
    for page in range(1, 50):
        page_html = fetch_text(f"{COLLECTION_URL}?page={page}")
        page_handles = {
            urllib.parse.unquote(match.split("?")[0].split("#")[0])
            for match in re.findall(
                r'href=["\']/products/([^"\']+)',
                page_html,
                flags=re.I,
            )
        }
        if not page_handles:
            break
        previous_count = len(handles)
        handles.update(page_handles)
        if len(handles) == previous_count:
            break
    return handles


def evidence_for_match(text: str, match: re.Match[str]) -> str:
    start = max(0, match.start() - 55)
    end = min(len(text), match.end() + 75)
    evidence = text[start:end].strip(" -|,.;")
    return ("..." if start else "") + evidence + ("..." if end < len(text) else "")


def infer_innovations(product: dict[str, Any], plain_description: str) -> list[dict[str, str]]:
    haystack = " | ".join(
        [
            product.get("title", ""),
            product.get("product_type", ""),
            plain_description,
            " ".join(product.get("tags") or []),
        ]
    )
    innovations = []
    for name, category, benefit, patterns in INNOVATION_RULES:
        match = next(
            (found for pattern in patterns if (found := re.search(pattern, haystack, flags=re.I))),
            None,
        )
        if match:
            innovations.append({
                "name": name,
                "category": category,
                "benefit": benefit,
                "evidence": evidence_for_match(haystack, match),
                "source": "Product title, description or tags",
            })
    return innovations


def color_option_position(product: dict[str, Any]) -> int | None:
    options = product.get("options") or []
    preferred = ["color", "colour", "สี"]
    fallback = ["print", "pattern", "style", "design", "แบบ", "ลาย"]
    for names in (preferred, fallback):
        for option in options:
            name = str(option.get("name") or "").strip().lower()
            if any(token in name for token in names):
                return int(option.get("position") or 1)
    for option in options:
        name = str(option.get("name") or "").strip().lower()
        if not any(token in name for token in ["size", "quantity", "pack", "ไซซ์", "จำนวน"]):
            return int(option.get("position") or 1)
    return None


def variant_color(variant: dict[str, Any], position: int | None) -> str:
    if position:
        value = variant.get(f"option{position}")
        if value:
            return str(value).strip()
    return "ไม่ระบุสี"


def image_for_variants(product: dict[str, Any], variants: list[dict[str, Any]]) -> str:
    variant_ids = {variant.get("id") for variant in variants}
    images = product.get("images") or []
    for image in images:
        if variant_ids.intersection(image.get("variant_ids") or []):
            return image.get("src") or ""
    return images[0].get("src") if images else ""


def normalize_colorway(
    product: dict[str, Any],
    color: str,
    variants: list[dict[str, Any]],
    plain_description: str,
    innovations: list[dict[str, str]],
    recommendation_handles: dict[str, set[str]],
    function_handles: dict[str, set[str]],
    material: str,
) -> dict[str, Any]:
    prices = [money(v.get("price")) for v in variants]
    prices = [p for p in prices if p is not None]
    compare_prices = [money(v.get("compare_at_price")) for v in variants]
    compare_prices = [p for p in compare_prices if p is not None and p > 0]
    available_variants = [v for v in variants if v.get("available")]
    min_price = min(prices) if prices else None
    max_price = max(prices) if prices else None
    max_compare = max(compare_prices) if compare_prices else None
    discount_pct = None
    if min_price and max_compare and max_compare > min_price:
        discount_pct = round((max_compare - min_price) / max_compare * 100, 1)
    title = product.get("title", "")
    product_type = product.get("product_type", "") or "Unspecified"
    tags = product.get("tags") or []
    images = product.get("images") or []
    first_variant_id = variants[0].get("id") if variants else None
    handle = product.get("handle")
    inferred_function = infer_function(title, product_type, tags, plain_description)
    official_function = next(
        (name for name, handles in function_handles.items() if handle in handles),
        None,
    )
    function = official_function or (
        "Bottoms" if inferred_function == "Underwear" else inferred_function
    )
    return {
        "id": f"{product.get('id')}-{color}",
        "source_product_id": product.get("id"),
        "title": title,
        "color": color,
        "handle": handle,
        "recommendation_groups": [
            key
            for key, handles in recommendation_handles.items()
            if handle in handles
        ],
        "recommended": any(
            handle in handles
            for handles in recommendation_handles.values()
        ),
        "url": (
            f"{BASE_URL}/products/{handle}?variant={first_variant_id}"
            if first_variant_id
            else f"{BASE_URL}/products/{handle}"
        ),
        "brand": infer_brand(title, product_type, tags),
        "function": function,
        "series": infer_series(title, product_type, tags),
        "product_type": product_type,
        "description": plain_description,
        "material": material_for_color(material, color),
        "tags": tags,
        "features": [innovation["name"] for innovation in innovations],
        "innovations": innovations,
        "published_at": product.get("published_at"),
        "created_at": product.get("created_at"),
        "updated_at": product.get("updated_at"),
        "image": image_for_variants(product, variants),
        "image_count": len(images),
        "variant_count": len(variants),
        "available_variant_count": len(available_variants),
        "availability": "In stock" if available_variants else "Sold out",
        "colors": [color],
        "color_count": 1,
        "min_price": min_price,
        "max_price": max_price,
        "compare_at_price": max_compare,
        "discount_pct": discount_pct,
        "variants": [
            {
                "id": v.get("id"),
                "title": v.get("title"),
                "sku": v.get("sku"),
                "color": color,
                "available": bool(v.get("available")),
                "price": money(v.get("price")),
                "compare_at_price": money(v.get("compare_at_price")),
            }
            for v in variants
        ],
    }


def normalize_product(
    product: dict[str, Any],
    recommendation_handles: dict[str, set[str]],
    function_handles: dict[str, set[str]],
    material: str,
) -> list[dict[str, Any]]:
    variants = product.get("variants") or []
    position = color_option_position(product)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for variant in variants:
        color = variant_color(variant, position)
        grouped.setdefault(color, []).append(variant)
    plain_description = strip_html(product.get("body_html"))
    innovations = infer_innovations(product, plain_description)
    return [
        normalize_colorway(
            product,
            color,
            color_variants,
            plain_description,
            innovations,
            recommendation_handles,
            function_handles,
            material,
        )
        for color, color_variants in grouped.items()
    ]


def summarize(products: list[dict[str, Any]]) -> dict[str, Any]:
    prices = [p["min_price"] for p in products if p["min_price"] is not None]
    all_features = Counter(feature for p in products for feature in p["features"])
    all_colors = Counter(color for p in products for color in p["colors"])
    discounted = [p for p in products if p["discount_pct"]]
    return {
        "product_count": len(products),
        "variant_count": sum(p["variant_count"] for p in products),
        "in_stock_count": sum(1 for p in products if p["availability"] == "In stock"),
        "sold_out_count": sum(1 for p in products if p["availability"] == "Sold out"),
        "average_min_price": round(statistics.mean(prices), 2) if prices else None,
        "median_min_price": round(statistics.median(prices), 2) if prices else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "discounted_count": len(discounted),
        "by_brand": Counter(p["brand"] for p in products),
        "by_function": Counter(p["function"] for p in products),
        "by_series": Counter(p["series"] for p in products),
        "top_features": all_features.most_common(12),
        "top_colors": all_colors.most_common(15),
    }


def write_csv(products: list[dict[str, Any]]) -> None:
    fields = [
        "title",
        "color",
        "recommended",
        "recommendation_groups",
        "brand",
        "function",
        "series",
        "product_type",
        "material",
        "availability",
        "variant_count",
        "available_variant_count",
        "color_count",
        "colors",
        "features",
        "innovation_categories",
        "min_price",
        "max_price",
        "compare_at_price",
        "discount_pct",
        "url",
        "image",
        "published_at",
        "updated_at",
    ]
    with (DATA_DIR / "gq_products.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for product in products:
            row = {field: product.get(field) for field in fields}
            row["colors"] = " | ".join(product["colors"])
            row["features"] = " | ".join(product["features"])
            row["recommendation_groups"] = " | ".join(product["recommendation_groups"])
            row["innovation_categories"] = " | ".join(
                sorted({item["category"] for item in product["innovations"]})
            )
            writer.writerow(row)


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    raw = json.loads(fetch_text(PRODUCTS_URL))
    recommendation_handles = {
        key: {
            product.get("handle")
            for product in json.loads(
                fetch_text(f"{BASE_URL}/collections/{handle}/products.json?limit=250")
            ).get("products", [])
            if product.get("handle")
        }
        for key, (_, handle) in RECOMMENDATION_COLLECTIONS.items()
    }
    function_handles = {
        key: {
            product.get("handle")
            for product in json.loads(
                fetch_text(f"{BASE_URL}/collections/{handle}/products.json?limit=250")
            ).get("products", [])
            if product.get("handle")
        }
        for key, handle in FUNCTION_COLLECTIONS.items()
    }
    raw_products = raw.get("products", [])
    storefront_handles = storefront_product_handles()
    api_handles = {product.get("handle") for product in raw_products if product.get("handle")}
    excluded_products = [
        {
            "id": product.get("id"),
            "title": product.get("title"),
            "handle": product.get("handle"),
            "product_type": product.get("product_type") or "Unspecified",
            "reason": exclusion_reason(product),
            "url": f"{BASE_URL}/products/{product.get('handle')}",
        }
        for product in raw_products
        if exclusion_reason(product)
    ]
    visible_products = [product for product in raw_products if is_clothing(product)]
    materials = fetch_materials(visible_products)
    products = [
        colorway
        for product in visible_products
        for colorway in normalize_product(
            product,
            recommendation_handles,
            function_handles,
            materials.get(product.get("handle"), ""),
        )
    ]
    products.sort(key=lambda p: (p["function"], p["series"], p["title"], p["color"]))
    audit = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "storefront_linked_product_count": len(storefront_handles),
        "api_product_count": len(raw_products),
        "api_only_handles": sorted(api_handles - storefront_handles),
        "storefront_only_handles": sorted(storefront_handles - api_handles),
        "hidden_product_count": sum(
            product.get("product_type") == "PPLR_HIDDEN_PRODUCT"
            for product in raw_products
        ),
        "excluded_non_clothing_count": sum(
            product.get("product_type") != "PPLR_HIDDEN_PRODUCT"
            for product in raw_products
            if exclusion_reason(product)
        ),
        "clothing_model_count": len(visible_products),
        "product_color_row_count": len(products),
        "variant_count": sum(product["variant_count"] for product in products),
        "excluded_products": excluded_products,
        "recommendation_collection_counts": {
            key: len(handles)
            for key, handles in recommendation_handles.items()
        },
        "function_collection_counts": {
            key: len(handles)
            for key, handles in function_handles.items()
        },
    }
    payload = {
        "source": COLLECTION_URL,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "products": products,
        "summary": summarize(products),
        "audit": audit,
    }

    (DATA_DIR / "gq_products.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "gq_products.js").write_text(
        "window.GQ_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    write_csv(products)
    (DATA_DIR / "gq_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Scraped {len(visible_products)} clothing products into "
        f"{len(products)} product-color rows and {payload['summary']['variant_count']} variants."
    )
    print(
        f"Audit: storefront={len(storefront_handles)}, API={len(raw_products)}, "
        f"API-only={len(api_handles - storefront_handles)}, "
        f"storefront-only={len(storefront_handles - api_handles)}."
    )
    print(f"Data written to {DATA_DIR}")


if __name__ == "__main__":
    main()
