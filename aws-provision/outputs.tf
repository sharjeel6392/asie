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
