#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import urllib.request
from pathlib import Path
from typing import List, Dict

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
        return explicit

    token = os.getenv("BRIGHTDATA_API_TOKEN")
    if not token:
        return None

    proxy_host = os.getenv("BRIGHTDATA_PROXY_HOST", "zproxy.lum-superproxy.io")
    proxy_port = os.getenv("BRIGHTDATA_PROXY_PORT", "22225")
    username = os.getenv("BRIGHTDATA_USERNAME", "brd-customer-hl_xxxxx-zone-unblocker")
    return f"http://{username}:{token}@{proxy_host}:{proxy_port}"


def fetch_page(url: str, demo: bool = False) -> str:
    if demo:
        fixture_path = Path("fixtures") / "sample_finanzen.html"
        return fixture_path.read_text(encoding="utf-8")

    proxy_url = build_proxy_url()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    if proxy_url:
        proxy_handler = urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
        opener = urllib.request.build_opener(proxy_handler)
        request = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="ignore")
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Bright Data proxy authentication failed. Update BRIGHTDATA_PROXY_URL or the token in .env."
            ) from exc

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "The request to finanzen.net failed. If you want to use Bright Data, set BRIGHTDATA_PROXY_URL correctly."
        ) from exc


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
