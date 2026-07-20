#!/usr/bin/env python3
"""
Helper utility to extract numeric Pinterest Board ID from a Pinterest Board URL or shortlink.

Usage:
  python jobs/pinterest-publisher/get_board_id.py "https://ca.pinterest.com/olivierstamand1/free-printable-coloring-pages-for-kids/"
  python jobs/pinterest-publisher/get_board_id.py "https://pin.it/2naGyd3dF"
"""

import sys
import re
import requests


def extract_board_id(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print(f"🔍 Resolving URL: {url} ...")
    res = requests.get(url, headers=headers, allow_redirects=True, timeout=15)
    final_url = res.url
    print(f"📍 Final URL: {final_url}")

    # Search for board resource ID patterns in HTML source
    board_match = re.findall(r'"BoardResource"[^}]*?"id":\s*"(\d+)"', res.text)
    if not board_match:
        board_match = re.findall(r'"board_id":\s*"(\d+)"', res.text)

    all_ids = list(dict.fromkeys(re.findall(r'"id":\s*"(\d{15,20})"', res.text)))

    if board_match:
        board_id = board_match[0]
        print(f"\n🎉 Extracted Pinterest Board ID: '{board_id}'")
        print(f"👉 Set in .env: PINTEREST_BOARD_ID='{board_id}'")
        return board_id
    elif all_ids:
        print(f"\n✨ Extracted Candidate IDs: {all_ids}")
        board_id = all_ids[1] if len(all_ids) > 1 else all_ids[0]
        print(f"👉 Recommended PINTEREST_BOARD_ID='{board_id}'")
        return board_id
    else:
        print("❌ Could not extract numeric Board ID from page source.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python jobs/pinterest-publisher/get_board_id.py <PINTEREST_BOARD_URL_OR_PIN_IT>")
        sys.exit(1)

    target_url = sys.argv[1]
    extract_board_id(target_url)
