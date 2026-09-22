from __future__ import annotations

import re
from collections import defaultdict

from app.models import ReplyEndResponse, ReplyRequest, ReplySendResponse, ReplyWaitResponse


_auto_reply_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
_suppressed_merchants: set[str] = set()

_AUTO_REPLY_MARKERS = (
    "thank you for contacting",
    "thanks for contacting",
    "we will respond shortly",
    "our team will respond",
    "your message has been received",
    "automated response",
    "automated assistant",
    "hamari team tak",
    "jaankari ke liye bahut-bahut shukriya",
)
_OPT_OUT_MARKERS = (
    "stop",
    "unsubscribe",
    "not interested",
    "do not message",
    "don't message",
    "dont message",
    "remove me",
    "leave me alone",
)
_POSITIVE_MARKERS = (
    "yes",
    "interested",
    "go ahead",
    "let's do it",
    "lets do it",
    "do it",
    "send it",
    "send the",
    "sign me up",
    "i want to join",
    "want to join",
    "confirm",
)
_OFF_TOPIC_MARKERS = (
    "gst",
    "tax filing",
    "income tax",
    "legal advice",
    "loan",
    "personal problem",
)


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def classify_reply(message: str) -> str:
    """Classify a reply using ordered, auditable phrase rules."""
    lowered = _normalize(message)
    if any(marker in lowered for marker in _OPT_OUT_MARKERS):
        return "opt_out_hostile"
    if any(marker in lowered for marker in _AUTO_REPLY_MARKERS):
        return "auto_reply"
    if any(marker in lowered for marker in _POSITIVE_MARKERS):
        return "positive_intent"
    if any(marker in lowered for marker in _OFF_TOPIC_MARKERS):
        return "off_topic"
    return "off_topic"


def is_merchant_suppressed(merchant_id: str) -> bool:
    return merchant_id in _suppressed_merchants


def _conversation_key(request: ReplyRequest) -> tuple[str, str]:
    return request.merchant_id, request.conversation_id


def handle_reply(request: ReplyRequest):
    classification = classify_reply(request.message)

    if classification == "opt_out_hostile":
        _suppressed_merchants.add(request.merchant_id)
        return ReplyEndResponse(
            action="end",
            rationale=(
                "Merchant frustration or opt-out was explicit; closing the conversation "
                "and suppressing future sends for this merchant."
            ),
        )

    if classification == "auto_reply":
        key = _conversation_key(request)
        normalized_message = _normalize(request.message)
        _auto_reply_counts[(key[0], normalized_message)] += 1
        count = _auto_reply_counts[(key[0], normalized_message)]

        if count >= 3:
            return ReplyEndResponse(
                action="end",
                rationale=(
                    "The same canned auto-reply appeared three times; closing because "
                    "there is no owner-engagement signal."
                ),
            )
        if count == 2:
            return ReplyWaitResponse(
                action="wait",
                wait_seconds=86400,
                rationale="The same auto-reply appeared twice; waiting 24 hours for the owner.",
            )
        return ReplyWaitResponse(
            action="wait",
            wait_seconds=14400,
            rationale="Detected a canned WhatsApp auto-reply; waiting 4 hours for the owner.",
        )

    if classification == "positive_intent":
        return ReplySendResponse(
            action="send",
            body="Great, I’ll move this forward. Reply CONFIRM when you’re ready for the next step.",
            cta="binary_confirm_cancel",
            rationale="Explicit positive intent detected; switching directly from qualification to action.",
        )

    return ReplySendResponse(
        action="send",
        body="That request is outside what I can help with here. Reply YES to continue with the current Vera request.",
        cta="binary_yes_no",
        rationale="The reply was off-topic; declining without making claims and redirecting to the active conversation.",
    )
