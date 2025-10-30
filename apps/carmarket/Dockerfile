FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/carmarket/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
# Include shared libraries
COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY libs/superapp_ai/superapp_ai /app/superapp_ai

COPY apps/carmarket/app /app/app
COPY apps/carmarket/alembic.ini /app/
COPY apps/carmarket/alembic /app/alembic

COPY apps/carmarket/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
