import logging
from flask import Flask
from superdesk.http_proxy import HTTPProxy, register_http_proxy


logger = logging.getLogger(__name__)


def init_app(app: Flask) -> None:
    stt_ai_url = app.config.get("STT_AI_URL")
    if stt_ai_url is None:
        logger.warning("'STT_AI_URL' config not set, HTTP Proxy will not be available")
        return

    register_http_proxy(
        app,
        HTTPProxy(
            endpoint_name="stt.ai_proxy",
            internal_url="stt/ai",
            external_url=stt_ai_url,
        ),
    )
