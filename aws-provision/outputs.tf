output "vpc_id" {
  value = module.network.vpc_id
}

output "public1_subnet_id" {
  value = module.network.public1_subnet_id
}

output "private1_subnet_id" {
  value = module.network.private1_subnet_id
}

output "public2_subnet_id" {
  value = module.network.public2_subnet_id
}

output "private2_subnet_id" {
  value = module.network.private2_subnet_id
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "rds_port" {
  value = module.rds.port
}

output "rds_db_name" {
  value = module.rds.db_name
}

output "rds_master_username" {
  value = module.rds.master_username
}

output "rds_master_password" {
  value     = module.rds.master_password
  sensitive = true
}

output "s3_bucket_name" {
  value = aws_s3_bucket.platform.bucket
}

output "ecr_inference_repo_url" {
  value = aws_ecr_repository.inference.repository_url
}

output "ecr_airflow_repo_url" {
  value = aws_ecr_repository.airflow.repository_url
}
