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
    def __init__(self,*, fmt_keys: dict[str, str] | None= None):
        super().__init__()
        # fmt_keys = {
        #     'level': 'levelname',
        #     'message': 'message',
        #     'timestamp': 'timestamp',
        #     'logger': 'name',
        #     'module': 'module',
        #     'function': 'funcName',
        #     'line': 'lineno',
        #     'thread_name': 'threadName'
        # } <- What's in the below property
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

        print(f"{fmt_keys=}")

    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default= str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        # print(f"{record=}")
        # print(f"{record.__dict__}") <- has keys name, msg, args(?), levelname, levelno, pathname, 
        #   filename, module, exc_info, exc_text, stack_info, lineno, funcName, created, msecs,
        #   relativeCreated, thread, threadname, processName, process, taskName
        timestamp = (
            dt.datetime
              .fromtimestamp(record.created)
              .astimezone()
              .strftime("%Y-%m-%d %H:%M:%S.%f %Z")
        )
        always_fields = {
            "message": record.getMessage(),
            "timestamp": timestamp
        }

        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info).splitlines()

        remote_exc = getattr(record, "_remote_exc_info", None)
        if record.exc_info is None and remote_exc:
            always_fields["exc_info"] = str(remote_exc).splitlines()

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {}
        for key, val in self.fmt_keys.items():
            if val in always_fields and always_fields[val] is not None:
                message[key] = always_fields[val]
            else:
                message[key] = getattr(record, val)

        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in STANDARD_ATTRS and not k.startswith("_")
            and v is not None
        }
        if extras:
            message["extra"] = extras

        return message
