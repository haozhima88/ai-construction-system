FROM python:3.12-slim

WORKDIR /app
COPY platform_db/requirements.txt /app/platform_db/requirements.txt
RUN pip install --no-cache-dir -r /app/platform_db/requirements.txt
COPY platform_db /app/platform_db

ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["sh", "-c", "alembic -c /app/platform_db/alembic.ini upgrade head && python -m platform_db.bootstrap && uvicorn platform_db.api:app --host 0.0.0.0 --port 8000"]
