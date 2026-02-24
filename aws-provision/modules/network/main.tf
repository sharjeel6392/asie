
# Define the VPC
resource "aws_vpc" "main" {
    cidr_block = var.vpc_cidr

    tags = {
        Name = "my-vpc"
    }
}

# Public Subnet
resource "aws_subnet" "public" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = var.public_subnet_cidr
    availability_zone       = var.az
    map_public_ip_on_launch = true

    tags = {
        Name = "public-subnet"
    }
}

# Private Subnet
resource "aws_subnet" "private" {
    vpc_id              = aws_vpc.main.id
    cidr_block          = var.private_subnet_cidr
    availability_zone   = var.az

    tags = {
        Name = "private-subnet"
    }
}

# IGW
resource "aws_internet_gateway" "igw" {
    vpc_id = aws_vpc.main.id

    tags = {
        Name = "my-igw"
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
        Name = "public-rt"
    }
}

# Associate it
resource "aws_route_table_association" "public_assoc" {
    subnet_id       = aws_subnet.public.id
    route_table_id  = aws_route_table.public.id
}


# NAT + EIP
resource "aws_eip" "nat_eip" {
    domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
    allocation_id   = aws_eip.nat_eip.id
    subnet_id       = aws_subnet.public.id

    tags = {
        Name = "my-nat"
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
        Name = "private-rt"
    }
}

# Associate it
resource "aws_route_table_association" "private_assoc" {
    subnet_id       = aws_subnet.private.id
    route_table_id  = aws_route_table.private.id
}