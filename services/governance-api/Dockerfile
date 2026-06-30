# Hawk-Eye governance-api (PLATFORM-32/35/41). Build context = REPO ROOT so it can bundle
# the shared governance models + go-live resolver (single source of truth, no duplication).
#   docker build -f services/governance-api/Dockerfile .
FROM python:3.12.7-slim
WORKDIR /svc
COPY services/governance-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# shared modules on the path (imported as `models`, `checklist`, `seed`)
COPY governance/db/models.py governance/db/seed.py /svc/
COPY governance/go-live/checklist.py /svc/
COPY services/governance-api/govapi /svc/govapi
ENV PYTHONPATH=/svc
EXPOSE 8093
CMD ["uvicorn", "govapi.main:app", "--host", "0.0.0.0", "--port", "8093"]
