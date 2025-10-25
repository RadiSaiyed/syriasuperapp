FROM python:3.11-slim
WORKDIR /app
COPY apps/ai_gateway/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
# Include shared library (superapp_shared)
COPY libs/superapp_shared/superapp_shared /app/superapp_shared

COPY apps/ai_gateway /app/apps/ai_gateway
ENV APP_PORT=8099
EXPOSE 8099
CMD ["python", "-m", "apps.ai_gateway.app.main"]
