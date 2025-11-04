from superdesk import get_resource_service
from planning.output_formatters import JsonEventFormatter


class STTJsonEventFormatter(JsonEventFormatter):
    name = "STT JSON Event"
    type = "stt_json_event"

    def __init__(self):
        super().__init__()
        self.format_type = "stt_json_event"

    def map_calendar_output(self, item):
        anpa_category = item.get("anpa_category", [])
        calendars = []

        if not anpa_category:
            item["calendars"] = calendars
            return

        vocabulary_items = get_resource_service("vocabularies").get_items("categories")
        vocabulary_map = {vocab["qcode"]: vocab for vocab in vocabulary_items}

        for category in anpa_category:
            vocab = vocabulary_map.get(category["qcode"])
            if vocab:
                name = vocab.get("name", "")
                if name:
                    calendars.append(
                        {
                            "is_active": True,
                            "qcode": name.lower().replace(" ", ""),
                            "name": name,
                        }
                    )

        has_non_sport = any(
            vocab.get("name") != "Urheilu"
            for category in anpa_category
            if (vocab := vocabulary_map.get(category["qcode"]))
        )
        if has_non_sport:
            calendars.append(
                {
                    "is_active": True,
                    "qcode": "muutkuinurheilu",
                    "name": "Muut kuin urheilu",
                }
            )

        item["calendars"] = calendars

    async def _format_item(self, item, subscribers: list[dict] | None = None):
        await super()._format_item(item)
        self.map_calendar_output(item)

        return item
