"""Shared helpers for querying Superdesk resources with optional projection support."""

import logging
from typing import Any, Dict, List, Optional

from superdesk import get_resource_service
from superdesk.core.app import get_current_async_app

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


def get_published_items_with_sttnewsroomnote_by_planning_id(
    planning_id: str,
) -> List[Dict[str, Any]]:
    """Return published items linked to *planning_id* via coverage assignments.
    Return a list of published item documents that have a subject with scheme 'sttnewsroomnote'.

    Executes the aggregation pipeline:

        match planning -> collect all sttimagetype names from picture/graphic coverages ->
        combine them into a comma-separated sttimagetype string -> unwind coverages ->
        convert assignment_id to ObjectId -> filter null assignments -> lookup published ->
        unwind -> merge sttimagetype into the published document.

    Any errors during aggregation are logged and result in an empty list.
    """

    try:
        async_app = get_current_async_app()
        collection = async_app.wsgi.data.get_mongo_collection("planning")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Unable to access planning Mongo collection via service/driver (%s: %s)",
            exc.__class__.__name__,
            exc,
        )
        return []

    pipeline = [
        {"$match": {"_id": planning_id}},
        {
            # 1) Collect all sttimagetype subject names from graphic coverages
            "$addFields": {
                "sttimagetypes": {
                    "$map": {
                        "input": {
                            "$filter": {
                                "input": "$coverages",
                                "as": "c",
                                "cond": {
                                    "$in": [
                                        "$$c.planning.g2_content_type",
                                        ["graphic", "picture"],
                                    ],
                                },
                            }
                        },
                        "as": "graphic",
                        "in": {
                            "$map": {
                                "input": {
                                    "$filter": {
                                        "input": {
                                            "$ifNull": [
                                                "$$graphic.planning.subject",
                                                [],
                                            ]
                                        },
                                        "as": "s",
                                        "cond": {"$eq": ["$$s.scheme", "sttimagetype"]},
                                    }
                                },
                                "as": "subject",
                                "in": "$$subject.name",
                            }
                        },
                    }
                }
            }
        },
        {
            "$addFields": {
                "sttimagetype": {
                    "$reduce": {
                        "input": {
                            "$reduce": {
                                "input": "$sttimagetypes",
                                "initialValue": [],
                                "in": {"$concatArrays": ["$$value", "$$this"]},
                            }
                        },
                        "initialValue": "",
                        "in": {
                            "$cond": [
                                {"$eq": ["$$value", ""]},
                                {"$ifNull": ["$$this", ""]},
                                {
                                    "$cond": [
                                        {"$eq": ["$$this", ""]},
                                        "$$value",
                                        {"$concat": ["$$value", ", ", "$$this"]},
                                    ]
                                },
                            ]
                        },
                    }
                }
            }
        },
        # 2) Work per-coverage to find the one(s) that have assignment_id, and join to published
        {"$unwind": "$coverages"},
        {
            # Convert assignment id (string) -> ObjectId
            "$addFields": {
                "assignment_id_obj": {
                    "$convert": {
                        "input": "$coverages.assigned_to.assignment_id",
                        "to": "objectId",
                        "onError": None,
                        "onNull": None,
                    }
                }
            }
        },
        # Only keep coverages where we do have a valid assignment id
        {"$match": {"assignment_id_obj": {"$ne": None}}},
        {
            # 3) Lookup published with filters
            "$lookup": {
                "from": "published",
                "let": {"aobj": "$assignment_id_obj"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$assignment_id", "$$aobj"]},
                            "state": "published",
                            "subject": {"$elemMatch": {"scheme": "sttnewsroomnote"}},
                        }
                    }
                ],
                "as": "pub",
            }
        },
        {"$unwind": "$pub"},
        {
            # 4) Merge the precomputed sttimagetype into each published doc
            "$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": ["$pub", {"sttimagetype": "$sttimagetype"}]
                }
            }
        },
    ]

    try:
        return list(collection.aggregate(pipeline))
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception(
            "Error aggregating published items for planning %s (%s: %s)",
            planning_id,
            exc.__class__.__name__,
            exc,
        )
        return []


def get_published_items_by_planning_id_and_genre_qcodes(
    planning_id: str,
    genre_qcodes: List[str],
    projection: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """Return published items linked to *planning_id* filtered by genre qcodes.

    This follows the relation:

        planning._id -> delivery.planning_id -> published.item_id (via delivery.item_id)

    Only delivery rows with ``item_state == 'published'`` are considered.
    The published query matches any item whose ``genre.qcode`` is one of
    ``genre_qcodes``.
    """

    if not planning_id or not genre_qcodes:
        return []

    deliveries = find_many(
        "delivery",
        {"planning_id": planning_id, "item_state": "published"},
        projection={"item_id": 1, "_id": 0},
    )

    item_ids_set = set()
    for delivery in deliveries:
        if not isinstance(delivery, dict):
            continue
        item_id = delivery.get("item_id")
        if not item_id:
            continue
        item_ids_set.add(str(item_id))

    item_ids = sorted(item_ids_set)
    if not item_ids:
        return []

    if projection is None:
        projection = {
            "assignment_id": 1,
            "firstpublished": 1,
            "genre": 1,
            "body_html": 1,
            "item_id": 1,
            "operation": 1,
            "profile": 1,
            "state": 1,
            "versioncreated": 1,
        }

    items = find_many(
        "published",
        {
            "item_id": {"$in": item_ids},
            "genre.qcode": {"$in": genre_qcodes},
            "state": {"$in": ["published"]},
        },
        projection=projection,
    )

    # Stable ordering for exports/UI usage: newest first when the field exists.
    items.sort(key=lambda item: (item or {}).get("versioncreated") or "", reverse=True)
    return items
