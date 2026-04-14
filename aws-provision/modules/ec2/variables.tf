variable "vpc_id" {}
variable "public_subnet_id" {}
variable "private_subnet_id" {}
variable "ami" {}
variable "my_ip" {
    description = "The IP address fetched from the user's machine to allow access to the bastion host."
    type        = list(string) 
}