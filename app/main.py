from __future__ import annotations

import time
from typing import Any, Union

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import compose, priority
from app.models import (
    ContextAcceptedResponse,
    ContextConflictResponse,
    ContextMalformedResponse,
    ContextRequest,
    HealthzResponse,
    MetadataResponse,
    ReplyRequest,
    ReplySendResponse,
    ReplyWaitResponse,
    ReplyEndResponse,
    TickRequest,
    TickResponse,
)
from app.reply_handler import handle_reply, is_merchant_suppressed
from app.store import ContextStore

app = FastAPI(title="Vera Merchant AI Assistant")
store = ContextStore()
sent_suppression_keys: set[str] = set()
start_time = time.monotonic()
MAX_CONTEXT_BODY_BYTES = 500 * 1024
ALLOWED_CONTEXT_SCOPES = {"category", "merchant", "customer", "trigger"}


@app.on_event("startup")
async def record_start_time() -> None:
    global start_time
    start_time = time.monotonic()


@app.middleware("http")
async def context_payload_size_guard(request: Request, call_next):
    if request.method != "POST" or request.url.path != "/v1/context":
        return await call_next(request)

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_CONTEXT_BODY_BYTES:
                return JSONResponse(
                    status_code=400,
                    content={
                        "accepted": False,
                        "reason": "payload_too_large",
                        "details": "Request body exceeds the 500KB context limit.",
                    },
                )
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "accepted": False,
                    "reason": "invalid_content_length",
                    "details": "Content-Length must be a valid integer.",
                },
            )

    received_bytes = 0
    original_receive = request._receive

    async def limited_receive():
        nonlocal received_bytes
        message = await original_receive()
        if message.get("type") == "http.request":
            received_bytes += len(message.get("body", b""))
            if received_bytes > MAX_CONTEXT_BODY_BYTES:
                raise ValueError("context payload exceeds 500KB")
        return message

    request._receive = limited_receive
    try:
        return await call_next(request)
    except ValueError as exc:
        if str(exc) != "context payload exceeds 500KB":
            raise
        return JSONResponse(
            status_code=400,
            content={
                "accepted": False,
                "reason": "payload_too_large",
                "details": "Request body exceeds the 500KB context limit.",
            },
        )


@app.get("/v1/healthz", response_model=HealthzResponse)
def healthz() -> HealthzResponse:
    counts = store.context_counts()
    return HealthzResponse(
        status="ok",
        uptime_seconds=max(0, int(time.monotonic() - start_time)),
        contexts_loaded=counts,
    )


@app.get("/v1/metadata", response_model=MetadataResponse)
def metadata() -> MetadataResponse:
    return MetadataResponse(
        team_name="Team Alpha",
        team_members=["Alice", "Bob"],
        model="claude-opus-4-7",
        approach="single-prompt composer with retrieval over digest items",
        contact_email="team@example.com",
        version="1.2.0",
        submitted_at="2026-04-26T08:00:00Z",
    )


@app.post(
    "/v1/context",
    response_model=Union[ContextAcceptedResponse, ContextConflictResponse, ContextMalformedResponse],
)
def upsert_context(request: ContextRequest) -> Union[ContextAcceptedResponse, ContextConflictResponse, ContextMalformedResponse]:
    if request.scope not in ALLOWED_CONTEXT_SCOPES:
        return JSONResponse(
            status_code=400,
            content={
                "accepted": False,
                "reason": "invalid_scope",
                "details": f"Unsupported scope: {request.scope}",
            },
        )

    result = store.upsert(request)
    if result["accepted"]:
        return ContextAcceptedResponse(**result)

    if result["reason"] == "stale_version":
        return ContextConflictResponse(**result)

    return ContextMalformedResponse(**result)


@app.post("/v1/tick", response_model=TickResponse)
def tick(request: TickRequest) -> TickResponse:
    triggers_by_merchant: dict[str, list[dict[str, Any]]] = {}
    for trigger_id in request.available_triggers:
        record = store.get("trigger", trigger_id)
        if record is None:
            continue

        trigger = record["payload"]
        merchant_id = trigger.get("merchant_id")
        if merchant_id:
            triggers_by_merchant.setdefault(merchant_id, []).append(trigger)

    actions = []
    for merchant_id, active_triggers in triggers_by_merchant.items():
        if is_merchant_suppressed(merchant_id):
            continue
        merchant_record = store.get("merchant", merchant_id)
        if merchant_record is None:
            continue

        merchant = merchant_record["payload"]
        selected_trigger = priority.pick_trigger(merchant, active_triggers)
        if selected_trigger is None:
            continue

        category_slug = merchant.get("category_slug")
        category_record = store.get("category", category_slug) if category_slug else None
        category = category_record["payload"] if category_record else {"slug": category_slug}

        customer = None
        customer_id = selected_trigger.get("customer_id")
        if customer_id:
            customer_record = store.get("customer", customer_id)
            if customer_record:
                customer = customer_record["payload"]

        composed = compose.compose(category, merchant, selected_trigger, customer)
        suppression_key = composed["suppression_key"]
        if suppression_key in sent_suppression_keys:
            continue

        trigger_id = selected_trigger.get("id") or "trigger"
        conversation_id = f"conv_{merchant_id}_{selected_trigger.get('kind', 'trigger')}"
        action = {
            "conversation_id": conversation_id,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "send_as": composed["send_as"],
            "trigger_id": trigger_id,
            "template_name": (
                "merchant_trigger_v1"
                if composed["send_as"] == "merchant_on_behalf"
                else "vera_trigger_v1"
            ),
            "template_params": [],
            "body": composed["message"],
            "cta": composed["cta"],
            "suppression_key": suppression_key,
            "rationale": composed["rationale"],
        }
        actions.append(action)
        sent_suppression_keys.add(suppression_key)

        if len(actions) >= 20:
            break

    return TickResponse(actions=actions)


@app.post(
    "/v1/reply",
    response_model=Union[ReplySendResponse, ReplyWaitResponse, ReplyEndResponse],
)
def reply(request: ReplyRequest) -> Union[ReplySendResponse, ReplyWaitResponse, ReplyEndResponse]:
    return handle_reply(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
