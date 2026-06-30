# Hawk-Eye TEE-attestation mock (PLATFORM-14). MOCK confidential-compute attestation.
FROM python:3.12.7-slim
WORKDIR /svc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY teesvc ./teesvc
EXPOSE 8090
CMD ["uvicorn", "teesvc.main:app", "--host", "0.0.0.0", "--port", "8090"]
