# BACKEND API stub (§3 stub rule). Replaced by the real BACKEND image (CONTEXT.md).
FROM python:3.12.7-slim
RUN pip install --no-cache-dir "fastapi==0.115.6" "uvicorn[standard]==0.32.1" \
    "pydantic==2.10.4" "prometheus-client==0.21.1"
WORKDIR /app
COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
