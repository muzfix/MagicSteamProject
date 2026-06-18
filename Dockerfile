FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as non-root — if the app is ever compromised, the attacker gets a locked
# account with no shell and no write access outside /app, not root.
RUN adduser --disabled-password --gecos "" --no-create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Use Gunicorn + UvicornWorker (config in gunicorn.conf.py).
# Override CMD with plain uvicorn for local docker-compose dev if needed.
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
