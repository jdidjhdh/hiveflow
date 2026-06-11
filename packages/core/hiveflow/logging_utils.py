import logging


class TraceLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        trace_id = kwargs.pop("trace_id", self.extra.get("trace_id", "-"))
        return f"[trace={trace_id}] {msg}", kwargs


def get_trace_logger(name: str) -> TraceLogger:
    logger = logging.getLogger(name)
    return TraceLogger(logger, {"trace_id": "-"})
