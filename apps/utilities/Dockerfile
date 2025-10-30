FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/utilities/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared libraries
COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY libs/superapp_ai/superapp_ai /app/superapp_ai

COPY apps/utilities/app /app/app
COPY apps/utilities/alembic.ini /app/
COPY apps/utilities/alembic /app/alembic

COPY apps/utilities/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
