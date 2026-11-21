FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Install dependencies first: this layer is cached until pyproject.toml changes.
COPY pyproject.toml README.md ./
COPY forecast ./forecast
RUN pip install --no-cache-dir .

# Bake a first model into the image, so a fresh container can serve straight away.
RUN python -m forecast.train /app/data/alarms.csv /app/models/model.json

# Don't run as root.
RUN useradd --uid 10001 --no-create-home app && chown -R app /app
USER 10001

ENV MODEL_PATH=/app/models/model.json PORT=8080
EXPOSE 8080
# Cloud Run sets $PORT; everywhere else it defaults to 8080.
CMD ["sh", "-c", "uvicorn forecast.api:app --host 0.0.0.0 --port ${PORT}"]
