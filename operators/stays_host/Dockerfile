FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/stays/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/stays/app /app/app
COPY operators/stays_host /app/operators/stays_host

EXPOSE 8101

CMD ["uvicorn", "operators.stays_host.main:app", "--host", "0.0.0.0", "--port", "8101"]

