# app/worker.py
import os, time, logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [worker] %(message)s",
)
log = logging.getLogger("worker")

def main():
    log.info("Worker online. DB_PATH=%s  REDIS_URL=%s",
             os.getenv("DB_PATH"), os.getenv("REDIS_URL"))
    # TODO: put real background jobs here (queue consumers, schedulers, etc.)
    while True:
        log.info("heartbeat")
        time.sleep(30)

if __name__ == "__main__":
    main()
