variable "vpc_id" {}

variable "private_subnet_ids" {
  type = list(string)
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks allowed to reach Postgres (5432) — scoped to the private subnets where EKS nodes will live."
  type        = list(string)
}

variable "db_name" {
  default = "asie_app"
}

variable "db_username" {
  default = "asie_admin"
}

variable "instance_class" {
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  default = 20
}

variable "engine_version" {
  default = "16"
}
