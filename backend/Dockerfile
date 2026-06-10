# Container image for the Lambdas (ETL process/dispatch and the query API all
# share this image; the function's image_config.command selects the handler).
#
# Build & push (example):
#   aws ecr get-login-password --region eu-west-1 | docker login --username AWS \
#     --password-stdin <acct>.dkr.ecr.eu-west-1.amazonaws.com
#   docker build -t rag-aws-etl -f backend/Dockerfile .
#   docker tag rag-aws-etl <acct>.dkr.ecr.eu-west-1.amazonaws.com/rag-aws-etl:latest
#   docker push <acct>.dkr.ecr.eu-west-1.amazonaws.com/rag-aws-etl:latest
FROM public.ecr.aws/lambda/python:3.13

# Install the backend dependencies needed at runtime.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    boto3 \
    "llama-index-core" \
    tiktoken \
    lancedb \
    pyarrow \
    langchain-aws \
    langfuse

# Ship the package source onto the Lambda runtime path.
COPY backend/src/rag_aws ${LAMBDA_TASK_ROOT}/rag_aws

# Default handler; overridden per-function via image_config.command in Terraform.
CMD ["rag_aws.etl.handlers.process.handler"]
