output "bastion_public_ip" {
    value = aws_instance.public.public_ip
}

output "private_instance_id" {
    value = aws_instance.private.id
}

output "private_instance_private_ip" {
    value = aws_instance.private.private_ip
}