import logging

from pptmaker.security.secrets import _redact_value, redact_text


class RedactKeysFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.args = _redact_value(record.args)
        record.msg = redact_text(record.getMessage())
        record.args = ()
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(item, RedactKeysFilter) for item in handler.filters):
            handler.addFilter(RedactKeysFilter())
    for name in ("httpx", "httpcore", "openai", "pptmaker.research.bocha"):
        logging.getLogger(name).setLevel(logging.WARNING)
