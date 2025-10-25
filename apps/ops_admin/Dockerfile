FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Use server-only requirements (no desktop bindings)
COPY apps/ops_admin/requirements.server.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/ops_admin/app /app/app

# Default port; can be overridden by env
ENV APP_PORT=8099
EXPOSE 8099

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099"]
