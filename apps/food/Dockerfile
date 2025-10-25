FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/food/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

COPY apps/food/app /app/app
COPY apps/food/alembic.ini /app/
COPY apps/food/alembic /app/alembic

COPY apps/food/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
