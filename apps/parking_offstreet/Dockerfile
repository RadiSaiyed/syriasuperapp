FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/parking_offstreet/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared

COPY apps/parking_offstreet/app /app/app
COPY apps/parking_offstreet/alembic.ini /app/
COPY apps/parking_offstreet/alembic /app/alembic

COPY apps/parking_offstreet/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
