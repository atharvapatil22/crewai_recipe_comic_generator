FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY workers/comicgen/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire shared folder
COPY shared/ /app/shared/

# Copy the worker code
COPY workers/comicgen/ /app/

CMD rq worker --verbose -u redis://:$REDIS_PASSWORD@$REDIS_HOST:$REDIS_PORT comicgen
