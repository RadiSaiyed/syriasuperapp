FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY apps/realestate/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

COPY apps/realestate/app /app/app
COPY apps/realestate/alembic.ini /app/
COPY apps/realestate/alembic /app/alembic

COPY apps/realestate/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8092
ENTRYPOINT ["/app/entrypoint.sh"]
