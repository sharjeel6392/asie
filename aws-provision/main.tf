# Wire everything together
module "network" {
  source = "./modules/network"

  vpc_cidr             = var.vpc_cidr
  public1_subnet_cidr  = var.public1_subnet_cidr
  private1_subnet_cidr = var.private1_subnet_cidr
  az1                  = var.az1

  public2_subnet_cidr  = var.public2_subnet_cidr
  private2_subnet_cidr = var.private2_subnet_cidr
  az2                  = var.az2

  region = var.region
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------------------
# RDS — one shared Postgres instance for airflow_db / mlflow_db / asie_app.
# Private-subnet only; no public endpoint.
# ---------------------------------------------------------------------------
module "rds" {
  source = "./modules/rds"

  vpc_id               = module.network.vpc_id
  private_subnet_ids   = [module.network.private1_subnet_id, module.network.private2_subnet_id]
  private_subnet_cidrs = [var.private1_subnet_cidr, var.private2_subnet_cidr]

  db_name           = var.db_name
  db_username       = var.db_username
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage
  engine_version    = var.db_engine_version
}

# ---------------------------------------------------------------------------
# S3 — single bucket, three logical prefixes (dvc-data/, mlflow-artifacts/,
# models/). Data lands here starting Day 5; the bucket + gateway endpoint
# are provisioned now.
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "platform" {
  bucket = "asie-platform-${data.aws_caller_identity.current.account_id}"

  # Required for `asie.sh down` to actually complete. Without it Terraform
  # errors with BucketNotEmpty -- but only after it has already destroyed RDS
  # and the VPC, since the bucket has no dependency on either. That leaves a
  # half-destroyed stack, which is worse than either finishing or refusing.
  #
  # This deletes every object AND every version (versioning is on below), so
  # the models and DVC data go with it. `asie.sh down` gates on a typed
  # confirmation for exactly this reason, and `asie.sh pause` exists so
  # cost-saving never has to reach for `down`.
  force_destroy = true

  tags = {
    Name = "asie-platform"
  }
}

resource "aws_s3_bucket_versioning" "platform" {
  bucket = aws_s3_bucket.platform.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "platform" {
  bucket = aws_s3_bucket.platform.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "platform" {
  bucket = aws_s3_bucket.platform.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# A failed multipart upload leaves its uploaded parts behind indefinitely.
# They're invisible to `aws s3 ls` but still billed as storage, so on a flaky
# connection -- which is exactly how model/artifact uploads to this bucket
# fail -- they accumulate silently. Nothing here legitimately takes 7 days to
# finish an upload.
resource "aws_s3_bucket_lifecycle_configuration" "platform" {
  bucket = aws_s3_bucket.platform.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    # Applies to the whole bucket. An empty filter is how the provider
    # expresses that for a v2 lifecycle rule.
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  # Model exports became append-only in Day 2 of the GitOps week: each export
  # writes models/<mlflow_run_id>/ and never overwrites, which is what makes a
  # version pointer in git addressable and therefore what makes rollback real
  # (DEPLOYMENT_ARCHITECTURE.md §6.1). The cost of that property is unbounded
  # growth -- roughly 250 MB per model per retrain, on a @daily DAG.
  #
  # 90 days is chosen against the rollback window, not against storage price.
  # Rolling back to a model that has not served since last quarter is not a
  # rollback, it is a re-deploy, and it should go through the promotion gate
  # like anything else. Anything still deployed is far newer than this.
  #
  # NOTE: expiration deletes objects by age regardless of whether a git ref
  # still points at them. If a version pinned in gitops/values/inference.yaml
  # ages out, the initContainer fails on a missing prefix -- loudly, at pod
  # start, rather than silently serving the wrong weights. That is the right
  # failure direction, but it is a real constraint: do not pin a version and
  # then leave it undeployed for three months.
  rule {
    id     = "expire-old-model-versions"
    status = "Enabled"

    filter {
      prefix = "models/"
    }

    expiration {
      days = 90
    }
  }
}

# ---------------------------------------------------------------------------
# ECR — one repo per image asie.sh already builds against.
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "inference" {
  name                 = "asie-inference-repo"
  image_tag_mutability = "MUTABLE"

  # Same reason as the S3 bucket's force_destroy: without this, destroying a
  # repo that still holds images fails, and it fails partway through the
  # teardown rather than up front.
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "asie-inference-repo"
  }
}

resource "aws_ecr_repository" "airflow" {
  name                 = "asie-airflow-repo"
  image_tag_mutability = "MUTABLE"

  # Same reason as the S3 bucket's force_destroy: without this, destroying a
  # repo that still holds images fails, and it fails partway through the
  # teardown rather than up front.
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "asie-airflow-repo"
  }
}

# ghcr.io/mlflow/mlflow ships without psycopg2/boto3 baked in, so a custom
# image (Dockerfile.mlflow) is needed to talk to RDS + S3 — hence a 3rd repo.
resource "aws_ecr_repository" "mlflow" {
  name                 = "asie-mlflow-repo"
  image_tag_mutability = "MUTABLE"

  # Same reason as the S3 bucket's force_destroy: without this, destroying a
  # repo that still holds images fails, and it fails partway through the
  # teardown rather than up front.
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "asie-mlflow-repo"
  }
}

resource "aws_ecr_lifecycle_policy" "inference_expire_untagged" {
  repository = aws_ecr_repository.inference.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "airflow_expire_untagged" {
  repository = aws_ecr_repository.airflow.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "mlflow_expire_untagged" {
  repository = aws_ecr_repository.mlflow.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after 14 days"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = 14
      }
      action = { type = "expire" }
    }]
  })
}