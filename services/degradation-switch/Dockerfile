# Hawk-Eye degradation switch (PLATFORM-4/28). REAL graceful-degradation control plane.
FROM python:3.12.7-slim
WORKDIR /svc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY dswitch ./dswitch
EXPOSE 8092
CMD ["uvicorn", "dswitch.main:app", "--host", "0.0.0.0", "--port", "8092"]
