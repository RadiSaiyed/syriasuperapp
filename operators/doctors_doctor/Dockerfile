FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/doctors/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/superapp_shared/superapp_shared /app/superapp_shared
COPY apps/doctors/app /app/app
COPY operators/doctors_doctor /app/operators/doctors_doctor

EXPOSE 8103

CMD ["uvicorn", "operators.doctors_doctor.main:app", "--host", "0.0.0.0", "--port", "8103"]

