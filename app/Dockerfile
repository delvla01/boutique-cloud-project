# Slim base image keeps cold starts fast and the image small.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install deps first so this layer caches when only app code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Cloud Run sets $PORT; gunicorn binds to it. Two workers is plenty for the
# instance sizes we'll use, and threads handle concurrent requests cheaply.
CMD exec gunicorn --bind :$PORT --workers 2 --threads 8 --timeout 0 app:app
