FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/taxi/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/taxi/app /app/app
COPY apps/taxi/alembic.ini /app/
COPY apps/taxi/alembic /app/alembic
COPY operators/_shared /app/operators/_shared
COPY operators/taxi_partners /app/operators/taxi_partners

EXPOSE 8108

CMD ["uvicorn", "operators.taxi_partners.main:app", "--host", "0.0.0.0", "--port", "8108"]
