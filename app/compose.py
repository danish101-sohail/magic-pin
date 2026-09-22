from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


def _norm(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, Mapping):
        return dict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return {}


def _get(data: Any, *keys: str, default: Any = None) -> Any:
    current = data
    for key in keys:
        if isinstance(current, Mapping):
            current = current.get(key)
        elif hasattr(current, key):
            current = getattr(current, key)
        else:
            return default
        if current is None:
            return default
    return current if current is not None else default


def _merchant_name(merchant: Any) -> str:
    merchant = _norm(merchant)
    identity = _norm(_get(merchant, "identity"))
    owner = _get(identity, "owner_first_name") or _get(identity, "first_name")
    name = _get(identity, "name") or _get(merchant, "merchant_id") or "merchant"
    if owner:
        return str(owner)
    if name:
        return str(name)
    return "merchant"


def _customer_name(customer: Any) -> str:
    customer = _norm(customer)
    identity = _norm(_get(customer, "identity"))
    name = _get(identity, "name") or "there"
    return str(name)


def _category_slug(category: Any, merchant: Any) -> str:
    category = _norm(category)
    merchant = _norm(merchant)
    return str(_get(category, "slug") or _get(merchant, "category_slug") or "general")


def _tone_for_category(category_slug: str) -> str:
    tone_map = {
        "dentists": "peer_clinical",
        "salons": "warm_practical",
        "restaurants": "warm_busy_practical",
        "gyms": "energetic_disciplined",
        "pharmacies": "trustworthy_precise",
    }
    return tone_map.get(category_slug, "practical")


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _safe_offer_title(merchant: Any) -> str | None:
    offers = _get(merchant, "offers") or []
    if not isinstance(offers, list):
        return None
    for offer in offers:
        if isinstance(offer, Mapping) and str(_get(offer, "status", "")).lower() == "active":
            title = _get(offer, "title")
            if title:
                return str(title)
    return None


def _format_trigger_context(category: Any, trigger: Any) -> str:
    trigger = _norm(trigger)
    kind = str(_get(trigger, "kind") or "general")
    payload = _norm(_get(trigger, "payload"))
    category_dict = _norm(category)
    digest = _get(category_dict, "digest") or []
    top_item_id = _get(payload, "top_item_id") or _get(payload, "top_item")

    if isinstance(top_item_id, Mapping):
        top_item_id = _get(top_item_id, "id")
    if top_item_id and isinstance(digest, list):
        for item in digest:
            item = _norm(item)
            if _get(item, "id") == top_item_id:
                title = _get(item, "title")
                source = _get(item, "source")
                if title:
                    suffix = f" — {source}" if source else ""
                    return f"{title}{suffix}"
    return kind.replace("_", " ")


def _suppression_key(merchant_id: str | None, trigger_kind: str | None) -> str:
    merchant_id = merchant_id or "unknown_merchant"
    trigger_kind = trigger_kind or "unknown_trigger"
    return f"{merchant_id}:{trigger_kind}"


def _build_customer_message(category_slug: str, merchant: Any, trigger: Any, customer: Any) -> tuple[str, str]:
    customer = _norm(customer)
    merchant = _norm(merchant)
    trigger = _norm(trigger)

    customer_name = _customer_name(customer)
    merchant_name = _merchant_name(merchant)
    identity = _norm(_get(customer, "identity"))
    relationship = _norm(_get(customer, "relationship"))
    preferences = _norm(_get(customer, "preferences"))
    last_visit = _get(relationship, "last_visit")
    offer_title = _safe_offer_title(merchant)
    preferred_slots = _get(preferences, "preferred_slots")
    kind = str(_get(trigger, "kind") or "recall_due")

    if category_slug == "dentists":
        if offer_title:
            offer_line = f"{offer_title}."
        else:
            offer_line = "your recall is due."
        if last_visit:
            msg = f"Hi {customer_name}, {merchant_name} here. Your last visit was on {last_visit}, and your recall is due. {offer_line} Reply YES to confirm the next slot."
        else:
            msg = f"Hi {customer_name}, {merchant_name} here. Your recall is due. {offer_line} Reply YES to confirm the next slot."
        return msg, "binary_yes_no"

    if category_slug == "salons":
        if preferred_slots:
            slot_line = f"I can hold your preferred {preferred_slots} slot."
        else:
            slot_line = "I can reserve a slot that suits you."
        if offer_title:
            offer_line = f"Current offer: {offer_title}."
        else:
            offer_line = ""
        msg = f"Hi {customer_name}, {merchant_name} here. Your last visit was on {last_visit or 'your recent visit'}, and I can help you plan the next session. {offer_line} {slot_line} Reply YES to lock it in."
        return msg, "binary_yes_no"

    if category_slug == "restaurants":
        if offer_title:
            msg = f"Hi {customer_name}, {merchant_name} here. We have {offer_title} ready for your next visit. Reply YES and I’ll hold the table/slot."
        else:
            msg = f"Hi {customer_name}, {merchant_name} here. Your last visit was on {last_visit or 'your recent visit'}. Reply YES and I’ll save your next slot."
        return msg, "binary_yes_no"

    if category_slug == "gyms":
        offer_line = offer_title if offer_title else "our next session"
        msg = f"Hi {customer_name}, {merchant_name} here. We can get you back on track with {offer_line}. Reply YES and I’ll reserve the first slot."
        return msg, "binary_yes_no"

    if category_slug == "pharmacies":
        if offer_title:
            msg = f"Hi {customer_name}, {merchant_name} here. Your refill reminder is ready, and we have {offer_title}. Reply YES to confirm the delivery."
        else:
            msg = f"Hi {customer_name}, {merchant_name} here. Your refill reminder is ready. Reply YES to confirm the delivery."
        return msg, "binary_yes_no"

    msg = f"Hi {customer_name}, {merchant_name} here. We can help with your next step. Reply YES to continue."
    return msg, "binary_yes_no"


def _build_merchant_message(category_slug: str, merchant: Any, trigger: Any) -> tuple[str, str]:
    merchant = _norm(merchant)
    trigger = _norm(trigger)
    merchant_name = _merchant_name(merchant)
    trigger_kind = str(_get(trigger, "kind") or "general")
    performance = _norm(_get(merchant, "performance"))
    subscription = _norm(_get(merchant, "subscription"))
    customer_aggregate = _norm(_get(merchant, "customer_aggregate"))
    category = _norm(_get(merchant, "category_context"))
    trigger_text = _format_trigger_context(category, trigger)

    if category_slug == "dentists":
        high_risk = _get(customer_aggregate, "high_risk_adult_count")
        if high_risk is not None:
            msg = f"Dr. {merchant_name}, one item relevant to your high-risk adult cohort: {trigger_text}. {high_risk} patients in your roster fit that group. Want me to pull the summary and draft a patient WhatsApp?"
        else:
            msg = f"Dr. {merchant_name}, {trigger_text}. Worth a look and I can pull a patient-ready follow-up for you."
        return msg, "binary_yes_no"

    if category_slug == "salons":
        owner_first = _get(_norm(_get(merchant, "identity")), "owner_first_name") or merchant_name
        views = _get(performance, "views")
        calls = _get(performance, "calls")
        if views is not None and calls is not None:
            msg = f"Hi {owner_first}! Quick check — your salon has {views} views and {calls} calls in the last 30 days. {trigger_text}. Want me to turn this into a Google post + WhatsApp reply?"
        else:
            msg = f"Hi {owner_first}! Quick one — {trigger_text}. Want me to turn this into a ready-to-send post?"
        return msg, "binary_yes_no"

    if category_slug == "restaurants":
        offer_title = _safe_offer_title(merchant)
        if offer_title:
            msg = f"Quick heads-up {merchant_name} — {trigger_text}. Your active offer {offer_title} gives you the cleanest lever for this. Want me to draft the promo copy right now?"
        else:
            msg = f"Quick heads-up {merchant_name} — {trigger_text}. Want me to turn this into a precise promo or content brief?"
        return msg, "binary_yes_no"

    if category_slug == "gyms":
        views = _get(performance, "views")
        if views is not None:
            msg = f"Hi {merchant_name}, quick check — your gym is seeing {views} views in the last 30 days. {trigger_text}. Want me to draft a retention or conversion nudge for this week?"
        else:
            msg = f"Hi {merchant_name}, {trigger_text}. Want me to draft the retention angle for this week?"
        return msg, "binary_yes_no"

    if category_slug == "pharmacies":
        repeat_customers = _get(customer_aggregate, "total_unique_ytd")
        if repeat_customers is not None:
            msg = f"Hi {merchant_name}, quick heads-up — {trigger_text}. With {repeat_customers} unique customers in your current year, I can draft the customer note and the refill workflow for you."
        else:
            msg = f"Hi {merchant_name}, quick heads-up — {trigger_text}. I can draft the exact customer note and follow-up for you."
        return msg, "binary_yes_no"

    msg = f"Hi {merchant_name}, {trigger_text}. Want me to turn this into a concrete next step?"
    return msg, "binary_yes_no"


def compose(category: Any, merchant: Any, trigger: Any, customer: Any = None) -> dict[str, Any]:
    category = _norm(category)
    merchant = _norm(merchant)
    trigger = _norm(trigger)
    customer = _norm(customer) if customer is not None else None

    category_slug = _category_slug(category, merchant)
    trigger_kind = str(_get(trigger, "kind") or "generic")
    merchant_id = _get(merchant, "merchant_id") or "unknown_merchant"

    if customer is not None:
        message, cta = _build_customer_message(category_slug, merchant, trigger, customer)
        send_as = "merchant_on_behalf"
    else:
        message, cta = _build_merchant_message(category_slug, merchant, trigger)
        send_as = "vera"

    rationale = (
        f"Trigger '{trigger_kind}' matched the {category_slug} context; "
        f"the message uses the merchant's real state ({_get(merchant, 'merchant_id')}) and concrete facts from the trigger payload."
    )

    return {
        "message": message,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": _suppression_key(merchant_id, trigger_kind),
        "rationale": rationale,
    }


def compose_message(*args: Any, **kwargs: Any) -> dict[str, Any]:
    category = kwargs.get("category")
    merchant = kwargs.get("merchant")
    trigger = kwargs.get("trigger")
    customer = kwargs.get("customer")
    if args:
        if len(args) >= 4:
            category, merchant, trigger, customer = args[:4]
        elif len(args) >= 3:
            category, merchant, trigger = args[:3]
    return compose(category, merchant, trigger, customer)
