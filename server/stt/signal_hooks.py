from typing import Optional, Dict, Any, List
from bson import ObjectId
from copy import deepcopy
import logging
from eve.utils import config, ParsedRequest
from flask import json

from superdesk import get_resource_service, signals
from superdesk.factory.app import SuperdeskEve

from planning.common import WORKFLOW_STATE, ASSIGNMENT_WORKFLOW_STATE
from planning.signals import planning_ingested

from stt.stt_planning_ml import STTPlanningMLParser


logger = logging.getLogger(__name__)


def init_app(_app: SuperdeskEve):
    planning_ingested.connect(link_coverages_to_content)
    signals.item_publish.connect(before_content_published)


def link_coverages_to_content(_sender: Any, item: Dict[str, Any], original: Optional[Dict[str, Any]] = None):
    """Link coverage(s) to content upon ingest (if content exists)"""

    try:
        planning_id = item[config.ID_FIELD]
    except KeyError:
        logger.error("Failed to link planning with content, _id is missing")
        return

    if not len(item.get("coverages") or []):
        # No coverages on this Planning item, no need to continue
        return

    try:
        if len(item["coverages"]) == 1 and item["coverages"][0]["flags"]["placeholder"] is True:
            # There is only 1 coverage, and it is a placeholder coverage, no need to continue
            return
    except (KeyError, IndexError, TypeError):
        return

    if not _is_ingested_by_stt_planning_ml(item):
        return

    updates = {"coverages": deepcopy(item["coverages"])}
    coverage_id_to_content_id_map: Dict[str, str] = {}
    delivery_service = get_resource_service("delivery")
    planning_service = get_resource_service("planning")
    for coverage in updates["coverages"]:
        try:
            coverage_id = coverage["coverage_id"]
        except KeyError:
            logger.error("Failed to link coverage with content, coverage_id is missing")
            continue

        try:
            if coverage["flags"]["placeholder"] is True:
                # This is a placeholder coverage, and will never be attached to content
                continue
        except (KeyError, TypeError):
            pass

        # Get the deliveries that aren't linked to an Assignment
        # These deliveries are added in ``STTPlanningMLParser._create_temp_assignment_deliveries``
        deliveries = delivery_service.get_from_mongo(req=None, lookup={
            "planning_id": planning_id,
            "coverage_id": coverage_id,
            "assignment_id": None,
            "item_id": {"$ne": None}},
        )
        if not deliveries.count():
            # No unlinked deliveries found for this Coverage
            continue

        content = _get_content_item_by_uris([delivery["item_id"] for delivery in deliveries])
        if content is None:
            # No content has been found
            # Linking will occur when content is published (see ``before_content_published``)
            continue

        _update_coverage_assignment_details(coverage, content)
        coverage_id_to_content_id_map[coverage_id] = content[config.ID_FIELD]

    updated_coverage_ids = coverage_id_to_content_id_map.keys()
    if not len(updated_coverage_ids):
        # No coverages were updated, no need to update the Planning item or link any content
        return

    # Update the planning item with the latest Assignment information, and link the coverages to the content
    updated_item = planning_service.patch(planning_id, updates)
    for coverage in updated_item.get("coverages") or []:
        coverage_id = coverage.get("coverage_id")
        assignment_id = (coverage.get("assigned_to") or {}).get("assignment_id")
        if coverage_id not in updated_coverage_ids or assignment_id is None:
            continue

        _link_assignment_and_content(assignment_id, coverage_id, coverage_id_to_content_id_map[coverage_id])


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
    """Determine if the item was ingested by the ``STTPlanningMLParser`` parser"""

    try:
        if item["ingest_provider"] is None:
            return False
        ingest_provider_id = ObjectId(item["ingest_provider"])
        ingest_provider = get_resource_service("ingest_providers").find_one(req=None, _id=ingest_provider_id)
        return ingest_provider["feed_parser"] == STTPlanningMLParser.NAME
    except (KeyError, TypeError):
        return False


def _get_content_item_by_uris(uris: List[str]) -> Optional[Dict[str, Any]]:
    """Get latest content item by uri"""

    if not len(uris):
        # No URIs were provided, so there
        return None

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


def _link_assignment_and_content(
    assignment_id: ObjectId,
    coverage_id: str,
    content_id: str,
    skip_archive_update: Optional[bool] = False
):
    """Remove all temporary delivery entries for this coverage and link assignment and content"""

    get_resource_service("delivery").delete_action(lookup={"coverage_id": coverage_id})
    get_resource_service("assignments_link").post([{
        "assignment_id": assignment_id,
        "item_id": content_id,
        "skip_archive_update": skip_archive_update,
    }])
