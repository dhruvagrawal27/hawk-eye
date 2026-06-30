# Hawk-Eye HITL natural-justice gate (PLATFORM-37). Build context = REPO ROOT (bundles the
# shared governance models for the DPIA binding).  docker build -f services/hitl-gate/Dockerfile .
FROM python:3.12.7-slim
WORKDIR /svc
COPY services/hitl-gate/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY governance/db/models.py /svc/
COPY services/hitl-gate/hitlsvc /svc/hitlsvc
ENV PYTHONPATH=/svc
EXPOSE 8094
CMD ["uvicorn", "hitlsvc.main:app", "--host", "0.0.0.0", "--port", "8094"]
