import logging
from quart_babel import lazy_gettext

logger = logging.getLogger(__name__)


def set_language_fi(item, **kwargs):
    """A simple macro that sets the language field to 'fi'."""
    item["language"] = "fi"
    logger.info("Language set to 'fi' for item %s", item.get("_id"))
    return item


# Macro registration details
name = "Set Language to Finnish"
label = lazy_gettext("Set Language to Finnish")
callback = set_language_fi
access_type = "backend"
action_type = "direct"
