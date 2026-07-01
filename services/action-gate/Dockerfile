# Hawk-Eye L6.5 action-gate (privileged-action interdiction PDP). Source systems (pam-shim today;
# CyberArk/CBS/IGA in prod) call /api/v1/actions/evaluate BEFORE a privileged staff action proceeds.
FROM python:3.12.7-slim
WORKDIR /svc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agsvc ./agsvc
EXPOSE 8096
CMD ["uvicorn", "agsvc.main:app", "--host", "0.0.0.0", "--port", "8096"]
