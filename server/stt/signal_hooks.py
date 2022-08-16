from typing import Optional, Dict, Any, List
from bson import ObjectId
from copy import deepcopy
import logging
from eve.utils import config, ParsedRequest
from flask import json

from superdesk import get_resource_service, signals
from superdesk.factory.app import SuperdeskEve
from superdesk.metadata.item import ITEM_STATE, CONTENT_STATE

from planning.common import WORKFLOW_STATE, ASSIGNMENT_WORKFLOW_STATE
from planning.signals import planning_created

from stt.stt_planning_ml import STTPlanningMLParser


logger = logging.getLogger(__name__)


def init_app(_app: SuperdeskEve):
    planning_created.connect(after_planning_created)
    signals.item_publish.connect(before_content_published)


def after_planning_created(_sender: Any, item: Dict[str, Any]):
    """Link coverage(s) to content upon ingest (if content exists)"""

    if not _is_ingested_by_stt_planning_ml(item):
        return

    delivery_service = get_resource_service("delivery")
    planning_id = item.get(config.ID_FIELD)
    updates = {"coverages": deepcopy(item.get("coverages") or [])}
    coverages_updated = {}
    for coverage in updates["coverages"]:
        coverage_id = coverage.get("coverage_id")
        deliveries = delivery_service.get(req=None, lookup={
            "planning_id": planning_id,
            "coverage_id": coverage_id,
        })
        content = _get_content_item_by_uris([
            delivery["item_id"]
            for delivery in deliveries
            if delivery.get("item_id") is not None
        ])
        if content is None:
            # No content has been found
            # Linking will occur when content is published (see ``before_content_published``)
            continue

        _update_coverage_assignment_details(coverage, content)
        coverages_updated[coverage_id] = content

    updated_item = get_resource_service("planning").patch(planning_id, updates)
    updated_coverage_ids = coverages_updated.keys()
    for coverage in updated_item.get("coverages") or []:
        coverage_id = coverage.get("coverage_id")
        assignment_id = (coverage.get("assigned_to") or {}).get("assignment_id")
        if coverage_id not in updated_coverage_ids or assignment_id is None:
            continue

        _link_assignment_and_content(assignment_id, coverage_id, coverages_updated[coverage_id]["_id"])


def before_content_published(_sender: Any, item: Dict[str, Any], updates: Dict[str, Any]):
    """Link content to coverage before publishing"""

    if item.get("assignment_id") is not None:
        # This item is already linked to a coverage
        # no need to continue
        return

    delivery_service = get_resource_service("delivery")
    planning_service = get_resource_service("planning")

    deliveries = delivery_service.get(req=None, lookup={
        "item_id": item.get("uri"),
        "assignment_id": None
    })
    if not deliveries.count():
        # No ``delivery`` entries found without an Assignment
        return

    planning_id = deliveries[0].get("planning_id")
    coverage_id = deliveries[0].get("coverage_id")
    planning = planning_service.find_one(req=None, _id=planning_id)
    if not planning:
        logger.warning(f"Failed to link content to coverage: planning item '{planning_id}' not found")
        return

    planning_updates = {"coverages": deepcopy(planning.get("coverages") or [])}
    for coverage in planning_updates["coverages"]:
        if coverage.get("coverage_id") != coverage_id:
            continue
        _update_coverage_assignment_details(coverage, item)

    updated_planning = planning_service.patch(planning_id, planning_updates)
    assignment_id = next(
        (coverage for coverage in updated_planning.get("coverages", []) if coverage.get("coverage_id") == coverage_id),
        {}
    ).get("assigned_to", {}).get("assignment_id")
    if not assignment_id:
        logger.warning(f"Failed to get 'assignment_id' of coverage '{coverage_id}'")
        return

    _link_assignment_and_content(assignment_id, coverage_id, item.get("guid"), True)
    item["assignment_id"] = assignment_id
    updates["assignment_id"] = assignment_id


def _is_ingested_by_stt_planning_ml(item: Dict[str, Any]) -> bool:
    """Determine if the item was ingested by the STTPlanningMLParser parser"""

    ingest_provider_id = item.get("ingest_provider")
    if item.get(ITEM_STATE) != CONTENT_STATE.INGESTED or ingest_provider_id is None:
        return False

    ingest_provider = get_resource_service("ingest_providers").find_one(req=None, _id=ObjectId(ingest_provider_id))
    return ingest_provider is not None and ingest_provider.get("feed_parser") == STTPlanningMLParser.NAME


def _get_content_item_by_uris(uris: List[str]) -> Optional[Dict[str, Any]]:
    """Get content item(s) by uri"""

    req = ParsedRequest()
    req.args = {
        "source": json.dumps({
            "query": {"bool": {"must": [{"terms": {"uri": uris}}]}},
            "sort": [{"rewrite_sequence": "asc"}],
            "size": 1
        }),
        "repo": "archive,published,archived",
    }
    cursor = get_resource_service("search").get(req=req, lookup=None)

    if cursor.count():
        return cursor[0]

    return None


def _update_coverage_assignment_details(coverage: Dict[str, Any], content: Dict[str, Any]):
    """Assign Desk, workflow state etc to coverage"""

    coverage["workflow_status"] = WORKFLOW_STATE.ACTIVE
    coverage.setdefault("assigned_to", {})
    coverage["assigned_to"].update({
        "desk": (content.get("task") or {}).get("desk"),
        "state": (
            ASSIGNMENT_WORKFLOW_STATE.COMPLETED if content.get("pubstatus") is not None
            else ASSIGNMENT_WORKFLOW_STATE.IN_PROGRESS
        ),
        "priority": content.get("priority", 2),
        "user": content["task"]["user"],
        "assignor_desk": content["task"]["user"],
        "assignor_user": content["task"]["user"],
    })


def _link_assignment_and_content(assignment_id: ObjectId, coverage_id: str, content_id: str,
                                 skip_archive_update: Optional[bool] = False):
    """Remove all temporary delivery entries for this coverage and link assignment and content"""

    get_resource_service("delivery").delete_action(lookup={"coverage_id": coverage_id})
    get_resource_service("assignments_link").post([{
        "assignment_id": assignment_id,
        "item_id": content_id,
        "skip_archive_update": skip_archive_update,
    }])
