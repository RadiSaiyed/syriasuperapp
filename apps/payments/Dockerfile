FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/payments/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

# App code and Alembic config
COPY apps/payments/app /app/app
COPY apps/payments/alembic.ini /app/
COPY apps/payments/alembic /app/alembic

COPY apps/payments/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
