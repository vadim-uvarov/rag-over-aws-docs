# Get the bucket name and queue URL from terraform first:
  cd terraform/prod
  BUCKET=$(terraform output -raw bucket_name)
  QUEUE_URL=$(terraform output -raw etl_ingest_queue_url)
  cd ../..

  # real sync
  uv run python scripts/ingestion/ingest_corpus.py --bucket $BUCKET