FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Food service dependencies
COPY apps/food/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

# Copy Food domain code and this operator entrypoint
COPY apps/food/app /app/app
COPY operators/food_courier /app/operators/food_courier

EXPOSE 8092

CMD ["uvicorn", "operators.food_courier.main:app", "--host", "0.0.0.0", "--port", "8092"]

