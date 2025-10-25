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
# Food domain expects package name 'app'
COPY apps/food/app /app/app
COPY operators/food_operator /app/operators/food_operator

EXPOSE 8091

CMD ["uvicorn", "operators.food_operator.main:app", "--host", "0.0.0.0", "--port", "8091"]

