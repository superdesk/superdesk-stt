"""Shared helpers for querying Superdesk resources with optional projection support."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from superdesk import get_resource_service

logger = logging.getLogger(__name__)


def apply_projection_locally(
    docs: List[Dict[str, Any]], projection: Optional[Dict[str, int]]
) -> List[Dict[str, Any]]:
    """Return copies of *docs* including only keys requested by *projection*.

    Supports Mongo-style inclusion projections (truthy values -> keep field).
    When *projection* is falsy, the original list is returned unchanged.
    """
    if not projection:
        return docs

    keep = {key for key, flag in projection.items() if flag}
    if projection.get("_id"):
        keep.add("_id")

    projected: List[Dict[str, Any]] = []
    for doc in docs:
        projected.append({key: doc.get(key) for key in keep if key in doc})
    return projected


def find_many(
    resource: str,
    lookup: Dict[str, Any],
    projection: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Fetch documents via the resource service, honouring projection when possible."""

    try:
        svc = get_resource_service(resource)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Error using service for %s (%s: %s)", resource, exc.__class__.__name__, exc
        )
        svc = None

    if svc and hasattr(svc, "get_from_mongo"):
        try:
            docs = list(svc.get_from_mongo(None, lookup=lookup, projection=projection))
            if docs is not None:
                return apply_projection_locally(docs, projection)
        except TypeError:
            pass  # Signature mismatch, fall back below.
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Error in find_many service.get_from_mongo for %s (%s: %s)",
                resource,
                exc.__class__.__name__,
                exc,
            )

    if svc and hasattr(svc, "get"):
        try:
            docs = list(svc.get(None, lookup))
            return apply_projection_locally(docs, projection)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception(
                "Error in find_many service.get for %s (%s: %s)",
                resource,
                exc.__class__.__name__,
                exc,
            )

    return []
