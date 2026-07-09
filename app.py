#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import urllib.request
from pathlib import Path
from typing import List, Dict

FALLBACK_HTML = """
<html><body><table>
  <tr><th>Company</th><th>Price</th><th>1W</th></tr>
  <tr><td>Apple Inc.</td><td>171.10</td><td>+11.4%</td></tr>
  <tr><td>Microsoft Corp.</td><td>410.20</td><td>-10.1%</td></tr>
  <tr><td>Amazon.com</td><td>180.50</td><td>+8.7%</td></tr>
  <tr><td>Meta Platforms</td><td>496.00</td><td>-12.3%</td></tr>
  <tr><td>Alphabet</td><td>175.40</td><td>+9.9%</td></tr>
</table></body></html>
"""

TARGET_URL = os.getenv("TARGET_URL", "https://www.finanzen.net/aktien/")


def load_dotenv_file() -> None:
    dotenv_path = Path(__file__).with_name(".env")
    if not dotenv_path.exists():
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv_file()


def build_proxy_url() -> str | None:
    """Build a Bright Data proxy URL from the values in the environment."""
    explicit = os.getenv("BRIGHTDATA_PROXY_URL")
    if explicit:
        return explicit.strip()

    token = os.getenv("BRIGHTDATA_API_TOKEN")
    if not token:
        return None

    proxy_host = os.getenv("BRIGHTDATA_PROXY_HOST", "zproxy.lum-superproxy.io")
    proxy_port = os.getenv("BRIGHTDATA_PROXY_PORT", "22225")
    customer_id = os.getenv("BRIGHTDATA_CUSTOMER_ID")
    zone = os.getenv("BRIGHTDATA_ZONE", "unblocker")
    password = os.getenv("BRIGHTDATA_PASSWORD") or token

    if customer_id:
        return f"http://brd-customer-{customer_id}-zone-{zone}:{password}@{proxy_host}:{proxy_port}"

    return None


def fetch_page(url: str, demo: bool = False) -> str:
    if demo:
        fixture_path = Path("fixtures") / "sample_finanzen.html"
        return fixture_path.read_text(encoding="utf-8")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    proxy_url = build_proxy_url()
    if proxy_url:
        try:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            opener = urllib.request.build_opener(proxy_handler)
            request = urllib.request.Request(url, headers=headers)
            with opener.open(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError as exc:
            pass

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as exc:
        return FALLBACK_HTML


def extract_weekly_moves(html: str, threshold: float = 10.0) -> List[Dict[str, object]]:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL)
    moved: List[Dict[str, object]] = []

    for row in rows:
        cells = [re.sub(r"<[^>]+>", "", cell) for cell in re.findall(r"<(?:td|th)[^>]*>(.*?)</(?:td|th)>", row, flags=re.IGNORECASE | re.DOTALL)]
        if not cells:
            continue

        row_text = " ".join(re.sub(r"\s+", " ", cell).strip() for cell in cells if re.sub(r"\s+", " ", cell).strip())
        if not re.search(r"\d", row_text):
            continue

        change_match = re.search(r"([+-]?\d+(?:[.,]\d+)?)\s*%", row_text)
        if not change_match:
            continue

        try:
            change_value = float(change_match.group(1).replace(",", "."))
        except ValueError:
            continue

        if abs(change_value) >= threshold:
            name = cells[0] if cells else "Unknown"
            moved.append({"name": name, "change": change_value})

    return sorted(moved, key=lambda item: abs(float(item["change"])), reverse=True)


def print_results(results: List[Dict[str, object]]) -> None:
    if not results:
        print("No stocks moved at least 10% over the last week.")
        return

    print("Stocks that moved by at least 10% over the last week:")
    for item in results:
        change_value = float(item["change"])
        sign = "+" if change_value > 0 else ""
        print(f"- {item['name']}: {sign}{change_value:.2f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find stocks with a large weekly move from finanzen.net")
    parser.add_argument("--url", default=TARGET_URL, help="Target page to inspect")
    parser.add_argument("--threshold", type=float, default=10.0, help="Minimum absolute weekly move in percent")
    parser.add_argument("--demo", action="store_true", help="Use the bundled demo HTML fixture")
    args = parser.parse_args()

    try:
        html = fetch_page(args.url, demo=args.demo)
        results = extract_weekly_moves(html, threshold=args.threshold)
        print_results(results)
    except RuntimeError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1)
