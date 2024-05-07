from typing import Optional, Dict, Any, List
from bson import ObjectId
from copy import deepcopy
import logging
from eve.utils import config, ParsedRequest
from flask import json

from superdesk import get_resource_service, signals
from superdesk.factory.app import SuperdeskEve
from superdesk.metadata.item import CONTENT_STATE

from planning.common import (
    WORKFLOW_STATE,
    ASSIGNMENT_WORKFLOW_STATE,
    get_coverage_status_from_cv,
    post_required,
    update_post_item,
)
from planning.signals import planning_ingested

from stt.stt_planning_ml import STTPlanningMLParser
from stt.common import is_online_version


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
        pass

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
            elif coverage["assigned_to"]["assignment_id"] is not None:
                # This coverage is already linked to an Assignment, no need to continue
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

        _copy_metadata_from_article_to_coverage(coverage, content)
        _update_coverage_assignment_details(coverage, content)
        coverage_id_to_content_id_map[coverage_id] = content[config.ID_FIELD]

    updated_coverage_ids = coverage_id_to_content_id_map.keys()
    if not len(updated_coverage_ids):
        # No coverages were updated, no need to update the Planning item or link any content
        return

    # Update the planning item with the latest Assignment information, and link the coverages to the content
    try:
        updated_item = planning_service.patch(planning_id, updates)
    except Exception:
        logger.exception("Failed to update planning with newly linked coverages")
        return

    for coverage in updated_item.get("coverages") or []:
        try:
            coverage_id = coverage["coverage_id"]
            assignment_id = coverage["assigned_to"]["assignment_id"]
        except (KeyError, TypeError):
            # Either ``coverage_id`` or ``assignment_id`` is not defined
            continue

        if assignment_id is None:
            # This coverage has no Assignment, no need to link to content
            continue

        try:
            _link_assignment_and_content(assignment_id, coverage_id, coverage_id_to_content_id_map[coverage_id])
        except Exception as err:
            logger.exception(err)
            logger.error("Failed to link coverage assignment to content")


def before_content_published(_sender: Any, item: Dict[str, Any], updates: Dict[str, Any]):
    """Link content to coverage before publishing"""

    if item.get("assignment_id") is not None:
        # This item is already linked to a coverage
        # no need to continue
        return

    if is_online_version(item):
        # This article has an STTVersion of Nettiuutiset (Online News)
        # and no coverage is to be created or attached to this content
        # no need to continue
        return

    delivery_service = get_resource_service("delivery")
    planning_service = get_resource_service("planning")

    deliveries = delivery_service.get(req=None, lookup={
        "item_id": item.get("uri"),
        "assignment_id": None
    })

    assignment_id = None

    if deliveries.count():
        planning_id = deliveries[0].get("planning_id")
        coverage_id = deliveries[0].get("coverage_id")
    else:
        try:
            topic_id = item["extra"]["stt_topics"]
        except (KeyError, TypeError):
            return

        if not topic_id:
            # A Topic ID was not found, unable to automatically create a coverage
            return

        planning_id = f"urn:newsml:stt.fi:{topic_id}"
        coverage_id = None

    planning = planning_service.find_one(req=None, _id=planning_id)
    if not planning:
        logger.warning("Failed to link content to coverage: Planning item not found", extra=dict(
            content_guid=item.get("guid"),
            planning_id=planning_id,
        ))
        return

    planning_updates = {"coverages": deepcopy(planning.get("coverages") or [])}
    update_planning_item = True
    if coverage_id is not None:
        coverage = next(
            (
                coverage
                for coverage in planning_updates["coverages"]
                if coverage.get("coverage_id") == coverage_id
            ),
            None
        )
        if coverage is None:
            logger.warning("Failed to find coverage in planning item", extra=dict(
                content_guid=item.get("guid"),
                planning_id=planning_id,
                coverage_id=coverage_id,
            ))
            return

        _copy_metadata_from_article_to_coverage(coverage, item)
        _update_coverage_assignment_details(coverage, item)
    else:
        # Set the metadata for the new coverage
        try:
            stt_article_id = item["extra"]["sttidtype_textid"]
            coverage_id = f"ID_TEXT_{stt_article_id}"
        except (KeyError, TypeError):
            logger.error("Failed to find the STT Article ID from the content, unable to continue", extra=dict(
                content_guid=item.get("guid"),
                planning_id=planning_id,
            ))
            return

        existing_coverage = next(
            (
                coverage
                for coverage in planning_updates["coverages"]
                if coverage.get("coverage_id") == coverage_id
            ),
            None
        )
        if existing_coverage:
            # A Coverage ID with STT's Article ID already exists
            # Use that to link this content to
            try:
                coverage_has_assignment = bool(existing_coverage["assigned_to"]["assignment_id"])
            except (KeyError, TypeError):
                coverage_has_assignment = False

            if not coverage_has_assignment:
                # No Assignment currently exists, add ``assigned_to`` details so the Planning module
                # will automatically create one for us
                _copy_metadata_from_article_to_coverage(existing_coverage, item)
                _update_coverage_assignment_details(existing_coverage, item)
            else:
                # An Assignment already exists for this coverage,
                # Add another Assignment for this coverage, and link it to the content
                try:
                    assignment_id = get_resource_service("assignments").post([{
                        "assigned_to": {
                            "desk": (item.get("task") or {}).get("desk"),
                            "state": ASSIGNMENT_WORKFLOW_STATE.COMPLETED,
                        },
                        "planning_item": planning_id,
                        "coverage_item": coverage_id,
                        "planning": deepcopy(existing_coverage.get("planning")),
                        "priority": (
                            item.get("priority") or
                            (existing_coverage.get("assigned_to") or {}).get("priority") or
                            2
                        ),
                        "description_text": planning.get("description_text")
                    }])[0]
                except Exception:
                    logger.exception("Failed to create the new Assignment", extra=dict(
                        content_guid=item.get("guid"),
                        planning_id=planning_id,
                        coverage_id=coverage_id,
                    ))
                    return

                # No need to update Planning item directly, as there are no changes to coverages
                # Only changes to coverage assignments & deliveries (which is held in a different resource collection)
                update_planning_item = False
        else:
            new_coverage = {
                "coverage_id": coverage_id,
                "planning": {"g2_content_type": "text"},
                "news_coverage_status": get_coverage_status_from_cv("ncostat:int"),
                "flags": {},
            }

            _copy_metadata_from_article_to_coverage(new_coverage, item)
            _update_coverage_assignment_details(new_coverage, item)

            # Remove placeholder text coverage and add the new one
            planning_updates["coverages"] = [
                coverage
                for coverage in planning_updates["coverages"]
                if not (coverage.get("flags") or {}).get("placeholder")
            ] + [new_coverage]

    if update_planning_item:
        try:
            updated_planning = planning_service.patch(planning_id, planning_updates)
        except Exception as err:
            logger.exception(err)
            logger.error("Failed to update planning with newly linked coverages")
            return
    else:
        updated_planning = planning_updates
        if post_required(planning, planning):
            # Re-publish the Planning item (if required)
            # This way the updated coverage deliveries will be re-published to subscribers
            update_post_item(planning, planning)

    if assignment_id is None:
        # Assignment ID is not currently known, grab it from the latest Coverage information
        assignment_id = next(
            (
                coverage
                for coverage in updated_planning.get("coverages", [])
                if coverage.get("coverage_id") == coverage_id
            ),
            {}
        ).get("assigned_to", {}).get("assignment_id")
        if not assignment_id:
            logger.error("Failed to get 'assignment_id' of coverage", extra=dict(
                content_guid=item.get("guid"),
                planning_id=planning_id,
                coverage_id=coverage_id,
            ))
            return

    try:
        _link_assignment_and_content(assignment_id, coverage_id, item.get("guid"), True)
    except Exception:
        logger.exception("Failed to link coverage assignment to content", extra=dict(
            content_guid=item.get("guid"),
            planning_id=planning_id,
            coverage_id=coverage_id,
        ))
        return

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

    try:
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
    except Exception:
        logger.exception("Failed to retrieve list of content based on URIs", extra=dict(uris=uris))

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
        "priority": content.get("priority") or coverage["assigned_to"].get("priority") or 2,
        "user": content["task"]["user"],
        "assignor_desk": content["task"]["user"],
        "assignor_user": content["task"]["user"],
    })


def _copy_metadata_from_article_to_coverage(coverage: Dict[str, Any], content: Dict[str, Any]):
    coverage.setdefault("planning", {})
    coverage["planning"]["scheduled"] = content.get("firstpublished") or content.get("versioncreated")

    for field in ["genre", "language", "subject"]:
        if content.get(field):
            coverage["planning"][field] = content[field]

    if content.get("slugline", "").strip():
        coverage["planning"]["slugline"] = content["slugline"].strip()
    elif content.get("headline", "").strip():
        coverage["planning"]["slugline"] = content["headline"].strip()


def _link_assignment_and_content(
    assignment_id: ObjectId,
    coverage_id: str,
    content_id: str,
    skip_archive_update: Optional[bool] = False
):
    """Remove all temporary delivery entries for this coverage and link assignment and content"""

    get_resource_service("delivery").delete_action(lookup={"coverage_id": coverage_id, "assignment_id": None})
    get_resource_service("assignments_link").post([{
        "assignment_id": assignment_id,
        "item_id": content_id,
        "skip_archive_update": skip_archive_update,
        "item_state": CONTENT_STATE.PUBLISHED,
    }])
