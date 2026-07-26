import os
import json
import logging
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from google.adk.cli.fast_api import get_fast_api_app

from color_it_daily_agent.pipeline import prepare_agent_execution
from color_it_daily_agent.lib.persistence import mark_document_failed

logger = logging.getLogger("color_it_daily_agent")

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_SERVICE_URI = "sqlite+aiosqlite:///./sessions.db"
ALLOWED_ORIGINS = ["*"]
SERVE_WEB_INTERFACE = True

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)


@app.middleware("http")
async def process_agent_input_middleware(request: Request, call_next):
    ctx = None
    if request.method == "POST" and request.url.path.endswith("/run"):
        body_bytes = await request.body()
        if body_bytes:
            try:
                body_json = json.loads(body_bytes.decode("utf-8"))
                input_payload = {}
                is_adk = False

                if isinstance(body_json, dict) and "new_message" in body_json:
                    is_adk = True
                    parts = body_json.get("new_message", {}).get("parts", [])
                    if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                        try:
                            input_payload = json.loads(parts[0]["text"])
                        except Exception:
                            input_payload = {"current_date": parts[0]["text"]}
                else:
                    input_payload = body_json if isinstance(body_json, dict) else {}

                ctx, merged_payload = prepare_agent_execution(input_payload)

                if is_adk:
                    body_json["new_message"]["parts"][0]["text"] = json.dumps(merged_payload)
                    new_body_bytes = json.dumps(body_json).encode("utf-8")
                else:
                    new_body_bytes = json.dumps(merged_payload).encode("utf-8")

                async def receive():
                    return {"type": "http.request", "body": new_body_bytes}

                request = Request(request.scope, receive=receive)
            except HTTPException as http_ex:
                return JSONResponse(
                    status_code=http_ex.status_code,
                    content={"detail": http_ex.detail},
                )
            except Exception as ex:
                logger.error(f"Error processing agent input in middleware: {ex}")

    try:
        response = await call_next(request)
        if response.status_code >= 400 and ctx:
            mark_document_failed(ctx.document_id, f"Execution failed with HTTP status {response.status_code}", ctx.no_persist)
        return response
    except Exception as exc:
        if ctx:
            mark_document_failed(ctx.document_id, str(exc), ctx.no_persist)
        raise exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
