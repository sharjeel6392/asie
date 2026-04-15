output "bastion_1a_public_ip" {
    value = aws_instance.public-1a.public_ip
}

output "private_1a_instance_id" {
    value = aws_instance.private-1a.id
}

output "private_1a_instance_private_ip" {
    value = aws_instance.private-1a.private_ip
}

output "bastion_1b_public_ip" {
    value = aws_instance.public-1b.public_ip
}

output "private_1b_instance_id" {
    value = aws_instance.private-1b.id
}

output "private_1b_instance_private_ip" {
    value = aws_instance.private-1b.private_ip
}

