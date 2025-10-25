FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/utilities/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Include shared libraries
COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY libs/superapp_ai/superapp_ai /app/superapp_ai

COPY apps/utilities/app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8084"]
