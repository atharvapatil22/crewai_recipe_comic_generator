import os
from redis import Redis
from rq import Queue

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT,password=REDIS_PASSWORD)
preprocess_queue = Queue("preprocess", connection=redis_conn)
comicgen_queue = Queue("comicgen", connection=redis_conn)