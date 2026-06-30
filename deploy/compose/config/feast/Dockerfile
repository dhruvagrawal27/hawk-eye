# Hawk-Eye Feast feature-server sidecar (PLATFORM-2 hosts; DATA owns feature defs).
# Built at image-build time (egress allowed at build); the RUNNING system has no egress.
FROM python:3.12.7-slim

RUN pip install --no-cache-dir "feast==0.40.1" "redis==5.2.1" && \
    apt-get update && apt-get install -y --no-install-recommends curl bash && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /feature_repo
COPY feature_store.yaml example_repo.py ./
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6566
ENTRYPOINT ["/entrypoint.sh"]
