FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/jobs/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

COPY apps/jobs/app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8087"]
