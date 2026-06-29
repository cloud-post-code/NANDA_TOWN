FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY skills/ ./skills/

ENV PYTHONUNBUFFERED=1

CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
