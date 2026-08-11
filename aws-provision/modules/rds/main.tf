# Master password — generated, never hardcoded. Read it back with
# `terraform output -raw rds_master_password` when wiring up Airflow/MLflow (Day 4).
resource "random_password" "db_master" {
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "asie" {
  name       = "asie-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "asie-db-subnet-group"
  }
}

# Postgres reachable only from the private subnets (where EKS nodes and,
# later, RDS-consuming pods live). No public endpoint, no exceptions.
resource "aws_security_group" "rds" {
  name        = "asie-rds-sg"
  description = "Allow Postgres (5432) from ASIE's private subnets only"
  vpc_id      = var.vpc_id

  ingress {
    description = "Postgres from private subnets"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.private_subnet_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "asie-rds-sg"
  }
}

# One shared instance for airflow_db / mlflow_db / asie_app — none of them
# need to scale independently yet. Only `db_name` (asie_app) exists at
# creation; airflow_db and mlflow_db get created from inside the VPC on
# Day 4, since this instance has no public endpoint to reach from outside.
resource "aws_db_instance" "asie" {
  identifier     = "asie-db"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_master.result

  db_subnet_group_name   = aws_db_subnet_group.asie.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az                = false
  publicly_accessible     = false
  backup_retention_period = 1
  skip_final_snapshot     = true
  deletion_protection     = false

  tags = {
    Name = "asie-db"
  }
}
