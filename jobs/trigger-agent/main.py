import os
import json
import uuid
import logging
import requests
import functions_framework
import google.auth
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment Variables
AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT")
APP_NAME = os.environ.get("APP_NAME", "color_it_daily_agent")
USER_ID = os.environ.get("USER_ID", "daily-job")

def get_id_token(audience):
    """
    Obtains an OIDC ID token for the specified audience.
    """
    try:
        # For local testing with gcloud, or running in Cloud Run
        auth_req = GoogleRequest()
        token = id_token.fetch_id_token(auth_req, audience)
        return token
    except Exception as e:
        logger.warning(f"Standard auth failed ({e}). Trying local gcloud fallback...")
        try:
            # Fallback for local development if 'gcloud' is installed (matches call-agent.py behavior)
            import subprocess
            # Note: For user credentials, audience is often skipped or handled differently by gcloud.
            # We try the simple print-identity-token which worked for you previously.
            token = subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"], 
                text=True
            ).strip()
            return token
        except Exception as local_e:
            logger.error(f"Failed to get ID token via fallback: {local_e}")
            raise e

@functions_framework.http
def trigger_agent(request):
    """
    Cloud Run Function triggered via HTTP (e.g., Cloud Scheduler).
    Calls the Color It Daily Agent to generate a new image for today.
    """
    if not AGENT_ENDPOINT:
        logger.error("AGENT_ENDPOINT environment variable is not set.")
        return "Internal Server Error: Missing Configuration", 500

    try:
        # 1. Authenticate
        # We need an ID token to call the secured Agent Cloud Run service
        token = get_id_token(AGENT_ENDPOINT)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # 2. Create Session
        session_id = str(uuid.uuid4())
        session_url = f"{AGENT_ENDPOINT}/apps/{APP_NAME}/users/{USER_ID}/sessions/{session_id}"
        
        logger.info(f"Creating session at {session_url}...")
        resp_session = requests.post(session_url, headers=headers)
        resp_session.raise_for_status()
        logger.info(f"Session created: {session_id}")

        # 3. Prepare Payload
        now = datetime.now()
        current_date_str = now.strftime("%Y-%m-%d")
        
        user_request = {
            "current_date": current_date_str,
        }

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

        # 4. Run Agent
        run_url = f"{AGENT_ENDPOINT}/run"
        logger.info(f"Triggering agent at {run_url} for date {current_date_str}...")
        
        resp_run = requests.post(run_url, headers=headers, json=payload)
        resp_run.raise_for_status()
        
        result = resp_run.json()
        logger.info("Agent run completed successfully.")
        
        return {
            "status": "success",
            "date": current_date_str,
            "session_id": session_id,
            "agent_response": "Triggered successfully" 
        }, 200

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error calling agent: {e.response.status_code} - {e.response.text}")
        return f"Agent Call Failed: {e}", 502
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Error: {e}", 500
