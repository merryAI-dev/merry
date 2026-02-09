FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Minimal deps for our current job types (xlsx + pdf text extraction).
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt

# Copy only what the worker needs (avoid web/node_modules bloat).
COPY agent /app/agent
COPY shared /app/shared
COPY scripts /app/scripts
COPY discovery_service /app/discovery_service
COPY dolphin_service /app/dolphin_service
COPY data /app/data
COPY worker /app/worker

CMD ["python", "-m", "worker.main"]

