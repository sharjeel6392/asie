
# Security Group
resource "aws_security_group" "ec2_sg" {
    name    = "ec2-sg"
    vpc_id  = var.vpc_id

    ingress {
        from_port   = 22
        to_port     = 22
        protocol    = "tcp"
        cidr_blocks  = ["49.36.212.204/32"]
    }

    egress{
        from_port   = 0
        to_port     = 0
        protocol    = "-1"
        cidr_blocks  = ["0.0.0.0/0"]
    }
}

# Public EC2 (Bastion)
resource "aws_instance" "public" {
    ami                         = var.ami
    instance_type               = "t2.micro"
    subnet_id                   = var.public_subnet_id
    associate_public_ip_address = true
    key_name                    = "asie-key-pair"

    vpc_security_group_ids = [aws_security_group.ec2_sg.id]

    tags = {
        Name = "public-ec2"
    }
}

# Private EC2
resource "aws_instance" "private" {
    ami             = var.ami
    instance_type   = "t2.micro"
    subnet_id       = var.private_subnet_id

    vpc_security_group_ids = [aws_security_group.ec2_sg.id]

    tags = {
        Name = "private-ec2"
    }
}