FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/payments/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/payments/app /app/app
COPY operators/_shared /app/operators/_shared
COPY apps/payments/alembic.ini /app/
COPY apps/payments/alembic /app/alembic
COPY operators/payments_merchant_api /app/operators/payments_merchant_api

EXPOSE 8109

CMD ["uvicorn", "operators.payments_merchant_api.main:app", "--host", "0.0.0.0", "--port", "8109"]
