from superdesk import get_resource_service
from planning.output_formatters import JsonPlanningFormatter


class STTJsonPlanningFormatter(JsonPlanningFormatter):
    name = "STT JSON Planning"
    type = "stt_json_planning"

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

    async def _format_item(self, item, subscribers: list[dict] | None = None):
        await super()._format_item(item)
        self.update_stt_urgency(item)

        return item
