output "vpc_id" {
    value = module.network.vpc_id
}

output "public_subnet_id" {
    value = module.network.public_subnet_id
}

output "private_subnet_id" {
    value = module.network.private_subnet_id
}

output "bastion_public_ip" {
    value = module.ec2.bastion_public_ip
}