from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import ContextRequest
from app.store import ContextStore
    

DEFAULT_DELIVERED_AT = "1970-01-01T00:00:00Z"


def _resolve_expanded_dir(dataset_root: str | Path) -> Path:
    root = Path(dataset_root)
    preferred_candidates = [
        root / "expanded",
        root,
    ]
    for candidate in preferred_candidates:
        if candidate.exists():
            if (candidate / "categories").exists() or (candidate / "merchants").exists() or (candidate / "customers").exists() or (candidate / "triggers").exists():
                return candidate
    raise FileNotFoundError(
        f"Expanded dataset not found under {root} or {root / 'expanded'}. "
        "Run `python dataset/generate_dataset.py --out dataset/expanded` first."
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _ingest_into_store(store: ContextStore, scope: str, context_id: str, payload: dict[str, Any], version: int = 1) -> None:
    request = ContextRequest(
        scope=scope,
        context_id=context_id,
        version=version,
        payload=payload,
        delivered_at=DEFAULT_DELIVERED_AT,
    )
    response = store.upsert(request)

    if not response["accepted"] and response.get("reason") != "stale_version":
        raise ValueError(f"Failed to load {scope}:{context_id}: {response}")


def load_expanded_dataset(dataset_root: str | Path, store: ContextStore | None = None) -> ContextStore:
    """Populate a ContextStore from the generated expanded dataset structure."""
    expanded_dir = _resolve_expanded_dir(dataset_root)
    if store is None:
        store = ContextStore()

    categories_dir = expanded_dir / "categories"
    if categories_dir.exists():
        for category_file in sorted(categories_dir.glob("*.json")):
            category_payload = _load_json_file(category_file)
            slug = str(category_payload.get("slug") or category_file.stem)
            _ingest_into_store(store, "category", slug, category_payload)

    merchants_dir = expanded_dir / "merchants"
    if merchants_dir.exists():
        for merchant_file in sorted(merchants_dir.glob("*.json")):
            merchant_payload = _load_json_file(merchant_file)
            merchant_id = str(merchant_payload.get("merchant_id") or merchant_file.stem)
            _ingest_into_store(store, "merchant", merchant_id, merchant_payload)

    customers_dir = expanded_dir / "customers"
    if customers_dir.exists():
        for customer_file in sorted(customers_dir.glob("*.json")):
            customer_payload = _load_json_file(customer_file)
            customer_id = str(customer_payload.get("customer_id") or customer_file.stem)
            _ingest_into_store(store, "customer", customer_id, customer_payload)

    triggers_dir = expanded_dir / "triggers"
    if triggers_dir.exists():
        for trigger_file in sorted(triggers_dir.glob("*.json")):
            trigger_payload = _load_json_file(trigger_file)
            trigger_id = str(trigger_payload.get("id") or trigger_file.stem)
            _ingest_into_store(store, "trigger", trigger_id, trigger_payload)

    return store


def lookup_context(store: ContextStore, scope: str, context_id: str) -> dict[str, Any] | None:
    return store.get(scope, context_id)


def lookup_context_payload(store: ContextStore, scope: str, context_id: str) -> dict[str, Any] | None:
    record = store.get(scope, context_id)
    if record is None:
        return None
    return record.get("payload")
