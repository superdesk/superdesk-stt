from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Formatted:
    rows: List[Dict[str, Any]]


def format_paivalista_for_export(items):
    rows = items or []
    # TODO: sorting etc. if needed
    # item keys are:
    # ['type',
    # 'occur_status',
    # 'dates',
    # 'calendars',
    # 'state',
    # 'language',
    # 'languages',
    # 'place',
    # 'files',
    # '_time_to_be_confirmed',
    # 'slugline',
    # 'name',
    # 'definition_short',
    # 'location',
    # 'links',
    # '_updated',
    # '_created',
    # 'guid',
    # 'original_creator',
    # 'firstcreated',
    # 'versioncreated',
    # '_planning_schedule',
    # '_etag',
    # 'lock_action',
    # 'lock_user',
    # 'lock_time',
    # 'lock_session',
    # 'state_reason',
    # 'pubstatus',
    # 'actioned_date',
    # 'firstpublished',
    # '_id',
    # '_type',
    # 'plannings',
    # 'coverages',
    # 'published_archive_items',
    # 'assignees',
    # 'text_assignees',
    # 'contacts',
    # 'description_text',
    # 'schedule']

    return {"rows": rows}
