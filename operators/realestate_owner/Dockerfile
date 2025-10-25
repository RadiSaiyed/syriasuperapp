FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/realestate/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/realestate/app /app/app
COPY operators/realestate_owner /app/operators/realestate_owner

EXPOSE 8102

CMD ["uvicorn", "operators.realestate_owner.main:app", "--host", "0.0.0.0", "--port", "8102"]

