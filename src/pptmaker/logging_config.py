import logging

from pptmaker.security.secrets import _redact_value, redact_text


class RedactKeysFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(str(record.msg))
        record.args = _redact_value(record.args)
        return True


def configure_logging() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(item, RedactKeysFilter) for item in handler.filters):
            handler.addFilter(RedactKeysFilter())
    for name in ("httpx", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)
