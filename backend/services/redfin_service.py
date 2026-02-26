import requests
from bs4 import BeautifulSoup
import time
import re
import json

REDFIN_BASE = "https://www.redfin.com"
AUTOCOMPLETE_URL = "https://www.redfin.com/stingray/do/location-autocomplete"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.redfin.com/",
}


def search_redfin_address(address: str) -> dict | None:
    """
    Use Redfin's autocomplete to resolve an address to a property URL.
    Returns dict with url and basic info, or None if not found.
    """
    try:
        params = {"location": address, "v": "2", "al": "1", "num_homes": "5"}
        resp = requests.get(AUTOCOMPLETE_URL, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        text = resp.text
        if text.startswith("{}&&"):
            text = text[4:]

        data = json.loads(text)
        payload = data.get("payload", {})
        sections = payload.get("sections", [])

        for section in sections:
            rows = section.get("rows", [])
            for row in rows:
                if row.get("type") == "1" and row.get("url"):
                    return {
                        "url": REDFIN_BASE + row["url"],
                        "name": row.get("name", address),
                    }

        if sections:
            for section in sections:
                rows = section.get("rows", [])
                if rows:
                    row = rows[0]
                    if row.get("url"):
                        return {
                            "url": REDFIN_BASE + row["url"],
                            "name": row.get("name", address),
                        }

        return None
    except Exception as e:
        print(f"Redfin autocomplete error: {e}")
        return None


def _address_from_redfin_url(url: str) -> str:
    """Extract a readable address from a Redfin URL path (e.g. /CA/San-Francisco/123-Main-St-94105/home/...)."""
    try:
        from urllib.parse import unquote, urlparse
        path = urlparse(url).path
        parts = path.strip("/").split("/")
        if "home" in parts:
            idx = parts.index("home")
            if idx >= 3:
                street_zip = unquote(parts[idx - 1]).replace("-", " ")
                city = unquote(parts[idx - 2]).replace("-", " ")
                return f"{street_zip}, {city}"
        if len(parts) >= 3:
            street_zip = unquote(parts[-1]).replace("-", " ")
            city = unquote(parts[-2]).replace("-", " ")
            return f"{street_zip}, {city}"
        return ""
    except Exception:
        return ""


def scrape_redfin_estimate(url: str) -> dict:
    """
    Scrape a Redfin property page for the estimate, beds, baths, sqft, address.
    """
    result = {
        "estimated_value": 0.0,
        "beds": 0,
        "baths": 0,
        "sqft": 0,
        "address": _address_from_redfin_url(url),
    }

    try:
        time.sleep(1)
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        estimate_el = soup.select_one(".avm .statsValue, .avmLabel + .statsValue, .RedfinEstimateValueHeader .value")
        if estimate_el:
            price_text = estimate_el.get_text(strip=True)
            result["estimated_value"] = _parse_price(price_text)

        if result["estimated_value"] == 0:
            price_el = soup.select_one(".statsValue [data-rf-test-id='abp-price'] .value, .price-section .statsValue")
            if price_el:
                result["estimated_value"] = _parse_price(price_el.get_text(strip=True))

        if result["estimated_value"] == 0:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string)
                    if isinstance(ld, dict):
                        price = ld.get("price") or ld.get("offers", {}).get("price")
                        if price:
                            result["estimated_value"] = float(price)
                            break
                except Exception:
                    continue

        address_el = soup.select_one("h1.street-address, .full-address, .street-address, [data-rf-test-id='abp-streetLine']")
        if address_el and address_el.get_text(strip=True):
            result["address"] = address_el.get_text(strip=True)
        elif not result["address"] and soup.find("title"):
            title = soup.find("title").get_text(strip=True)
            if " | Redfin" in title:
                result["address"] = title.replace(" | Redfin", "").strip()

        stats = soup.select(".HomeMainStats .stat-block, .home-main-stats-variant .stat-block, .HomeInfoV2 .stat-block")
        for stat in stats:
            label_el = stat.select_one(".stat-label, .label")
            value_el = stat.select_one(".stat-value, .value")
            if not label_el or not value_el:
                continue
            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(strip=True)
            if "bed" in label:
                result["beds"] = _parse_number(value)
            elif "bath" in label:
                result["baths"] = _parse_number(value)
            elif "sq" in label or "ft" in label:
                result["sqft"] = int(_parse_number(value))

        if result["beds"] == 0 and result["baths"] == 0:
            key_details = soup.select(".keyDetail, .home-facts-table .table-row")
            for row in key_details:
                text = row.get_text(strip=True).lower()
                if "bed" in text:
                    result["beds"] = _parse_number(text)
                elif "bath" in text:
                    result["baths"] = _parse_number(text)
                elif "sq" in text:
                    nums = re.findall(r"[\d,]+", text)
                    if nums:
                        result["sqft"] = int(nums[0].replace(",", ""))

    except Exception as e:
        print(f"Redfin scrape error for {url}: {e}")

    return result


def get_property_data(address: str) -> dict | None:
    """
    Full pipeline: search for address, then scrape the property page.
    """
    search_result = search_redfin_address(address)
    if not search_result:
        return None

    url = search_result["url"]
    details = scrape_redfin_estimate(url)
    details["redfin_url"] = url
    details["address"] = search_result.get("name", address)
    return details


def get_property_data_from_url(url: str) -> dict | None:
    """
    Fetch property data directly from a Redfin URL. Use when you have the exact link.
    """
    if not url or "redfin.com" not in url:
        return None
    url = url.strip()
    if not url.startswith("http"):
        url = REDFIN_BASE + url if url.startswith("/") else "https://" + url
    details = scrape_redfin_estimate(url)
    details["redfin_url"] = url
    if not details.get("address"):
        details["address"] = _address_from_redfin_url(url) or "Property"
    return details


def _parse_price(text: str) -> float:
    text = text.replace("$", "").replace(",", "").strip()
    match = re.search(r"[\d.]+", text)
    if match:
        return float(match.group())
    return 0.0


def _parse_number(text: str) -> float:
    match = re.search(r"[\d.]+", text.replace(",", ""))
    if match:
        return float(match.group())
    return 0.0
