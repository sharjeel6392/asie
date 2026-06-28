variable "vpc_id" {}

variable "public1_subnet_id" {}
variable "private1_subnet_id" {}

variable "public2_subnet_id" {}
variable "private2_subnet_id" {}

variable "ami" {}
variable "my_ip" {
    description = "The IP address fetched from the user's machine to allow access to the bastion host."
    type        = list(string) 
}