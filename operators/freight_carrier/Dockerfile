FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/freight/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/freight/app /app/app
COPY operators/freight_carrier /app/operators/freight_carrier

EXPOSE 8106

CMD ["uvicorn", "operators.freight_carrier.main:app", "--host", "0.0.0.0", "--port", "8106"]

