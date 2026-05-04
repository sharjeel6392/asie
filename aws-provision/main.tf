# Wire everything together
module "network" {
    source              = "./modules/network"

    vpc_cidr            = var.vpc_cidr
    public1_subnet_cidr  = var.public1_subnet_cidr
    private1_subnet_cidr = var.private1_subnet_cidr
    az1                  = var.az1

    public2_subnet_cidr  = var.public2_subnet_cidr
    private2_subnet_cidr = var.private2_subnet_cidr
    az2                  = var.az2
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
    public1_subnet_id    = module.network.public1_subnet_id
    private1_subnet_id   = module.network.private1_subnet_id
    
    public2_subnet_id    = module.network.public2_subnet_id
    private2_subnet_id   = module.network.private2_subnet_id
    
    ami                 = data.aws_ami.amazon_linux_2023.id
    my_ip               = local.my_ip
}