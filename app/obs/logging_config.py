# app/obs/logging_config.py
import logging, os, sys, json, time

class JsonFormatter(logging.Formatter):
    def format(self, record):
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
