FROM python:3.11-slim

WORKDIR /app

ARG INCLUDE_DEV=false

COPY backend/requirements.txt /tmp/requirements.txt
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    if [ "$INCLUDE_DEV" = "true" ]; then \
        pip install --no-cache-dir -r /tmp/requirements-dev.txt; \
    fi

COPY backend/ ./backend/
COPY shared/ ./shared/

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
