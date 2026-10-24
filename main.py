import os
import json
import logging
import asyncio
from typing import Dict, Tuple, List, Optional
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from google.adk.cli.fast_api import get_fast_api_app

from color_it_daily_agent.pipeline import prepare_agent_execution
from color_it_daily_agent.lib.persistence import mark_document_failed, get_document_status
from color_it_daily_agent.lib.retry_utils import is_429_error

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
    extra_plugins=["color_it_daily_agent.lib.trace_plugin.PromptTracePlugin"],
    auto_create_session=True,
)

# In-flight run single-flight tracking
_in_flight_lock = asyncio.Lock()
# Maps track key ("session:<session_id>" or "doc:<document_id>") to asyncio.Future
# which resolves to a tuple of (status_code, headers_dict, body_bytes, media_type).
_in_flight_runs: Dict[str, asyncio.Future] = {}


@app.middleware("http")
async def process_agent_input_middleware(request: Request, call_next):
    if not (request.method == "POST" and request.url.path.endswith("/run")):
        return await call_next(request)

    body_bytes = await request.body()
    body_json = {}
    input_payload = {}
    is_adk = False
    session_id = None
    document_id = None

    if body_bytes:
        try:
            body_json = json.loads(body_bytes.decode("utf-8"))
            if isinstance(body_json, dict) and "new_message" in body_json:
                is_adk = True
                session_id = body_json.get("session_id")
                parts = body_json.get("new_message", {}).get("parts", [])
                if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                    try:
                        input_payload = json.loads(parts[0]["text"])
                    except Exception:
                        input_payload = {"current_date": parts[0]["text"]}
                    if isinstance(input_payload, dict):
                        document_id = input_payload.get("document_id")
            elif isinstance(body_json, dict):
                input_payload = body_json
                session_id = body_json.get("session_id")
                document_id = body_json.get("document_id")
        except Exception as ex:
            logger.error(f"Error parsing agent input in middleware: {ex}")

    keys_to_track: List[str] = []
    if session_id:
        keys_to_track.append(f"session:{session_id}")
    if document_id:
        keys_to_track.append(f"doc:{document_id}")

    existing_fut: Optional[asyncio.Future] = None
    fut: Optional[asyncio.Future] = None

    if keys_to_track:
        async with _in_flight_lock:
            for k in keys_to_track:
                if k in _in_flight_runs:
                    existing_fut = _in_flight_runs[k]
                    break

            if existing_fut is None:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                for k in keys_to_track:
                    _in_flight_runs[k] = fut

    if existing_fut is not None:
        logger.warning(
            f"⚠️ Duplicate in-flight /run request detected for session_id='{session_id}' "
            f"(doc_id='{document_id}'). Joining existing in-flight run (single-flight)..."
        )
        try:
            status_code, headers, body, media_type = await asyncio.shield(existing_fut)
            return Response(
                content=body,
                status_code=status_code,
                headers=headers,
                media_type=media_type,
            )
        except Exception as join_err:
            logger.error(
                f"❌ Joined in-flight run for session_id='{session_id}' failed: {join_err}"
            )
            raise

    ctx = None
    try:
        try:
            ctx, merged_payload = prepare_agent_execution(input_payload)

            if ctx and ctx.document_id and fut is not None:
                doc_key = f"doc:{ctx.document_id}"
                if doc_key not in keys_to_track:
                    keys_to_track.append(doc_key)
                    async with _in_flight_lock:
                        _in_flight_runs[doc_key] = fut

            if is_adk:
                body_json["new_message"]["parts"][0]["text"] = json.dumps(merged_payload)
                new_body_bytes = json.dumps(body_json).encode("utf-8")
            else:
                new_body_bytes = json.dumps(merged_payload).encode("utf-8")

            async def receive():
                return {"type": "http.request", "body": new_body_bytes}

            request = Request(request.scope, receive=receive)
        except HTTPException as http_ex:
            err_resp = JSONResponse(
                status_code=http_ex.status_code,
                content={"detail": http_ex.detail},
            )
            if fut is not None and not fut.done():
                fut.set_result(
                    (err_resp.status_code, dict(err_resp.headers), err_resp.body, err_resp.media_type)
                )
            return err_resp
        except Exception as ex:
            logger.error(f"Error preparing agent execution in middleware: {ex}")

        try:
            response = await call_next(request)
            if ctx:
                doc_status = get_document_status(ctx.document_id, ctx.no_persist)
                if response.status_code >= 400:
                    mark_document_failed(
                        ctx.document_id,
                        f"Execution failed with HTTP status {response.status_code}",
                        ctx.no_persist,
                    )
                elif doc_status != "PASS":
                    err_detail = (
                        f"Agent execution completed with status '{doc_status}' "
                        f"without publishing an approved document."
                    )
                    logger.error(f"❌ {err_detail} (doc_id={ctx.document_id})")
                    mark_document_failed(ctx.document_id, err_detail, ctx.no_persist)
                    response = JSONResponse(
                        status_code=500,
                        content={
                            "detail": err_detail,
                            "document_id": ctx.document_id,
                            "status": "failed",
                        },
                    )
        except Exception as exc:
            err_str = str(exc)
            is_429 = is_429_error(exc)
            if ctx:
                mark_document_failed(ctx.document_id, err_str, ctx.no_persist)

            status_code = 429 if is_429 else 500
            error_msg = (
                f"Rate limit / quota exceeded (429): {err_str}"
                if is_429
                else f"Agent execution error: {err_str}"
            )
            logger.error(f"❌ {error_msg}")
            response = JSONResponse(
                status_code=status_code,
                content={
                    "detail": error_msg,
                    "document_id": ctx.document_id if ctx else None,
                    "status": "failed",
                    "error_code": "RESOURCE_EXHAUSTED" if is_429 else "INTERNAL_ERROR",
                },
            )

        # Buffer response body so single-flight joiners and this caller both receive the body
        if hasattr(response, "body_iterator"):
            body_chunks = []
            async for chunk in response.body_iterator:
                body_chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
            res_body = b"".join(body_chunks)
        else:
            res_body = getattr(response, "body", b"")

        res_headers = dict(response.headers)
        res_headers.pop("content-length", None)
        res_headers.pop("content-encoding", None)

        result_tuple = (response.status_code, res_headers, res_body, response.media_type)
        if fut is not None and not fut.done():
            fut.set_result(result_tuple)

        return Response(
            content=res_body,
            status_code=response.status_code,
            headers=res_headers,
            media_type=response.media_type,
        )
    except BaseException as base_exc:
        if fut is not None and not fut.done():
            fut.set_exception(base_exc)
        raise
    finally:
        if keys_to_track:
            async with _in_flight_lock:
                for k in keys_to_track:
                    _in_flight_runs.pop(k, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
