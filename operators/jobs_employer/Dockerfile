FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/jobs/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/jobs/app /app/app
COPY operators/_shared /app/operators/_shared
COPY operators/jobs_employer /app/operators/jobs_employer

EXPOSE 8107

CMD ["uvicorn", "operators.jobs_employer.main:app", "--host", "0.0.0.0", "--port", "8107"]
