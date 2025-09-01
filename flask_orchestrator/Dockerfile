FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY flask_orchestrator/requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire shared folder
COPY shared/ /app/shared/

# Copy flask_orchestrator files
COPY flask_orchestrator/app.py /app/app.py
COPY flask_orchestrator/routes.py /app/routes.py

EXPOSE 5000

CMD ["python", "app.py"]