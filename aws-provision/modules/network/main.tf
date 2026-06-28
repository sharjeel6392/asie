
# Define the VPC
resource "aws_vpc" "main" {
    cidr_block           = var.vpc_cidr
    enable_dns_support   = true
    enable_dns_hostnames = true

    tags = {
        Name = "asie-vpc"
    }
}

# Public Subnet in ap-south-1a
resource "aws_subnet" "public1" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = var.public1_subnet_cidr
    availability_zone       = var.az1
    map_public_ip_on_launch = true

    tags = {
        Name = "asie-public1-subnet"
        "kubernetes.io/role/elb" = "1"
    }
}

# Private Subnet in ap-south-1a
resource "aws_subnet" "private1" {
    vpc_id              = aws_vpc.main.id
    cidr_block          = var.private1_subnet_cidr
    availability_zone   = var.az1

    tags = {
        Name = "asie-private1-subnet"
        "kubernetes.io/role/internal-elb" = "1"
    }
}

# Public Subnet in ap-south-1b
resource "aws_subnet" "public2" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = var.public2_subnet_cidr
    availability_zone       = var.az2
    map_public_ip_on_launch = true

    tags = {
        Name = "asie-public2-subnet"
        "kubernetes.io/role/elb" = "1"
    }
}

# Private Subnet in ap-south-1b
resource "aws_subnet" "private2" {
    vpc_id              = aws_vpc.main.id
    cidr_block          = var.private2_subnet_cidr
    availability_zone   = var.az2

    tags = {
        Name = "asie-private2-subnet"
        "kubernetes.io/role/internal-elb" = "1"
    }
}


# IGW
resource "aws_internet_gateway" "igw" {
    vpc_id = aws_vpc.main.id

    tags = {
        Name = "asie-my-igw"
    }
}

# Public Route Table
resource "aws_route_table" "public" {
    vpc_id = aws_vpc.main.id

    route {
        cidr_block = "0.0.0.0/0"
        gateway_id = aws_internet_gateway.igw.id
    }

    tags = {
        Name = "asie-public-rt"
    }
}

# Associate it
resource "aws_route_table_association" "public_1a_assoc" {
    subnet_id       = aws_subnet.public1.id
    route_table_id  = aws_route_table.public.id
}

resource "aws_route_table_association" "public_1b_assoc" {
    subnet_id       = aws_subnet.public2.id
    route_table_id  = aws_route_table.public.id
}

# NAT + EIP
resource "aws_eip" "nat_eip" {
    domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
    allocation_id   = aws_eip.nat_eip.id
    subnet_id       = aws_subnet.public1.id
    
    depends_on      = [aws_internet_gateway.igw]

    tags = {
        Name = "asie-my-nat"
    }
}

# Private Route Table
resource "aws_route_table" "private" {
    vpc_id = aws_vpc.main.id

    route {
        cidr_block      = "0.0.0.0/0"
        nat_gateway_id  = aws_nat_gateway.nat.id
    }
    
    tags = {
        Name = "asie-private-rt"
    }
}

# Associate it
resource "aws_route_table_association" "private_1a_assoc" {
    subnet_id       = aws_subnet.private1.id
    route_table_id  = aws_route_table.private.id
}

resource "aws_route_table_association" "private_1b_assoc" {
    subnet_id       = aws_subnet.private2.id
    route_table_id  = aws_route_table.private.id
}