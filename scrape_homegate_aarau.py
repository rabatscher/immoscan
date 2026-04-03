#!/usr/bin/env python3
"""Scrape Homegate listings for 5000 Aarau into JSON.

Usage:
  python scrape_homegate_aarau.py
  python scrape_homegate_aarau.py --html-file page.html --output listings.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

URL = "https://www.homegate.ch/kaufen/immobilien/plz-5000/trefferliste?ac=4.5"


@dataclass
class Listing:
    title: str
    price: Optional[str]
    location: str
    property_type: Optional[str]
    rooms: Optional[float]
    area_sqm: Optional[float]


def normalize_html_to_text(html: str) -> str:
    html = re.sub(r"<script[\\s\\S]*?</script>", " ", html, flags=re.IGNORECASE)
    html = re.sub(r"<style[\\s\\S]*?</style>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_float(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return None


def parse_listings(text: str) -> list[Listing]:
    # Capture rough listing chunks from the normalized page text.
    pattern = re.compile(
        r"(?:CHF\s*[\d'’]+\.?\-?|Preis auf Anfrage)\s+"
        r"(?:(\d+(?:[.,]\d+)?)\s+Zimmer\s+)?"
        r"(?:(\d+(?:[.,]\d+)?)\s*m²\s*Wohnfläche\s+)?"
        r"([^\d].{0,120}?)\s+5000\s+Aarau\s+(.{5,180}?)(?=CHF\s*[\d'’]+\.?\-|Preis auf Anfrage|Wegzeit\s*-|$)",
        flags=re.IGNORECASE,
    )

    listings: list[Listing] = []
    for m in pattern.finditer(text):
        start = m.start()
        prefix = text[max(0, start - 40) : start]

        price_match = re.search(r"(CHF\s*[\d'’]+\.?\-|Preis auf Anfrage)$", prefix + " " + m.group(0))
        price = price_match.group(1).replace(" .", ".") if price_match else None

        rooms = parse_float(m.group(1) or "")
        area = parse_float(m.group(2) or "")
        before_location = re.sub(r"\s+", " ", m.group(3)).strip(" ,-:")
        title = re.sub(r"\s+", " ", m.group(4)).strip(" ,-:")

        property_type = None
        lowered = title.lower()
        for candidate in [
            "etagenwohnung",
            "einfamilienhaus",
            "doppeleinfamilienhaus",
            "doppelhaushälfte",
            "mehrfamilienhaus",
            "villa",
            "wohnung",
            "haus",
        ]:
            if candidate in lowered:
                property_type = candidate
                break
        if property_type is None and before_location:
            property_type = before_location

        listings.append(
            Listing(
                title=title,
                price=price,
                location="5000 Aarau",
                property_type=property_type,
                rooms=rooms,
                area_sqm=area,
            )
        )

    # Deduplicate by (title, price, rooms, area).
    unique: dict[tuple[Optional[str], Optional[str], Optional[float], Optional[float]], Listing] = {}
    for item in listings:
        key = (item.title, item.price, item.rooms, item.area_sqm)
        unique[key] = item
    return list(unique.values())


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=URL)
    parser.add_argument("--html-file", help="Parse a local HTML file instead of fetching the URL")
    parser.add_argument("--output", default="aarau_5000_listings.json")
    args = parser.parse_args()

    html = Path(args.html_file).read_text(encoding="utf-8") if args.html_file else fetch_html(args.url)
    text = normalize_html_to_text(html)
    listings = parse_listings(text)

    Path(args.output).write_text(
        json.dumps([asdict(l) for l in listings], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(listings)} listings to {args.output}")


if __name__ == "__main__":
    main()
