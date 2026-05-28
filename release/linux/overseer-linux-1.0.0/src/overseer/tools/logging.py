import logging, json, hashlib
logger = logging.getLogger(__name__)

class LogsManager:
    def __init__(self):
        self._run_id: int | None = None
        self._logged_keys: set[tuple] = set()

    def set_run_id(self, run_id: int):
        self._run_id = run_id
        self._logged_keys.clear()

def _log_exception(self, level: int, msg: str, *, extra: dict | None = None, exc_info = None, key: tuple | None = None):
    extra = extra or {}

    if key is None:
        # Build a stable fingerprint.
        # Keep it cheap and deterministic; don't include huge objects.
        exc_part = None
        if exc_info:
            # exc_info can be True or a tuple; normalize
            if exc_info is True:
                exc_part = ("exc",)  # best effort; record current exception exists
            else:
                et, ev, _tb = exc_info
                exc_part = (getattr(et, "__name__", str(et)), str(ev))

        extra_part = json.dumps(extra, sort_keys=True, default=str)
        raw = f"{level}|{msg}|{extra_part}|{exc_part}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        key = (self._sim_run_id, digest)

    if key in self._logged_plot_keys:
        return
    self._logged_plot_keys.add(key)

    logger.log(level, msg, extra=extra, exc_info=exc_info)

