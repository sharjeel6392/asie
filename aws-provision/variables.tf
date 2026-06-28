variable "region" {
    default = "ap-south-1"
}

variable "profile" {
    default = "default"
}

variable "vpc_cidr" {
    default = "10.0.0.0/16"
}

variable "public1_subnet_cidr" {
    default = "10.0.1.0/24"
}

variable "private1_subnet_cidr" {
    default = "10.0.2.0/24"
}

variable "public2_subnet_cidr" {
    default = "10.0.3.0/24"
}

variable "private2_subnet_cidr" {
    default = "10.0.4.0/24"
}

variable "az1" {
    default = "ap-south-1a"
}

variable "az2" {
    default = "ap-south-1b"
}

# Fetch the user's IP address to allow access to the cluster
data "http" "my_ip" {
    url = "https://checkip.amazonaws.com/"
}

locals {
    my_ip = ["${chomp(data.http.my_ip.response_body)}/32"]
}