output "endpoint" {
  value = aws_db_instance.asie.address
}

output "port" {
  value = aws_db_instance.asie.port
}

output "db_name" {
  value = aws_db_instance.asie.db_name
}

output "master_username" {
  value = aws_db_instance.asie.username
}

output "master_password" {
  value     = random_password.db_master.result
  sensitive = true
}

output "security_group_id" {
  value = aws_security_group.rds.id
}
