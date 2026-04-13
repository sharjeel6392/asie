variable "region" {
    default = "ap-south-1"
}

variable "profile" {
    default = "default"
}

variable "vpc_cidr" {
    default = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
    default = "10.0.1.0/24"
}

variable "private_subnet_cidr" {
    default = "10.0.2.0/24"
}

variable "az" {
    default = "ap-south-1a"
}

# Fetch the user's IP address to allow access to the cluster
data "http" "my_ip" {
    url = "https://checkip.amazonaws.com/"
}

variable "my_ip" {
    description = "Your IP address to allow access to the cluster"
    default = ["${chomp(data.http.my_ip.response_body)}/32"]
}