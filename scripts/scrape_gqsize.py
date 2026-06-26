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
     [r"cool\s*tech", r"ผ้าเย็น", r"เย็นลงสูงสุด", r"ลดอุณหภูมิ", r"เจลเย็น", r"เย็นทั้งตัว"]),
    ("SMELLBLOCK", "Odor control", "ช่วยลดหรือควบคุมกลิ่นไม่พึงประสงค์",
     [r"smell\s*block", r"smellblock", r"anti[-\s]?odor", r"ลดกลิ่น", r"ระงับกลิ่น"]),
    ("Water & Stain Repellent", "Protection", "ช่วยสะท้อนน้ำ ลดการเกาะของคราบ และดูแลรักษาง่าย",
     [r"repeltech", r"สะท้อนน้ำ", r"กันน้ำ", r"กันเปื้อน", r"คราบ.*ล้างออกง่าย"]),
    ("GQ SWEAT DELETE", "Sweat management", "ช่วยซับเหงื่อด้านในและลดคราบเหงื่อซึมตามคำอธิบายสินค้า",
     [r"gq\s*sweat\s*delete", r"sweat\s*delete", r"กันคราบเหงื่อ", r"ลดคราบเหงื่อ", r"ซับเหงื่อ"]),
    ("GQ FIT-PRO COLLAR", "Fit innovation", "คอเสื้อโอบพอดีกับรูปคอ ช่วยให้ดูสมาร์ทและกระชับ",
     [r"gq\s*fit[-\s]?pro\s*collar", r"fit[-\s]?pro\s*collar", r"คอเสื้อโอบพอดี", r"คอเสื้อ.*กระชับ"]),
    ("GQ ANTI-RIP", "Durability", "เสริมจุดตะเข็บหรือโครงสร้างเพื่อลดโอกาสฉีกขาด",
     [r"gq\s*anti[-\s]?rip", r"anti[-\s]?rip", r"ป้องกันการฉีกขาด", r"เสริมผ้าตะเข็บ"]),
    ("GQ STRONG BUTTONS", "Durability", "กระดุมแน่นและหลุดยากตามคำอธิบายสินค้า",
     [r"gq\s*strong\s*buttons?", r"strong\s*buttons?", r"กระดุมแน่น", r"หลุดยาก"]),
    ("GQ BUFFET BUTTON", "Adjustable fit", "กระดุมบุฟเฟต์ที่ช่วยขยายหรือปรับ fit ได้",
     [r"gq\s*buffet\s*buttons?", r"buffet\s*buttons?", r"กระดุมบุฟเฟต์", r"กระดุม.*ขยายได้"]),
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
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<noscript\b[^>]*>.*?</noscript>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", " ", value, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_product_page_details(handle: str) -> dict[str, str]:
    page_html = fetch_text(f"{BASE_URL}/products/{handle}")
    plain_text = strip_html(page_html)
    match = re.search(
        r"\bFabric\s+(.*?)(?=\s+ควรทำดูแลรักษา|\s+วิธีที่แนะนำในการดูแลรักษา|\s+Care\b)",
        plain_text,
        flags=re.I,
    )
    material = ""
    if match:
        material = re.sub(r"\s+", " ", match.group(1)).strip(" -|,.;")
        if len(material) > 600:
            material = ""
    return {"material": material, "page_text": relevant_product_text(plain_text)}


def relevant_product_text(plain_text: str) -> str:
    segments: list[str] = []

    innovation_start = plain_text.find("นวัตกรรม GQ ในสินค้าชิ้นนี้")
    if innovation_start >= 0:
        innovation_end_candidates = [
            plain_text.find(marker, innovation_start + 1)
            for marker in ["Bestsellers", "Product Spec", "รายละเอียด สินค้า"]
        ]
        innovation_end_candidates = [index for index in innovation_end_candidates if index > innovation_start]
        innovation_end = min(innovation_end_candidates) if innovation_end_candidates else innovation_start + 900
        segments.append(plain_text[innovation_start:innovation_end])

    spec_start_candidates = [
        plain_text.find(marker)
        for marker in ["Product Spec", "รายละเอียด สินค้า", "Description"]
    ]
    spec_start_candidates = [index for index in spec_start_candidates if index >= 0]
    if spec_start_candidates:
        spec_start = min(spec_start_candidates)
        spec_end_candidates = [
            plain_text.find(marker, spec_start + 1)
            for marker in ["ควรทำดูแลรักษา", "วิธีที่แนะนำในการดูแลรักษา", "ตารางไซซ์", "Size Guide"]
        ]
        spec_end_candidates = [index for index in spec_end_candidates if index > spec_start]
        spec_end = min(spec_end_candidates) if spec_end_candidates else spec_start + 2500
        segments.append(plain_text[spec_start:spec_end])

    return " | ".join(segments) if segments else plain_text[:3500]


def fetch_product_page_details(products: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    handles = [product.get("handle") for product in products if product.get("handle")]
    details: dict[str, dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(extract_product_page_details, handle): handle
            for handle in handles
        }
        for future in as_completed(futures):
            handle = futures[future]
            try:
                details[handle] = future.result()
            except Exception:
                details[handle] = {"material": "", "page_text": ""}
    return details


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
    title_text = title.lower()
    type_text = product_type.lower()
    if any(keyword in type_text for keyword in ["pants", "jeans", "shorts", "chino"]):
        return "Bottoms"
    if any(keyword in title_text for keyword in ["pants", "jeans", "shorts", "chino"]):
        return "Bottoms"
    for group, keywords in FUNCTION_RULES:
        if any(keyword in haystack for keyword in keywords):
            return group
    return "Other"


def infer_subcategory(title: str, product_type: str, series: str, function: str) -> str:
    haystack = " ".join([title, product_type, series, function]).lower()
    compact = haystack.replace(" ", "").replace("-", "")
    title_text = title.lower()

    if "perfect" in title_text and "oxford" in title_text:
        return "Perfect Oxford Shirt"
    if "gqwhite" in title_text:
        return "GQWhite Shirt"
    if "peanuts" in title_text and "boxy" in title_text:
        return "PEANUTS Boxy Shirt"
    if "minimal jeans" in title_text and "boot" in title_text:
        return "Minimal Jeans Boot Cut"
    if "the good day lab" in title_text:
        if "t-shirt" in title_text and "pack2" in title_text:
            return "Good Day Lab Kids T-Shirt Pack"
        if "t-shirt" in title_text:
            return "Good Day Lab Kids T-Shirt"
        if "long sleeve polo" in title_text and "pack2" in title_text:
            return "Good Day Lab Long Sleeve Polo Pack"
        if "long sleeve polo" in title_text:
            return "Good Day Lab Long Sleeve Polo"
        if "polo" in title_text and "pack2" in title_text:
            return "Good Day Lab Polo Pack"
        if "polo" in title_text and "no package" in title_text:
            return "Good Day Lab Polo No Package"
        if "polo" in title_text:
            return "Good Day Lab Polo"
    if "women scrub pants" in title_text and "elite" in title_text:
        return "Scrub Pants Elite Women"
    if "men scrub pants" in title_text and "elite" in title_text:
        return "Scrub Pants Elite Men"
    if "women scrub pants" in title_text and "premium" in title_text:
        return "Scrub Pants Premium Women"
    if "men scrub pants" in title_text and "premium" in title_text:
        return "Scrub Pants Premium Men"
    if "women scrub shirt" in title_text and "elite" in title_text:
        return "Scrub Shirt Elite Women"
    if "men scrub shirt" in title_text and "elite" in title_text:
        return "Scrub Shirt Elite Men"
    if "women scrub shirt" in title_text and "premium" in title_text:
        return "Scrub Shirt Premium Women"
    if "men scrub shirt" in title_text and "premium" in title_text:
        return "Scrub Shirt Premium Men"
    if "women scrub polo" in title_text:
        return "Scrub Polo Women"
    if "men scrub polo" in title_text:
        return "Scrub Polo Men"
    if "underscrub" in title_text and "women" in title_text:
        return "Underscrub Women"
    if "underscrub" in title_text and "men" in title_text:
        return "Underscrub Men"
    if "women scrub jacket" in title_text and "elite" in title_text:
        return "Scrub Jacket Elite Women"
    if "men scrub jacket" in title_text and "elite" in title_text:
        return "Scrub Jacket Elite Men"

    rules = [
        ("Perfect Oxford Shirt", ["perfect oxford", "perfectoxford", "gqoxford"]),
        ("GQWhite Shirt", ["gqwhite"]),
        ("Bear Size Oxford Shirt", ["bear size oxford"]),
        ("Cool Tech Denim Shirt", ["cool tech denim"]),
        ("PEANUTS Boxy Shirt", ["peanuts boxy"]),
        ("Summer Print Shirt", ["summer print shirt"]),
        ("Summer Aloha T-Shirt", ["summer t-shirt aloha"]),
        ("Smart T-Shirt", ["smart t-shirt"]),
        ("Cool Tech T-Shirt Pocket", ["t-shirt pocket"]),
        ("Cool Tech T-Shirt Regular Print", ["regular t-shirt print"]),
        ("Cool Tech T-Shirt Regular", ["regular t-shirt"]),
        ("Cool Tech T-Shirt Oversized Print", ["oversized t-shirt print"]),
        ("Cool Tech T-Shirt Oversized", ["oversized t-shirt"]),
        ("Cool Tech PEANUTS T-Shirt", ["peanuts", "cool tech", "t-shirt"]),
        ("PEANUTS Everyday T-Shirt", ["everyday", "peanuts"]),
        ("Good Day Lab Kids T-Shirt Pack", ["good day lab", "t-shirt", "pack"]),
        ("Good Day Lab Kids T-Shirt", ["good day lab", "kids", "t-shirt"]),
        ("Good Day Lab Polo Pack", ["good day lab", "polo", "pack"]),
        ("Good Day Lab Long Sleeve Polo", ["good day lab", "long sleeve polo"]),
        ("Good Day Lab Polo", ["good day lab", "polo"]),
        ("Minimal Polo PEANUTS", ["minimal polo", "peanuts"]),
        ("Minimal Polo Stripe", ["minimal polo", "stripe"]),
        ("Minimal Polo", ["minimal polo"]),
        ("Perfect Polo Classic", ["perfect polo", "classic"]),
        ("Perfect Polo Limited", ["perfect polo", "limited"]),
        ("Perfect Polo Twin Tipped", ["perfect polo", "twin tipped"]),
        ("Bear Size Sport T-Shirt", ["bear size sports t-shirt", "bear size sport t-shirt"]),
        ("Bear Size Running T-Shirt", ["running", "training", "t-shirt"]),
        ("Bear Size Running Tank Top", ["running", "training", "tank"]),
        ("Bear Size Sport Polo", ["bear size sports polo", "bear size sport polo"]),
        ("Bear Size Polo", ["bear size polo"]),
        ("Bear Size T-Shirt", ["bear size t-shirt"]),
        ("Minimal Hoodie UV", ["hoodie uv"]),
        ("Minimal Hoodie", ["hoodie"]),
        ("Cool Tech Innerwear Short Sleeve", ["innerwear", "short sleeve"]),
        ("Cool Tech Innerwear Tank Top", ["innerwear", "tank top"]),
        ("Cool Tech Loungewear Long Sleeve", ["loungewear", "long sleeve"]),
        ("Cool Tech Loungewear T-Shirt", ["loungewear", "t-shirt"]),
        ("Cool Tech Loungewear Shorts", ["loungewear", "shorts"]),
        ("Cool Tech Loungewear Pants", ["loungewear", "pants"]),
        ("Cool Tech Jeans Shorts", ["jean shorts"]),
        ("Cool Tech Jeans Boot Cut", ["jeans", "boot cut"]),
        ("Cool Tech Jeans Regular", ["jeans", "regular"]),
        ("Cool Tech Jeans Slim", ["jeans", "slim"]),
        ("Cool Tech Jeans Straight", ["jeans", "straight"]),
        ("Cool Tech Jeans Tapered", ["jeans", "tapered"]),
        ("Minimal Jeans Boot Cut", ["minimal jeans", "boot cut"]),
        ("Minimal Jeans Classic", ["minimal jeans", "classic"]),
        ("Minimal Jeans Relaxed", ["minimal jeans", "relaxed"]),
        ("Minimal Jeans Skinny", ["minimal jeans", "skinny"]),
        ("Minimal Jeans Wide", ["minimal jeans", "wide"]),
        ("Perfect Chino Ankle", ["perfect ankle chino", "chino ankle"]),
        ("Perfect Chino Shorts", ["chino", "shorts"]),
        ("Perfect Chino", ["perfect chino"]),
        ("Perfect Pants Regular", ["perfect pants", "regular"]),
        ("Perfect Pants Relaxed", ["perfect pants", "relaxed"]),
        ("Perfect Pleated Pants", ["perfect pleated"]),
        ("Perfect Shorts", ["perfect shorts"]),
        ("Performance Pants", ["performance pants"]),
        ("Bear Size Work Pants", ["bear size work pants"]),
        ("Bear Size Shorts", ["bear size shorts"]),
        ("Bear Size Sport Shorts", ["bear size sports shorts", "bear size sport shorts"]),
        ("Bear Size Kai Underwear Comfort", ["hor kai comfort"]),
        ("Bear Size Kai Underwear Soft", ["kai noom"]),
        ("Bear Size Cool Tech Underwear Extreme", ["bear size cool tech", "underwear"]),
        ("Cool Tech Boxer", ["boxer"]),
        ("Cool Tech Underwear All-Day", ["all-day secure"]),
        ("Cool Tech Underwear New Normal", ["new normal"]),
        ("Cool Tech Underwear Sports", ["sports collection"]),
        ("Cool Tech Underwear Extreme", ["cool tech", "extreme"]),
        ("Perfect Blazer Relaxed", ["blazer", "relaxed"]),
        ("Perfect Blazer Slim", ["blazer", "slim"]),
        ("Performance Blazer", ["performance blazer"]),
        ("Jean Jacket", ["jean jacket"]),
        ("Scrub Jacket Elite Men", ["men scrub jacket", "elite"]),
        ("Scrub Jacket Elite Women", ["women scrub jacket", "elite"]),
        ("Scrub Jacket Premium", ["scrub premium jacket", "premium scrub jacket"]),
        ("Scrub Pants Premium Men", ["men scrub pants", "premium"]),
        ("Scrub Pants Premium Women", ["women scrub pants", "premium"]),
        ("Scrub Pants Elite Men", ["men scrub pants", "elite"]),
        ("Scrub Pants Elite Women", ["women scrub pants", "elite"]),
        ("Scrub Shirt Premium Men", ["men scrub shirt", "premium"]),
        ("Scrub Shirt Premium Women", ["women scrub shirt", "premium"]),
        ("Scrub Shirt Elite Women", ["women scrub shirt", "elite"]),
        ("Scrub Polo Men", ["men scrub polo"]),
        ("Scrub Polo Women", ["women scrub polo"]),
        ("Underscrub Men", ["underscrub", "men"]),
        ("Underscrub Women", ["underscrub", "women"]),
    ]
    for label, keywords in rules:
        if all(keyword in haystack or keyword.replace(" ", "") in compact for keyword in keywords):
            return label
    return product_type if product_type and product_type != "Unspecified" else f"{series} {function}".strip()


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


def infer_innovations(product: dict[str, Any], plain_description: str, detail_text: str = "") -> list[dict[str, str]]:
    base_haystack = " | ".join(
        [
            product.get("title", ""),
            product.get("product_type", ""),
            plain_description,
            " ".join(product.get("tags") or []),
        ]
    )
    haystack = " | ".join([base_haystack, detail_text])
    innovations = []
    for name, category, benefit, patterns in INNOVATION_RULES:
        search_text = base_haystack if name == "Inclusive Size Design" else haystack
        match = next(
            (found for pattern in patterns if (found := re.search(pattern, search_text, flags=re.I))),
            None,
        )
        if match:
            innovations.append({
                "name": name,
                "category": category,
                "benefit": benefit,
                "evidence": evidence_for_match(search_text, match),
                "source": "Product title, PDP description or tags",
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
    series = infer_series(title, product_type, tags)
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
        "series": series,
        "product_type": product_type,
        "product_subcategory": infer_subcategory(title, product_type, series, function),
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
    page_detail: dict[str, str],
) -> list[dict[str, Any]]:
    variants = product.get("variants") or []
    position = color_option_position(product)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for variant in variants:
        color = variant_color(variant, position)
        grouped.setdefault(color, []).append(variant)
    plain_description = strip_html(product.get("body_html"))
    detail_text = page_detail.get("page_text", "")
    innovations = infer_innovations(product, plain_description, detail_text)
    return [
        normalize_colorway(
            product,
            color,
            color_variants,
            plain_description,
            innovations,
            recommendation_handles,
            function_handles,
            page_detail.get("material", ""),
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
        "product_subcategory",
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
    product_page_details = fetch_product_page_details(visible_products)
    products = [
        colorway
        for product in visible_products
        for colorway in normalize_product(
            product,
            recommendation_handles,
            function_handles,
            product_page_details.get(product.get("handle"), {}),
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
