output "vpc_id" {
    value = aws_vpc.main.id
}

output "public1_subnet_id" {
    value = aws_subnet.public1.id
}

output "private1_subnet_id" {
    value = aws_subnet.private1.id
}

output "public2_subnet_id" {
    value = aws_subnet.public2.id
}

output "private2_subnet_id" {
    value = aws_subnet.private2.id
}