# Container image for the scheduled corpus ingestion (PR8). Runs
# scripts/ingest_corpus.py once per scheduled invocation on Fargate.
#
# Build & push (example):
#   docker build -t rag-aws-ingest -f backend/ingestion.Dockerfile .
#   docker tag rag-aws-ingest <acct>.dkr.ecr.eu-west-1.amazonaws.com/rag-aws-ingest:latest
#   docker push <acct>.dkr.ecr.eu-west-1.amazonaws.com/rag-aws-ingest:latest
FROM python:3.13-slim

# git is needed to shallow-clone the awsdocs repos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir boto3

# Preserve the layout scripts/ingest_corpus.py expects (backend/src on sys.path).
COPY backend/src/rag_aws ./backend/src/rag_aws
COPY scripts/ingest_corpus.py ./scripts/ingest_corpus.py

# Bucket comes from PROJECT_BUCKET_NAME; extra flags can be appended as CMD.
ENTRYPOINT ["python", "/app/scripts/ingest_corpus.py"]
CMD []
