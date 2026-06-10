# ECR repository for the project's single Lambda container image. The ETL
# process/dispatch steps and the query API all run the *same* image; which
# handler executes is selected per-function via image_config.command. Keeping
# one image keeps the build and lifecycle management simple.
#
# This lives in the bootstrap stack (not the prod stack) because the repository
# must already exist before CI can build and push the image: the prod stack's
# Lambda functions reference an image by tag, so a deploy that built the prod
# stack and the image together would be a chicken-and-egg problem.
resource "aws_ecr_repository" "lambda" {
  name = "rag-aws-etl" # Referenced by the Dockerfile build docs and the deploy workflow.

  # CI pushes immutable, SHA-tagged images so a given tag always resolves to the
  # exact bytes that were deployed; tags can never be silently overwritten.
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

# Bound the repository's growth: drop dangling untagged layers quickly and keep
# only a small window of recent tagged images for rollbacks.
resource "aws_ecr_lifecycle_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only the 10 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      },
    ]
  })
}
