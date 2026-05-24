import json
import datetime as dt
import logging
from typing import override

STANDARD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno",
    "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName",
    "processName", "process", "message",
}

class JSONFormatter(logging.Formatter):
    # fmt_keys are specified in the logging_config.yml file.
    def __init__(self,*, fmt_keys: dict[str, str] | None= None):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

        print(f"{fmt_keys=}")

    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default= str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        timestamp = (
            dt.datetime
              .fromtimestamp(record.created)
              .astimezone()
              .strftime("%Y-%m-%d %H:%M:%S.%f %Z")
        )

        message = {
            "message": record.getMessage(),
            "timestamp": timestamp
        }

        if record.exc_info is not None:
            message["exc_info"] = self.formatException(record.exc_info).splitlines()

        remote_exc = getattr(record, "_remote_exc_info", None)
        if record.exc_info is None and remote_exc:
            message["exc_info"] = str(remote_exc).splitlines()

        if record.stack_info is not None:
            message["stack_info"] = self.formatStack(record.stack_info)

        specially_computed_fields = {"message", "timestamp", "exc_info", "stack_info"}
        for fmt_name, source_name in self.fmt_keys.items():
            if source_name in specially_computed_fields:
                continue
            message[fmt_name] = getattr(record, source_name, None)

        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in STANDARD_ATTRS and not k.startswith("_")
            and v is not None
        }
        if extras:
            message["extra"] = extras

        return message


