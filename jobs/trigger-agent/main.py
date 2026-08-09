import os
import json
import uuid
import logging
import requests
import functions_framework
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from datetime import datetime

try:
    from google.cloud import firestore
except ImportError:
    firestore = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT")
APP_NAME = os.environ.get("APP_NAME", "color_it_daily_agent")
USER_ID = os.environ.get("USER_ID", "daily-job")


def get_id_token(audience: str) -> str:
    """
    Obtains an OIDC ID token for the specified audience.
    """
    auth_req = GoogleRequest()
    return id_token.fetch_id_token(auth_req, audience)


def gcs_to_public_url(path: str) -> str:
    """
    Converts a gs:// bucket path into a public https://storage.googleapis.com/ URL.
    """
    if path and isinstance(path, str) and path.startswith("gs://"):
        return path.replace("gs://", "https://storage.googleapis.com/", 1)
    return path


def fetch_document_data(document_id: str, is_user: bool = False) -> dict:
    """
    Fetches generated document metadata from Firestore.
    """
    if not firestore:
        return {}
    try:
        db = firestore.Client()
        collection_base = os.environ.get("COLORING_PAGE_COLLECTION", "coloring_pages")
        target_col = f"{collection_base}_user" if is_user else collection_base
        doc_ref = db.collection(target_col).document(document_id).get()
        if doc_ref.exists:
            return doc_ref.to_dict() or {}
    except Exception as e:
        logger.warning(f"Could not fetch document '{document_id}' from Firestore: {e}")
    return {}


@functions_framework.http
def trigger_agent(request):
    """
    Cloud Run Function triggered via HTTP (e.g., Cloud Scheduler).
    Calls the Color It Daily Agent to generate a new image for today.
    """
    if not AGENT_ENDPOINT:
        logger.error("AGENT_ENDPOINT environment variable is not set.")
        return "Internal Server Error: Missing Configuration", 500

    # Extract dynamic payload if triggered with JSON (e.g., from Cloud Scheduler)
    # Fallback to Environment Variables if not provided in the request
    req_data = request.get_json(silent=True) or {}
    collection_name = req_data.get("collection") or req_data.get("collection_name") or os.environ.get("COLLECTION_NAME")
    target_keyword = req_data.get("keyword") or req_data.get("target_keyword") or os.environ.get("TARGET_KEYWORD")
    target_audience = req_data.get("audience") or req_data.get("target_audience") or os.environ.get("TARGET_AUDIENCE")
    micro_style = req_data.get("micro_style") or req_data.get("selected_style") or os.environ.get("MICRO_STYLE")
    
    if "no_persist" in req_data:
        no_persist = bool(req_data["no_persist"])
    else:
        no_persist = os.environ.get("NO_PERSIST", "").lower() in ("true", "1", "yes")

    if "user" in req_data:
        is_user = bool(req_data["user"])
    elif "is_user" in req_data:
        is_user = bool(req_data["is_user"])
    else:
        is_user = os.environ.get("IS_USER", "").lower() in ("true", "1", "yes")

    if "test_mode" in req_data:
        test_mode = bool(req_data["test_mode"])
    elif "test" in req_data:
        test_mode = bool(req_data["test"])
    else:
        test_mode = os.environ.get("TEST_MODE", "").lower() in ("true", "1", "yes")

    document_id = req_data.get("document_id") or str(uuid.uuid4())

    try:
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
            "document_id": document_id,
        }
        
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
        if is_user:
            user_request["user"] = True
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

        # 4. Run Agent
        run_url = f"{AGENT_ENDPOINT}/run"
        logger.info(f"Triggering agent at {run_url} for date {current_date_str} (doc_id={document_id})")
        logger.info(f"Payload: {json.dumps(user_request)}")
        
        resp_run = requests.post(run_url, headers=headers, json=payload)
        resp_run.raise_for_status()
        logger.info("Agent run completed successfully.")
        
        # 5. Fetch Generated Document Details
        doc_data = fetch_document_data(document_id, is_user=is_user)
        
        opt_path = doc_data.get("optimized_image_path")
        public_img_url = gcs_to_public_url(opt_path)

        generation_info = None
        if doc_data:
            generation_info = {
                "document_id": document_id,
                "title": doc_data.get("title"),
                "description": doc_data.get("description"),
                "visual_tags": doc_data.get("visual_tags"),
                "mood": doc_data.get("mood"),
                "target_audience": doc_data.get("target_audience"),
                "micro_style": doc_data.get("micro_style"),
                "optimized_image_path": public_img_url,
                "status": doc_data.get("status"),
                "feedback": doc_data.get("feedback"),
            }

        title_str = doc_data.get("title") if doc_data else None
        agent_msg = f"Successfully generated coloring page '{title_str}'." if title_str else "Coloring page generation finished successfully."

        return {
            "status": doc_data.get("status", "success") if doc_data else "success",
            "date": current_date_str,
            "session_id": session_id,
            "document_id": document_id,
            "generation": generation_info,
            "agent_response": agent_msg,
            "parameters_used": user_request
        }, 200

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        error_text = e.response.text if e.response is not None else str(e)
        logger.error(f"HTTP Error calling agent ({status_code}): {error_text}")
        
        is_429 = status_code == 429 or "429" in error_text or "RESOURCE_EXHAUSTED" in error_text
        err_msg = "Rate limit / quota exceeded. Please try again in a few minutes." if is_429 else f"Agent execution failed with HTTP status {status_code}."
        
        return {
            "status": "failed",
            "date": current_date_str if 'current_date_str' in locals() else None,
            "session_id": session_id if 'session_id' in locals() else None,
            "document_id": document_id if 'document_id' in locals() else None,
            "error_code": "RESOURCE_EXHAUSTED" if is_429 else "AGENT_HTTP_ERROR",
            "agent_response": err_msg,
            "detail": error_text,
            "parameters_used": user_request if 'user_request' in locals() else {}
        }, (429 if is_429 else status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "status": "failed",
            "error_code": "INTERNAL_ERROR",
            "agent_response": f"Unexpected error: {e}",
        }, 500