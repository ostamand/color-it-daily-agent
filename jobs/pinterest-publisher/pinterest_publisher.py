import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """
    Generates a clean URL slug matching website route conventions.
    """
    if not text:
        return ""
    s = text.lower().replace("'s", "").replace("'", "")
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def select_pinterest_board(visual_tags: list, title: str) -> str:
    """
    Selects target Pinterest Board ID based on visual tags and title keywords.
    Falls back to PINTEREST_BOARD_ID if no match is found.
    """
    board_map_raw = os.environ.get("PINTEREST_BOARD_MAP", "{}")
    fallback_board = os.environ.get("PINTEREST_BOARD_ID", "")
    try:
        board_map = json.loads(board_map_raw)
    except Exception:
        board_map = {}

    if not board_map:
        return fallback_board

    search_tokens = [t.lower() for t in visual_tags] + title.lower().split()

    for keyword, target_board_id in board_map.items():
        kw_lower = keyword.lower()
        if any(kw_lower in token for token in search_tokens) and target_board_id:
            logger.info(f"Routed Pin to specific board '{target_board_id}' based on keyword '{keyword}'")
            return target_board_id

    return fallback_board


_genai_client = None

def get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        use_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "true").lower() in ("true", "1", "yes")
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "coloring-pages-476315")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
        if use_vertex:
            _genai_client = genai.Client(vertexai=True, project=project, location=location)
        else:
            _genai_client = genai.Client()
    return _genai_client


def generate_pinterest_metadata(
    title: str,
    description: str,
    visual_tags: list,
    reasoning: Optional[str] = None
) -> Dict[str, str]:
    """
    Generates SEO-optimized Pinterest Pin metadata using Gemini 3.5 Flash.
    Strictly caps total length to fit Pinterest's 500-character limit.
    """
    client = get_genai_client()
    model_name = os.environ.get("PINTEREST_GEMINI_MODEL", "gemini-3.5-flash")
    tags_str = ", ".join(visual_tags) if visual_tags else "coloring page, kids activities"

    system_instruction = (
        "You are an expert Social Media & Pinterest Growth Strategist specializing in kids' educational content, free printables, and coloring pages.\n"
        "Brand Identity: Color It Daily (coloritdaily.com).\n"
        "Value Proposition: 100% Free high-res printables, no ads, no sign-ups, no watermarks, bold clean lines, optimized for 8.5x11 printing.\n\n"
        "Format your output as JSON with keys: title, description, hashtags.\n"
        "- title: Max 80 characters.\n"
        "- description: Warm 2-sentence description (max 220 characters) emphasizing fine motor skills, quiet time, and 100% free download.\n"
        "- hashtags: 5-8 high-traffic Pinterest hashtags separated by spaces.\n"
        "CRITICAL: The entire combined text (title + description + hashtags) MUST NOT exceed 450 characters."
    )

    user_prompt = f"""Input Details:
- Original Title: {title}
- Visual Description: {description}
- Visual Tags: {tags_str}
- Context/Reasoning: {reasoning or 'N/A'}

Generate viral, SEO-friendly Pinterest Pin metadata matching the brand standards."""

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
                response_mime_type="application/json",
            )
        )
        data = json.loads(response.text)
        return {
            "title": data.get("title", f"Free Printable: {title} Coloring Page")[:80],
            "description": data.get("description", f"Download this free high-quality {title} coloring page! Perfect for kids and classrooms.")[:220],
            "hashtags": data.get("hashtags", "#coloritdaily #freeprintable #kidsactivities #coloringpages")
        }
    except Exception as e:
        logger.error(f"Error generating Pinterest metadata via Gemini ({e}). Using fallback template.")
        return {
            "title": f"Free Printable: {title} Coloring Page"[:80],
            "description": f"Download this free high-quality {title} coloring page! Perfect for kids, parents, and classrooms."[:220],
            "hashtags": "#coloritdaily #freeprintable #kidsactivities #coloringpages"
        }


def post_pin_to_pinterest(
    title: str,
    description: str,
    hashtags: str,
    image_url: str,
    destination_url: str,
    board_id: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Posts a pin via Buffer GraphQL API or Webhook.
    Caps total post text at 490 characters to respect Pinterest's strict 500-char limit.
    """
    board = board_id or os.environ.get("PINTEREST_BOARD_ID", "")
    buffer_token = os.environ.get("BUFFER_ACCESS_TOKEN", "")
    buffer_profile = os.environ.get("BUFFER_PROFILE_ID", "")
    webhook_url = os.environ.get("PINTEREST_WEBHOOK_URL", "")

    # Combine title, description, and hashtags cleanly
    full_text = f"{title}\n\n{description}\n\n{hashtags}".strip()
    if len(full_text) > 490:
        max_desc_len = 490 - len(title) - len(hashtags) - 8
        if max_desc_len > 30:
            short_desc = description[:max_desc_len - 3] + "..."
            full_text = f"{title}\n\n{short_desc}\n\n{hashtags}".strip()
        full_text = full_text[:490]

    if dry_run:
        logger.info("[PINTEREST DRY-RUN] Simulating Pin creation:")
        logger.info(f"  Title: {title}")
        logger.info(f"  Full Text (Length {len(full_text)}): {full_text}")
        logger.info(f"  Board ID: {board}")
        logger.info(f"  Image URL: {image_url}")
        logger.info(f"  Link: {destination_url}")
        return {
            "status": "dry_run",
            "pin_id": "dry-run-pin-id",
            "message": "Simulated pin creation successfully."
        }

    # Buffer GraphQL API (Official API at https://api.buffer.com)
    if buffer_token and buffer_profile:
        logger.info("Posting Pin via Buffer GraphQL API...")
        buffer_url = "https://api.buffer.com"
        headers = {
            "Authorization": f"Bearer {buffer_token}",
            "Content-Type": "application/json"
        }
        query = """
        mutation CreatePost($input: CreatePostInput!) {
          createPost(input: $input) {
            __typename
            ... on PostActionSuccess {
              post {
                id
                status
              }
            }
            ... on NotFoundError { message }
            ... on UnauthorizedError { message }
            ... on UnexpectedError { message }
            ... on RestProxyError { message }
            ... on LimitReachedError { message }
            ... on InvalidInputError { message }
          }
        }
        """
        variables = {
            "input": {
                "channelId": buffer_profile,
                "schedulingType": "automatic",
                "mode": "shareNow",
                "text": full_text,
                "assets": [
                    {
                        "image": {
                            "url": image_url
                        }
                    }
                ],
                "metadata": {
                    "pinterest": {
                        "title": title[:100],
                        "url": destination_url,
                        "boardServiceId": board
                    }
                }
            }
        }
        try:
            res = requests.post(buffer_url, headers=headers, json={"query": query, "variables": variables}, timeout=15)
            res.raise_for_status()
            res_json = res.json()
            
            create_res = res_json.get("data", {}).get("createPost", {})
            typename = create_res.get("__typename", "")

            if typename != "PostActionSuccess":
                err_msg = create_res.get("message", "Unknown Buffer GraphQL Error")
                logger.error(f"Buffer GraphQL API Error ({typename}): {err_msg}")
                raise Exception(f"Buffer GraphQL Error ({typename}): {err_msg}")

            post_id = create_res.get("post", {}).get("id", "buffer-success")
            logger.info(f"Successfully posted Pin via Buffer GraphQL API (Post ID: {post_id}).")
            return {
                "status": "success_buffer",
                "pin_id": post_id,
                "response": res_json
            }
        except Exception as e:
            logger.error(f"Buffer API Error: {e}")
            raise e

    # Make.com / Webhook Integration (Optional Backup)
    if webhook_url:
        logger.info(f"Posting Pin via Webhook ({webhook_url})...")
        payload = {
            "title": title[:100],
            "description": full_text,
            "image_url": image_url,
            "link": destination_url,
            "board_id": board
        }
        try:
            res = requests.post(webhook_url, json=payload, timeout=15)
            res.raise_for_status()
            logger.info("Successfully posted Pin payload to Webhook.")
            return {
                "status": "success_webhook",
                "pin_id": f"webhook-{res.status_code}",
                "response": res.text
            }
        except Exception as e:
            logger.error(f"Webhook Error: {e}")
            raise e

    logger.warning("Neither BUFFER_ACCESS_TOKEN/BUFFER_PROFILE_ID nor PINTEREST_WEBHOOK_URL is set in environment.")
    return {
        "status": "dry_run_unconfigured",
        "pin_id": "unconfigured-pin-id",
        "message": "Buffer API credentials or Webhook URL not set. Simulated pin creation."
    }


def publish_to_pinterest_safely(doc_id: str, doc_data: dict, dry_run: bool = False) -> dict:
    """
    Safe wrapper to handle Pinterest posting for a coloring page document.
    """
    enabled = os.environ.get("PINTEREST_ENABLED", "true").lower() in ("true", "1", "yes")
    if not enabled:
        logger.info("Pinterest publishing disabled via PINTEREST_ENABLED=false.")
        return {"status": "disabled", "message": "Pinterest publishing disabled."}

    title = doc_data.get("title", "")
    description = doc_data.get("description", "")
    visual_tags = doc_data.get("visual_tags", [])
    reasoning = doc_data.get("reasoning", "")
    optimized_image_path = doc_data.get("optimized_image_path", "")
    bucket_name = os.environ.get("GCP_MEDIA_BUCKET", "color-it-daily-agent-assets")
    base_website_url = os.environ.get("WEBSITE_BASE_URL", "https://coloritdaily.com")

    if optimized_image_path.startswith("gs://"):
        relative_path = optimized_image_path.replace(f"gs://{bucket_name}/", "")
        public_image_url = f"https://storage.googleapis.com/{bucket_name}/{relative_path}"
    else:
        public_image_url = f"https://storage.googleapis.com/{bucket_name}/optimized/{doc_id}.webp"

    # Resolve exact page slug (unique_name) on coloritdaily.com
    unique_name = doc_data.get("unique_name") or slugify(title)
    destination_url = f"{base_website_url}/pages/{unique_name}"

    # Step 1: Generate Metadata via Gemini 3.5 Flash
    metadata = generate_pinterest_metadata(title, description, visual_tags, reasoning)

    # Step 2: Select Board ID
    board_id = select_pinterest_board(visual_tags, title)

    # Step 3: Post Pin via Buffer API
    result = post_pin_to_pinterest(
        title=metadata["title"],
        description=metadata["description"],
        hashtags=metadata["hashtags"],
        image_url=public_image_url,
        destination_url=destination_url,
        board_id=board_id,
        dry_run=dry_run
    )

    result["metadata"] = metadata
    result["board_id"] = board_id
    result["image_url"] = public_image_url
    result["destination_url"] = destination_url
    return result
