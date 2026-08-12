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

# ---------------------------------------------------------------------------
# ECR — one repo per image asie.sh already builds against.
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "inference" {
  name                 = "asie-inference-repo"
  image_tag_mutability = "MUTABLE"

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