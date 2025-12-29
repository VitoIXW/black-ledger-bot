FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/
COPY tests/ /app/tests/

# data dir for sqlite
RUN mkdir -p /data

ENV PYTHONPATH=/app/src

CMD ["python3", "-m", "app.main"]
