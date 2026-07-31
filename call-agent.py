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

2. Run against a specific collection with target keyword targeting:
   python call-agent.py --endpoint http://localhost:8080 --collection "Wonder Daily" --keyword "dinosaur colouring pages"

3. Run in local-only no-persistence mode (saves assets locally to ./tmp/color_it_daily/):
   python call-agent.py --endpoint http://localhost:8080 --collection "Wonder Daily" --no-persist

4. Run against deployed GCP Cloud Run service:
   python call-agent.py --endpoint https://color-it-daily-agent-uc.a.run.app --collection "Wonder Daily"

Arguments:
----------
  --endpoint        (Required) The base URL of the FastAPI agent server.
  --collection      (Optional) The target collection name (e.g. 'Wonder Daily', 'Halloween').
  --keyword / -k    (Optional) Target SEO keyword phrase (e.g. 'dinosaur colouring pages').
  --no-persist      (Optional) Disable Firestore & GCS writes; save all assets and document.json locally.
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


def main(endpoint: str, collection_name: str = None, target_keyword: str = None, no_persist: bool = False):
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

    # run the agent
    from datetime import datetime
    now = datetime.now()
    current_date_str = now.strftime("%Y-%m-%d")

    user_request = {
        "current_date": current_date_str,
    }
    if collection_name:
        user_request["collection_name"] = collection_name
    if target_keyword:
        user_request["target_keyword"] = target_keyword
    if no_persist:
        user_request["no_persist"] = True

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
    response.raise_for_status()

    print("Assets generated successfully.")
    print("Response:", response.json())


if __name__ == "__main__":
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Trigger Color It Daily Agent runs")
    parser.add_argument("--endpoint", type=str, required=True, help="Base URL of the agent service")
    parser.add_argument("--collection", type=str, default=None, help="Target collection name")
    parser.add_argument("--keyword", "-k", type=str, default=None, help="Target SEO keyword phrase (e.g. 'dinosaur colouring pages')")
    parser.add_argument("--no-persist", action="store_true", help="Disable persistence and save assets locally")
    args = parser.parse_args()
    
    main(args.endpoint, collection_name=args.collection, target_keyword=args.keyword, no_persist=args.no_persist)