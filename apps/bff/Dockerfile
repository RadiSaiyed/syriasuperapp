FROM python:3.11-slim

WORKDIR /app

COPY apps/bff/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/bff /app/apps/bff

ENV APP_HOST=0.0.0.0
ENV APP_PORT=8070

CMD ["python", "-m", "apps.bff.app.main"]

