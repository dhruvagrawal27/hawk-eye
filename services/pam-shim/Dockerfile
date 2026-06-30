# Hawk-Eye PAM shim (PLATFORM-15, MOCK). Real swap: CyberArk / BeyondTrust.
FROM python:3.12.7-slim
WORKDIR /svc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pamsvc ./pamsvc
EXPOSE 8091
CMD ["uvicorn", "pamsvc.main:app", "--host", "0.0.0.0", "--port", "8091"]
