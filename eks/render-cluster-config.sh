#!/bin/bash
# Fills eks/eks-cluster.yaml's <YOUR_X_ID> placeholders with the live
# VPC/subnet IDs from Terraform, writing eks/tmp-cluster.yaml (gitignored).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT/aws-provision"
VPC_ID=$(terraform output -raw vpc_id)
PUBLIC1_SUBNET=$(terraform output -raw public1_subnet_id)
PUBLIC2_SUBNET=$(terraform output -raw public2_subnet_id)
PRIVATE1_SUBNET=$(terraform output -raw private1_subnet_id)
PRIVATE2_SUBNET=$(terraform output -raw private2_subnet_id)
cd "$REPO_ROOT"

sed -e "s|<YOUR_VPC_ID>|$VPC_ID|g" \
    -e "s|<YOUR_PUBLIC1_SUBNET_ID>|$PUBLIC1_SUBNET|g" \
    -e "s|<YOUR_PUBLIC2_SUBNET_ID>|$PUBLIC2_SUBNET|g" \
    -e "s|<YOUR_PRIVATE1_SUBNET_ID>|$PRIVATE1_SUBNET|g" \
    -e "s|<YOUR_PRIVATE2_SUBNET_ID>|$PRIVATE2_SUBNET|g" \
    eks/eks-cluster.yaml > eks/tmp-cluster.yaml

echo "Generated eks/tmp-cluster.yaml with:"
echo "  vpc_id=$VPC_ID public1=$PUBLIC1_SUBNET public2=$PUBLIC2_SUBNET private1=$PRIVATE1_SUBNET private2=$PRIVATE2_SUBNET"
