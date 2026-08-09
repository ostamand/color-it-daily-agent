"""
==============================================================================
Color It Daily Agent - Test Client Execution Script
==============================================================================

This utility script connects to the Color It Daily ADK FastAPI agent service,
creates an active session, and triggers a run request.

Usage Examples:
---------------
1. Run locally against default collection ('Wonder Daily'):
   python call-agent.py --endpoint http://localhost:8080

2. Run against a specific collection with target keyword and target audience:
   python call-agent.py --endpoint http://localhost:8080 --collection "Wonder Daily" --audience "tweens_teens"

3. Run as user/organization-initiated request (saves to {COLLECTION}_user, user=true in Postgres):
   python call-agent.py --endpoint http://localhost:8080 --org-id 1 --org-name "Color It Daily Users" --user-email "test@coloritdaily.com"

Arguments:
----------
  --endpoint        (Required) The base URL of the FastAPI agent server.
  --collection      (Optional) The target collection name.
  --audience / -a   (Optional) Target audience tier ('toddler', 'kids_3_10', 'tweens_teens', 'young_adults', 'adults').
  --keyword / -k    (Optional) Target SEO keyword phrase (e.g. 'dinosaur colouring pages').
  --micro-style / -s(Optional) Target micro-style name, slug, or ID (e.g. 'the-bold-sticker-hero-subject').
  --no-persist      (Optional) Disable Firestore & GCS writes; save all assets and document.json locally.
  --user-email      (Optional) User email address for user-initiated request.
  --org-id          (Optional) Organization ID (non-zero routes to coloring_pages_user and sets user=true in Postgres).
  --org-name        (Optional) Organization name.
  --test-mode / --test (Optional) Enable test mode to bypass Vertex AI generation using cached test output.
==============================================================================
"""

import argparse
import os
import requests
import subprocess
import uuid
import json

from dotenv import load_dotenv

USER_ID = "admin"
APP_NAME = "color_it_daily_agent"


def get_cloud_token():
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-identity-token"], text=True
        ).strip()
        return token
    except Exception as ex:
        print(ex)
        return None


def main(
    endpoint: str,
    collection_name: str = None,
    target_audience: str = None,
    target_keyword: str = None,
    micro_style: str = None,
    no_persist: bool = False,
    user_email: str = None,
    user_id: int = None,
    test_mode: bool = False,
):
    token = get_cloud_token()

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # list available apps
    response = requests.get(f"{endpoint}/list-apps", headers=headers)
    response.raise_for_status()
    print("Apps:", response.json())

    # create a session
    session_id = str(uuid.uuid4())
    response = requests.post(
        f"{endpoint}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}",
        headers=headers,
    )
    response.raise_for_status()
    print("Session:", response.json())

    from datetime import datetime

    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    user_request = {
        "current_date": current_date_str,
    }
    if user_id is not None:
        user_request["user_id"] = user_id
    if user_email:
        user_request["user_email"] = user_email
    if collection_name:
        user_request["collection_name"] = collection_name
    if target_audience:
        user_request["target_audience"] = target_audience
    if target_keyword:
        user_request["target_keyword"] = target_keyword
    if micro_style:
        user_request["micro_style"] = micro_style
    if no_persist:
        user_request["no_persist"] = True
    if test_mode:
        user_request["test_mode"] = True

    payload = {
        "app_name": APP_NAME,
        "user_id": USER_ID,
        "session_id": session_id,
        "new_message": {
            "role": "user",
            "parts": [{"text": json.dumps(user_request)}],
        },
        "streaming": False,
    }

    print(f"Sending payload to {endpoint}/run: {json.dumps(user_request, indent=2)}")
    response = requests.post(f"{endpoint}/run", headers=headers, json=payload)
    if response.status_code >= 400:
        print(f"ERROR ({response.status_code}): {response.text}")
    response.raise_for_status()

    print("Assets generated successfully.")
    print("Response:", response.json())


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Trigger Color It Daily Agent runs")
    parser.add_argument(
        "--endpoint", type=str, required=True, help="Base URL of the agent service"
    )
    parser.add_argument("--collection", type=str, default=None, help="Target collection name")
    parser.add_argument(
        "--audience",
        "-a",
        type=str,
        default=None,
        choices=["toddler", "kids_3_10", "tweens_teens", "young_adults", "adults"],
        help="Target audience tier ('toddler', 'kids_3_10', 'tweens_teens', 'young_adults', 'adults')",
    )
    parser.add_argument(
        "--keyword",
        "-k",
        type=str,
        default=None,
        help="Target SEO keyword phrase (e.g. 'dinosaur colouring pages')",
    )
    parser.add_argument(
        "--micro-style",
        "-s",
        type=str,
        default=None,
        help="Target micro-style name, slug, or ID (e.g. 'the-bold-sticker-hero-subject')",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Disable persistence and save assets locally",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=None,
        help="User ID for the request (references organization_users.id)",
    )
    parser.add_argument(
        "--user-email",
        type=str,
        default=None,
        help="User email address for the request (optional if user-id is provided)",
    )
    parser.add_argument(
        "--test-mode",
        "--test",
        action="store_true",
        help="Enable test mode to bypass generation and return a previously generated coloring page document",
    )
    args = parser.parse_args()

    main(
        args.endpoint,
        collection_name=args.collection,
        target_audience=args.audience,
        target_keyword=args.keyword,
        micro_style=args.micro_style,
        no_persist=args.no_persist,
        user_email=args.user_email,
        user_id=args.user_id,
        test_mode=args.test_mode,
    )