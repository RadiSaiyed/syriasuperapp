FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Taxi service dependencies
COPY apps/taxi/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

# Copy Taxi domain code and this operator entrypoint
COPY apps/taxi/app /app/app
COPY apps/taxi/alembic.ini /app/
COPY apps/taxi/alembic /app/alembic
COPY operators/taxi_driver /app/operators/taxi_driver

EXPOSE 8083

CMD ["uvicorn", "operators.taxi_driver.main:app", "--host", "0.0.0.0", "--port", "8083"]
