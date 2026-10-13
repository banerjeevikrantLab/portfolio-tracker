import json
import re
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

REDFIN_BASE = "https://www.redfin.com"
AUTOCOMPLETE_URL = "https://www.redfin.com/stingray/do/location-autocomplete"
AVM_URL = "https://www.redfin.com/stingray/api/home/details/avm"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.redfin.com/",
}

# Redfin's CDN answers rate-limited clients with 403/429, or 202 plus a tiny
# JavaScript challenge page instead of the real listing.
_BLOCK_STATUSES = {202, 403, 429}


class RedfinBlockedError(Exception):
    """Redfin is temporarily refusing automated requests from this network."""


def _strip_redfin_prefix(text: str) -> str:
    if text.startswith("{}&&"):
        return text[4:]
    return text


def _get(url: str, **kwargs) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=15, **kwargs)
    if resp.status_code in _BLOCK_STATUSES:
        raise RedfinBlockedError(f"Redfin returned HTTP {resp.status_code}")
    resp.raise_for_status()
    return resp


def _empty_result(url: str = "") -> dict:
    return {
        "estimated_value": 0.0,
        "redfin_estimate": 0.0,
        "last_sold_price": 0.0,
        "value_source": "",
        "beds": 0,
        "baths": 0,
        "sqft": 0,
        "address": _address_from_redfin_url(url) if url else "",
        "redfin_url": url,
    }


def _to_price(value) -> float:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return 0.0
    return price if price > 0 else 0.0


def _choose_value(result: dict, listed_price: float = 0.0) -> None:
    """Value a property at the higher of the Redfin Estimate and last sold price."""
    estimate = result["redfin_estimate"]
    last_sold = result["last_sold_price"]
    if estimate or last_sold:
        if last_sold > estimate:
            result["estimated_value"] = last_sold
            result["value_source"] = "last_sold"
        else:
            result["estimated_value"] = estimate
            result["value_source"] = "estimate"
    elif listed_price:
        result["estimated_value"] = listed_price
        result["value_source"] = "list_price"


def _property_id_from_url(url: str) -> str | None:
    match = re.search(r"/home/(\d+)", url or "")
    return match.group(1) if match else None


def _address_from_redfin_url(url: str) -> str:
    """Extract a readable address from a Redfin URL path."""
    try:
        path = urlparse(url).path
        parts = path.strip("/").split("/")
        if "home" not in parts or parts.index("home") < 3:
            if len(parts) >= 3:
                street_zip = unquote(parts[-1]).replace("-", " ")
                city = unquote(parts[-2]).replace("-", " ")
                return f"{street_zip}, {city}"
            return ""
        idx = parts.index("home")
        state = unquote(parts[0])
        city = unquote(parts[idx - 2]).replace("-", " ")
        street_part = unquote(parts[idx - 1]).replace("-", " ")
        zip_match = re.search(r"(\d{5})$", street_part)
        zip_code = zip_match.group(1) if zip_match else ""
        street = street_part[: zip_match.start()].strip() if zip_match else street_part
        bits = [b for b in (street, city) if b]
        if state and zip_code:
            bits.append(f"{state} {zip_code}")
        elif state:
            bits.append(state)
        elif zip_code:
            bits.append(zip_code)
        return ", ".join(bits)
    except Exception:
        return ""


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith("http"):
        url = REDFIN_BASE + url if url.startswith("/") else "https://" + url
    return url.split("?")[0].split("#")[0].rstrip("/")


def search_redfin_address(address: str) -> dict | None:
    """Use Redfin's autocomplete to resolve an address to a property URL."""
    params = {"location": address, "v": "2", "al": "1", "num_homes": "5"}
    try:
        resp = _get(AUTOCOMPLETE_URL, params=params)
        data = json.loads(_strip_redfin_prefix(resp.text))
    except RedfinBlockedError:
        raise
    except Exception as e:
        print(f"Redfin autocomplete error: {e}", flush=True)
        return None

    sections = (data.get("payload") or {}).get("sections", [])
    for section in sections:
        for row in section.get("rows", []):
            if row.get("type") == "1" and row.get("url"):
                return {"url": REDFIN_BASE + row["url"], "name": row.get("name", address)}
    for section in sections:
        rows = section.get("rows", [])
        if rows and rows[0].get("url"):
            return {"url": REDFIN_BASE + rows[0]["url"], "name": rows[0].get("name", address)}
    return None


def _fetch_avm(property_id: str, url: str) -> dict | None:
    """Fetch Redfin Estimate, last sold price, and facts from the AVM endpoint."""
    resp = _get(AVM_URL, params={"propertyId": property_id, "accessLevel": "1"})
    try:
        payload = json.loads(_strip_redfin_prefix(resp.text)).get("payload") or {}
    except ValueError as e:
        print(f"Redfin AVM parse error for property {property_id}: {e}", flush=True)
        return None
    if not payload:
        return None

    result = _empty_result(url)
    result["redfin_estimate"] = _to_price(payload.get("predictedValue"))
    result["last_sold_price"] = _to_price(payload.get("lastSoldPrice"))
    _choose_value(result, _to_price((payload.get("priceInfo") or {}).get("amount")))

    result["beds"] = float(payload.get("numBeds") or 0)
    result["baths"] = float(payload.get("numBaths") or 0)
    sqft = payload.get("sqFt")
    if isinstance(sqft, dict):
        result["sqft"] = int(sqft.get("value") or 0)
    elif sqft:
        result["sqft"] = int(sqft)

    street = ((payload.get("streetAddress") or {}).get("assembledAddress") or "").strip()
    if street:
        url_address = _address_from_redfin_url(url)
        if url_address and "," in url_address:
            result["address"] = street + url_address[url_address.find(","):]
        else:
            result["address"] = street
    return result


def _scrape_listing_html(url: str) -> dict:
    """Fallback: read values embedded in the public listing page."""
    result = _empty_result(url)
    html = _get(url).text
    soup = BeautifulSoup(html, "lxml")

    predicted = re.search(r'"predictedValue"\s*:\s*([0-9.]+)', html)
    if predicted:
        result["redfin_estimate"] = _to_price(predicted.group(1))
    if not result["redfin_estimate"]:
        estimate_el = soup.select_one(
            ".avm .statsValue, .avmLabel + .statsValue, .RedfinEstimateValueHeader .value"
        )
        if estimate_el:
            result["redfin_estimate"] = _parse_price(estimate_el.get_text(strip=True))

    last_sold = re.search(r'"lastSoldPrice"\s*:\s*([0-9.]+)', html)
    if last_sold:
        result["last_sold_price"] = _to_price(last_sold.group(1))

    listed = 0.0
    price_el = soup.select_one(
        ".statsValue [data-rf-test-id='abp-price'] .value, .price-section .statsValue"
    )
    if price_el:
        listed = _parse_price(price_el.get_text(strip=True))
    _choose_value(result, listed)

    address_el = soup.select_one(
        "h1.street-address, .full-address, .street-address, [data-rf-test-id='abp-streetLine']"
    )
    if address_el:
        text = re.sub(r"\s+", " ", address_el.get_text(" ", strip=True))
        if text and len(text) < 200:
            result["address"] = text
    if not result["address"] and soup.find("title"):
        title = soup.find("title").get_text(strip=True)
        if " | Redfin" in title:
            result["address"] = title.replace(" | Redfin", "").strip()

    for stat in soup.select(
        ".HomeMainStats .stat-block, .home-main-stats-variant .stat-block, .HomeInfoV2 .stat-block"
    ):
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
    return result


def scrape_redfin_estimate(url: str) -> dict:
    """
    Load value, beds, baths, sqft, and address for a Redfin property URL.

    Raises RedfinBlockedError when Redfin refuses every lookup method.
    """
    url = _normalize_url(url)
    blocked = False

    property_id = _property_id_from_url(url)
    if property_id:
        try:
            avm = _fetch_avm(property_id, url)
            if avm and avm["estimated_value"]:
                return avm
        except RedfinBlockedError as e:
            print(f"Redfin AVM blocked for {url}: {e}", flush=True)
            blocked = True
        except requests.RequestException as e:
            print(f"Redfin AVM error for {url}: {e}", flush=True)

    try:
        result = _scrape_listing_html(url)
    except RedfinBlockedError:
        raise
    except requests.RequestException as e:
        print(f"Redfin scrape error for {url}: {e}", flush=True)
        if blocked:
            raise RedfinBlockedError(str(e))
        result = _empty_result(url)

    if not result.get("address"):
        result["address"] = _address_from_redfin_url(url) or "Property"
    result["redfin_url"] = url
    return result


def get_property_data(address: str) -> dict | None:
    """Full pipeline: search for address, then scrape the property page."""
    search_result = search_redfin_address(address)
    if not search_result:
        return None

    url = search_result["url"]
    details = scrape_redfin_estimate(url)
    details["redfin_url"] = url
    if search_result.get("name"):
        details["address"] = search_result["name"]
    return details


def get_property_data_from_url(url: str) -> dict | None:
    """Fetch property data directly from a Redfin URL."""
    url = _normalize_url(url)
    if not url or "redfin.com" not in url:
        return None
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
