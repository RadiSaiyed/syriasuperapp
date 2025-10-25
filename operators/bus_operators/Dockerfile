FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Bus service dependencies
COPY apps/bus/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

# Copy Bus domain code and this operator entrypoint
COPY apps/bus/app /app/app
COPY operators/bus_operators /app/operators/bus_operators

EXPOSE 8085

CMD ["uvicorn", "operators.bus_operators.main:app", "--host", "0.0.0.0", "--port", "8085"]

