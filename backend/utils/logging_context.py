import contextvars
import logging

# Context variables for logging metadata (default to "-" if not set)
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="-")
document_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("document_id", default="-")
route_var: contextvars.ContextVar[str] = contextvars.ContextVar("route", default="-")

class CorrelationFilter(logging.Filter):
    """
    Logging filter that injects the current request correlation context
    (request_id, user_id, document_id, route) into each log record.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.document_id = document_id_var.get()
        record.route = route_var.get()
        return True

def clear_context() -> None:
    """Resets all context variables to their default values."""
    request_id_var.set("-")
    user_id_var.set("-")
    document_id_var.set("-")
    route_var.set("-")
