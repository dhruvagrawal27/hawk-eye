# Hawk-Eye CPU serving stub (KServe v2). PLATFORM-3 / §3 stub rule.
# ML swaps the real Triton image (deploy/versions.bom.yaml :: stack.triton).
FROM python:3.12.7-slim
RUN pip install --no-cache-dir "fastapi==0.115.6" "uvicorn[standard]==0.32.1" \
    "pydantic==2.10.4" "prometheus-client==0.21.1"
WORKDIR /app
COPY app.py .
EXPOSE 8001
# v2 protocol on :8001 (CONTEXT.md §7). Real Triton serves the same contract.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
