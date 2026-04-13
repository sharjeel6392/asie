#!/bin/bash

set -e

REGION="ap=south-1"
CLUSTER_NAME="asie-cluster"
NAMESPACE="asie-inference-namespace"
ECR_REPO="asie-inference-repo"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO"

# -------------------------------
# SETUP
# -------------------------------

if [ "$1" == "up" ]; then
    echo "Starting FULL SETUP..."

    echo "Step 1: Provisioning AWS infrastructure with Terraform..."
    cd aws-provision
    terraform init
    terraform apply -auto-approve

    VPC_ID=$(terraform output -raw vpc_id)
    PUBLIC_SUBNET=$(terraform output -raw public_subnet_id)
    PRIVATE_SUBNET=$(terraform output -raw private_subnet_id)

    cd ..

    echo "Step 2: Building and pushing Docker image to ECR..."
    aws ecr describe-repositories --repository-names $ECR_REPO || \
        aws ecr create-repository --repository-name $ECR_REPO

    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.drk.ecr.$REGION.amazonaws.com

    docker build -t $ECR_REPO .
    docker tag $ECR_REPO:latest $ECR_URI:latest
    docker push $ECR_URI:latest

    echo "Step 3: Creating EKS cluster with eksctl..."
    # Replace placeholders in eks config with actual values, dynamically.
    sed "s|<YOUR_VPC_ID>|$VPC_ID|g;
         s|<YOUR_PUBLIC_SUBNET_ID>|$PUBLIC_SUBNET|g;
         s|<YOUR_PRIVATE_SUBNET_ID>|$PRIVATE_SUBNET|g"
         eks/eks-cluster.yaml > eks/tmp-cluster.yaml

    eksctl create cluster -f eks/tmp-cluster.yaml

    echo "Step 4: Enable OIDC (For IRSA)..."
    eksctl utils associate-iam-oidc-provider \
        --region $REGION \
        --cluster $CLUSTER_NAME \
        --approve

    echo "Step 5: Update kubeconfig for kubectl access..."
    aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME

    echo "Step 6: Create IRSA Service Account"
    eksctl create iamserviceaccount \
        --name asie-irsa-sa \
        --namespace $NAMESPACE \
        --cluster $CLUSTER_NAME \
        --approve

    echo "Step 7: Deploy inference application to EKS using Helm..."
    helm upgrade --install asie ./helm/asie-inference \
        --namespace $NAMESPACE \
        --create-namespace \
        --set image.repository=$ECR_URI \
        --set image.tag=latest \
        --set serviceAccount.name=asie-irsa-sa

    echo "Step 8: Waiting for LoadBalancer to be ready..."
    kubectl get svc -n $NAMESPACE asie-inference-service -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' -w
    kubectl get svc -n $NAMESPACE
    echo "Setup complete! Your inference service is now accessible via the LoadBalancer endpoints."

fi
# -------------------------------
# TEARDOWN
# -------------------------------
if [ "$1" == "down" ]; then
    echo "Starting CLEAN TEARDOWN..."

    echo "Step 1: Deleting Helm Release..."
    helm uninstall asie -n $NAMESPACE || true

    echo "Step 2: Deleting Namespace..."
    kubectl delete namespace $NAMESPACE || true

    echo "Step 3: Deleting EKS Cluster"
    eksctl delete cluster --name $CLUSTER_NAME --region $REGION || true

    echo "Step 4: Deleting ECR Repository..."
    aws ecr delete-repository \
        --repository-name $ECR_REPO \
        --force || true

    echo "Step 5: Destroying AWS infrastructure with Terraform..."
    cd aws-provision
    terraform destroy -auto-approve
    cd ..

    echo "Teardown complete! ALL resources have been cleaned up."
fi

# Usage instructions:
# To set up the entire infrastrucrture and deploy the application, run:
# ./asie.sh up
# To tear down and clean up all resources, run:
# ./asie.sh down