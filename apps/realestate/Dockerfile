FROM python:3.11-slim

WORKDIR /app
COPY apps/realestate/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/realestate/app /app/app

ENV ENV=dev APP_PORT=8092

EXPOSE 8092
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8092"]

