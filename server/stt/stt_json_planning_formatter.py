from superdesk import get_resource_service
from planning.output_formatters import JsonPlanningFormatter


class STTJsonPlanningFormatter(JsonPlanningFormatter):
    name = "STT JSON Planning"
    type = "stt_json_planning"

    CATEGORY_QCODE_NHUB_MAP = {
        "3": {
            "name": "Kotimaa",
            "agenda_id": "673f47881562ef05527e195a",
            "calendar_qcode": "kotimaa",
        },
        "4": {
            "name": "Kulttuuri",
            "agenda_id": "673f478f2c95fe4cab8ee67e4",
            "calendar_qcode": "kulttuuri",
        },
        "9": {
            "name": "Politiikka",
            "agenda_id": "673f47a1f16a90a38481291f",
            "calendar_qcode": "politiikka",
        },
        "11": {
            "name": "Talous",
            "agenda_id": "673f47a914ae7505c4ba6138",
            "calendar_qcode": "talous",
        },
        "14": {
            "name": "Ulkomaat",
            "agenda_id": "673f47b114ae7505c4ba613a",
            "calendar_qcode": "ulkomaat",
        },
        "16": {
            "name": "Urheilu",
            "agenda_id": "673f47ba1562ef05527e195c",
            "calendar_qcode": "urheilu",
        },
        "not_sports": {
            "name": "Muut kuin urheilu",
            "agenda_id": "673f47982c95fe4cab8ee67e",
            "calendar_qcode": "muutkuinurheilu",
        },
    }

    def __init__(self):
        super().__init__()
        self.format_type = "stt_json_planning"

    def update_stt_urgency(self, item):
        priority = item.get("priority", 0)

        if priority == 1:
            qcode = "stturgency-1"
        elif priority == 2 or priority == 3:
            # Special case where qcode 2 and 3 mapped to value of qcode 2 to NH
            qcode = "stturgency-2"
        elif priority == 4:
            qcode = "stturgency-4"
        else:
            qcode = "stturgency-5"

        vocabulary_items = get_resource_service("vocabularies").get_items("stturgency")

        stturgency_item = None
        for vocab_item in vocabulary_items:
            if vocab_item.get("qcode") == qcode:
                stturgency_item = vocab_item
                break

        if stturgency_item:
            item.setdefault("subject", [])
            item["subject"] = [
                subj for subj in item["subject"] if subj.get("scheme") != "stturgency"
            ]
            item["subject"].append(
                {
                    "name": stturgency_item["name"],
                    "qcode": qcode,
                    "scheme": "stturgency",
                }
            )

    def exclude_internal_planning_fields(self, item):
        if "internal_note" in item:
            del item["internal_note"]
        if "subject" in item:
            item["subject"] = [
                subject
                for subject in item["subject"]
                if subject.get("scheme") != "sttcheckedby"
            ]

    def exclude_internal_coverage_fields(self, item):
        if not item.get("coverages"):
            return

        exclude_fields = [
            "headline",
            "location",
            "sttpicturewhatabout",
            "sttpicturewhatisphotographed",
            "internal_note",
            "sttdoesphotographerknow",
            "sttpictureregistrationok",
            "sttregistrationinfo",
            "sttpicturecategory",
            "sttpictureheadlinefi",
            "sttpicturecaptionfi",
            "sttpictureinstructionsfi",
            "sttpicturekeywordsfi",
            "sttpictureheadlineen",
            "sttpicturecaptionen",
            "sttpictureinstructionsen",
            "sttpicturekeywordsen",
            "sttpictureinvoiced",
        ]

        for coverage in item["coverages"]:
            planning = coverage.get("planning")
            if not planning:
                continue

            # First remove direct attributes in the planning obj
            for field in exclude_fields:
                if field in planning:
                    del planning[field]

            # Then filter out internal fields from the fields array
            if "fields" in planning:
                planning["fields"] = [
                    field
                    for field in planning["fields"]
                    if field.get("field") not in exclude_fields
                ]

            # Then filter out internal fields from the subjects array
            if "subject" in planning:
                planning["subject"] = [
                    field
                    for field in planning["subject"]
                    if field.get("scheme") not in exclude_fields
                ]

    def map_agenda_output(self, item):
        anpa_category = item.get("anpa_category", [])
        agendas = []
        for category in anpa_category:
            qcode = category.get("qcode")
            if qcode in self.CATEGORY_QCODE_NHUB_MAP:
                category_qcode_entry = self.CATEGORY_QCODE_NHUB_MAP[qcode]
                agendas.append(
                    {
                        "_id": category_qcode_entry["agenda_id"],
                        "name": category_qcode_entry["name"],
                    }
                )
            else:
                name = category.get("name", "")
                sanitized = name.lower().replace(" ", "")
                agendas.append({"_id": sanitized, "name": name})

        has_non_sport = any(
            category.get("name") != "Urheilu" for category in anpa_category
        )
        if has_non_sport:
            not_sports = self.CATEGORY_QCODE_NHUB_MAP.get("not_sports")
            if not_sports:
                agendas.append(
                    {"_id": not_sports["agenda_id"], "name": not_sports["name"]}
                )
        item["agendas"] = agendas

    async def _format_item(self, item, subscribers: list[dict] | None = None):
        await super()._format_item(item)
        self.update_stt_urgency(item)
        self.exclude_internal_planning_fields(item)
        self.exclude_internal_coverage_fields(item)
        self.map_agenda_output(item)

        return item
