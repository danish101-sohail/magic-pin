from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class OfferCatalogItem(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    value: Optional[str] = None
    audience: Optional[str] = None
    type: Optional[str] = None


class VoiceProfile(BaseModel):
    tone: Optional[str] = None
    vocab_allowed: Optional[list[str]] = None
    vocab_taboo: Optional[list[str]] = None
    taboos: Optional[list[str]] = None


class PeerStats(BaseModel):
    avg_rating: Optional[float] = None
    avg_reviews: Optional[int] = None
    avg_ctr: Optional[float] = None
    scope: Optional[str] = None


class DigestItem(BaseModel):
    id: Optional[str] = None
    kind: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    summary: Optional[str] = None


class ContentItem(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    channel: Optional[str] = None
    body: Optional[str] = None


class SeasonalBeat(BaseModel):
    month_range: Optional[str] = None
    note: Optional[str] = None


class TrendSignal(BaseModel):
    query: Optional[str] = None
    delta_yoy: Optional[float] = None
    segment_age: Optional[str] = None


class CategoryPayload(BaseModel):
    slug: str
    offer_catalog: Optional[list[OfferCatalogItem]] = None
    voice: Optional[VoiceProfile] = None
    peer_stats: Optional[PeerStats] = None
    digest: Optional[list[DigestItem]] = None
    patient_content_library: Optional[list[ContentItem]] = None
    seasonal_beats: Optional[list[SeasonalBeat]] = None
    trend_signals: Optional[list[TrendSignal]] = None


class MerchantIdentity(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    place_id: Optional[str] = None
    verified: Optional[bool] = None
    languages: Optional[list[str]] = None
    owner_first_name: Optional[str] = None


class Subscription(BaseModel):
    status: Optional[str] = None
    plan: Optional[str] = None
    days_remaining: Optional[int] = None


class Delta7d(BaseModel):
    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None


class Performance(BaseModel):
    window_days: Optional[int] = None
    views: Optional[int] = None
    calls: Optional[int] = None
    directions: Optional[int] = None
    ctr: Optional[float] = None
    delta_7d: Optional[Delta7d] = None


class MerchantOffer(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None


class ConversationEntry(BaseModel):
    ts: Optional[str] = None
    from_: Optional[str] = Field(default=None, alias="from")
    body: Optional[str] = None
    engagement: Optional[str] = None


class CustomerAggregate(BaseModel):
    total_unique_ytd: Optional[int] = None
    lapsed_180d_plus: Optional[int] = None
    retention_6mo_pct: Optional[float] = None
    high_risk_adult_count: Optional[int] = None


class MerchantPayload(BaseModel):
    merchant_id: str
    category_slug: Optional[str] = None
    identity: Optional[MerchantIdentity] = None
    subscription: Optional[Subscription] = None
    performance: Optional[Performance] = None
    offers: Optional[list[MerchantOffer]] = None
    conversation_history: Optional[list[ConversationEntry]] = None
    customer_aggregate: Optional[CustomerAggregate] = None
    signals: Optional[list[str]] = None


class CustomerIdentity(BaseModel):
    name: Optional[str] = None
    phone_redacted: Optional[str] = None
    language_pref: Optional[str] = None


class Relationship(BaseModel):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: Optional[int] = None
    services_received: Optional[list[str]] = None


class Preferences(BaseModel):
    preferred_slots: Optional[str] = None
    channel: Optional[str] = None


class Consent(BaseModel):
    opted_in_at: Optional[str] = None
    scope: Optional[list[str]] = None


class CustomerPayload(BaseModel):
    customer_id: str
    merchant_id: str
    identity: Optional[CustomerIdentity] = None
    relationship: Optional[Relationship] = None
    state: Optional[str] = None
    preferences: Optional[Preferences] = None
    consent: Optional[Consent] = None


class TriggerPayload(BaseModel):
    id: str
    scope: str
    kind: str
    source: str
    merchant_id: str
    customer_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    urgency: int
    suppression_key: str
    expires_at: str


class ContextRequest(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any] = Field(default_factory=dict)
    delivered_at: str


class ContextAcceptedResponse(BaseModel):
    accepted: Literal[True] = True
    ack_id: str
    stored_at: str


class ContextConflictResponse(BaseModel):
    accepted: Literal[False] = False
    reason: Literal["stale_version"]
    current_version: int


class ContextMalformedResponse(BaseModel):
    accepted: Literal[False] = False
    reason: str
    details: str


class ActionPayload(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: str
    template_name: str
    template_params: list[str]
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str]


class TickResponse(BaseModel):
    actions: list[ActionPayload] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    from_role: Literal["merchant", "customer"]
    message: str
    received_at: str
    turn_number: int


class ReplySendResponse(BaseModel):
    action: Literal["send"]
    body: str
    cta: str
    rationale: str


class ReplyWaitResponse(BaseModel):
    action: Literal["wait"]
    wait_seconds: int
    rationale: str


class ReplyEndResponse(BaseModel):
    action: Literal["end"]
    rationale: str


class HealthzResponse(BaseModel):
    status: Literal["ok"]
    uptime_seconds: int
    contexts_loaded: dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
