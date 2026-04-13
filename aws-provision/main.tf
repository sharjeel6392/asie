# Wire everything together
module "network" {
    source              = "./modules/network"
    
    vpc_cidr            = var.vpc_cidr
    public_subnet_cidr  = var.public_subnet_cidr
    private_subnet_cidr = var.private_subnet_cidr
    az                  = var.az
}

data "aws_ami" "amazon_linux_2023" {
    most_recent = true
    owners      = ["amazon"]

    filter {
        name    = "name"
        values  = ["al2023-ami-2023*-x86_64"]
    }

    filter {
        name    = "architecture"
        values   = ["x86_64"]
    }
}

module "ec2" {
    source              = "./modules/ec2"

    vpc_id              = module.network.vpc_id
    public_subnet_id    = module.network.public_subnet_id
    private_subnet_id   = module.network.private_subnet_id
    ami                 = data.aws_ami.amazon_linux_2023.id
    my_ip               = var.my_ip
}