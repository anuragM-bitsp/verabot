"""
Vera Bot — FastAPI server
Endpoints: GET /v1/healthz, GET /v1/metadata, POST /v1/context, POST /v1/tick, POST /v1/reply
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from compose import compose
from store import ContextStore

app = FastAPI(title="Vera Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = ContextStore()


# ──────────────────────────────────────────────────────────────────────────────
# MODELS
# ──────────────────────────────────────────────────────────────────────────────

class ContextPayload(BaseModel):
    scope: str                          # "merchant" | "customer" | "trigger"
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class TickPayload(BaseModel):
    session_id: Optional[str] = None
    merchant_id: str
    trigger_id: Optional[str] = None
    trigger: Optional[dict] = None
    customer_id: Optional[str] = None
    category: Optional[str] = None
    extra: Optional[dict] = None


class ReplyPayload(BaseModel):
    session_id: Optional[str] = None
    merchant_id: str
    message: str
    customer_id: Optional[str] = None
    tick_output: Optional[dict] = None
    extra: Optional[dict] = None


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH & METADATA
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/v1/healthz")
async def healthz():
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@app.get("/v1/metadata")
async def metadata():
    return {
        "name": "Vera",
        "version": "1.0.0",
        "description": "Deterministic merchant growth message engine for magicpin",
        "author": "Vera Team",
        "capabilities": ["compose", "context-aware", "multi-category", "stateful"],
        "supported_categories": ["dentist", "salon", "restaurant", "gym", "pharmacy"],
        "supported_triggers": ["recall", "spike", "dip", "research", "festival", "review", "seasonal"],
        "endpoints": {
            "healthz": "GET /v1/healthz",
            "metadata": "GET /v1/metadata",
            "context": "POST /v1/context",
            "tick": "POST /v1/tick",
            "reply": "POST /v1/reply",
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# CONTEXT
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/v1/context")
async def push_context(payload: ContextPayload):
    """
    Idempotent context push. Higher version replaces atomically.
    Scopes: merchant | customer | trigger
    """
    accepted = store.put(payload.scope, payload.context_id, payload.version, payload.payload)
    ack_id = f"ack_{uuid.uuid4().hex[:8]}"
    
    return {
        "accepted": accepted,
        "ack_id": ack_id,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "scope": payload.scope,
        "context_id": payload.context_id,
        "version": payload.version,
    }


# ──────────────────────────────────────────────────────────────────────────────
# TICK  (core compose call)
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/v1/tick")
async def tick(payload: TickPayload):
    """
    Generate the next Vera message for this merchant + trigger moment.
    Resolves context from store, calls compose(), returns structured output.
    """
    # Resolve merchant context
    merchant = store.get("merchant", payload.merchant_id)
    if merchant is None:
        # Try to build a minimal merchant from the payload itself
        merchant = payload.extra or {}
        merchant.setdefault("identity", {"id": payload.merchant_id, "name": payload.merchant_id})

    # Resolve trigger
    trigger = {}
    if payload.trigger:
        trigger = payload.trigger
    elif payload.trigger_id:
        trigger = store.get("trigger", payload.trigger_id) or {}

    # Resolve customer
    customer = None
    if payload.customer_id:
        customer = store.get("customer", payload.customer_id)

    # Resolve category
    category = payload.category
    if not category:
        category = merchant.get("identity", {}).get("category", "restaurant")

    # Compose
    result = compose(category, merchant, trigger, customer)

    session_id = payload.session_id or f"sess_{uuid.uuid4().hex[:10]}"

    # Persist tick output to session store for reply continuity
    store.put_session(session_id, {
        "merchant_id": payload.merchant_id,
        "trigger": trigger,
        "customer_id": payload.customer_id,
        "category": category,
        "output": result,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "session_id": session_id,
        "message": result["message"],
        "headline": result["headline"],
        "cta": result["cta"],
        "send_as": result["send_as"],
        "suppression_key": result["suppression_key"],
        "rationale": result["rationale"],
        "trigger_type": result["trigger_type"],
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# REPLY  (handle merchant response)
# ──────────────────────────────────────────────────────────────────────────────

_POSITIVE_SIGNALS = ["yes", "ok", "sure", "go", "send", "run", "launch", "book", "do it", "perfect", "great", "haan", "ha", "bilkul", "chal"]
_NEGATIVE_SIGNALS = ["no", "not", "later", "wait", "stop", "nahi", "nahin", "band", "ruko", "hold"]
_EDIT_SIGNALS = ["change", "edit", "update", "different", "modify", "instead", "replace", "other"]

def _classify_reply(message: str) -> str:
    msg = message.lower().strip()
    for s in _POSITIVE_SIGNALS:
        if s in msg.split() or msg.startswith(s):
            return "affirm"
    for s in _NEGATIVE_SIGNALS:
        if s in msg.split():
            return "decline"
    for s in _EDIT_SIGNALS:
        if s in msg.split():
            return "edit_request"
    if "?" in msg:
        return "question"
    if any(c.isdigit() for c in msg):
        return "data_input"
    return "unknown"


@app.post("/v1/reply")
async def reply(payload: ReplyPayload):
    """
    Handle merchant reply to a Vera tick message.
    Classifies intent and returns the appropriate next action.
    """
    intent = _classify_reply(payload.message)
    
    # Resolve session context
    session = None
    if payload.tick_output:
        session = {"output": payload.tick_output}

    merchant_name = ""
    trigger_type = "generic"
    if session:
        trigger_type = session.get("output", {}).get("trigger_type", "generic")
        merchant_id = payload.merchant_id
        m = store.get("merchant", merchant_id)
        if m:
            merchant_name = m.get("identity", {}).get("name", "")

    if intent == "affirm":
        next_message = (
            f"Done! I've queued the campaign for {merchant_name or 'your business'}. "
            f"You'll see results in the dashboard within the hour. "
            f"Want me to set a follow-up reminder in 24 hours?"
        )
        next_action = "campaign_queued"
    elif intent == "decline":
        next_message = (
            f"No problem. I'll check back when there's a better moment. "
            f"Should I remind you tomorrow, or would you prefer to pick a time?"
        )
        next_action = "deferred"
    elif intent == "edit_request":
        next_message = (
            f"Sure — what would you like to change? "
            f"You can say things like 'use ₹199 instead' or 'target only women' and I'll update it."
        )
        next_action = "await_edit"
    elif intent == "question":
        next_message = (
            f"Great question. Here's what I recommend: "
            f"based on your current performance, running this now gives the best reach-to-cost ratio. "
            f"Want me to show you the projected numbers?"
        )
        next_action = "explain"
    elif intent == "data_input":
        next_message = (
            f"Got it — I've noted that. Updating the offer parameters now. "
            f"Shall I proceed with the updated details?"
        )
        next_action = "confirm_edit"
    else:
        next_message = (
            f"Thanks for the reply! To confirm — should I go ahead with the suggested action? "
            f"Just say 'yes' to confirm or 'no' to skip."
        )
        next_action = "clarify"

    return {
        "intent": intent,
        "next_message": next_message,
        "next_action": next_action,
        "session_id": payload.session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────────
# ROOT
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"service": "Vera Bot", "docs": "/docs", "health": "/v1/healthz"}
