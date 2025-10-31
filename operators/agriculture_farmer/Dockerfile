FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/agriculture/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/agriculture/app /app/app
COPY operators/_shared /app/operators/_shared
COPY operators/agriculture_farmer /app/operators/agriculture_farmer

EXPOSE 8100

CMD ["uvicorn", "operators.agriculture_farmer.main:app", "--host", "0.0.0.0", "--port", "8100"]
