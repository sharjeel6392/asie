#!/bin/bash

set -e

REGION="ap-south-1"
CLUSTER_NAME="asie-cluster"

INFERENCE_NAMESPACE="asie-inference"
AIRFLOW_NAMESPACE="airflow"
MLFLOW_NAMESPACE="mlflow"

INFERENCE_RELEASE="asie"
AIRFLOW_RELEASE="airflow"
# Must be exactly "asie-mlflow" -- eks/airflow-values.yaml and
# helm/asie-inference's configmap both hardcode the resulting Service DNS
# (asie-mlflow.mlflow.svc.cluster.local). A different release name here
# silently breaks both.
MLFLOW_RELEASE="asie-mlflow"

INFERENCE_ECR_REPO="asie-inference-repo"
AIRFLOW_ECR_REPO="asie-airflow-repo"
MLFLOW_ECR_REPO="asie-mlflow-repo"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
INFERENCE_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$INFERENCE_ECR_REPO"
AIRFLOW_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$AIRFLOW_ECR_REPO"
MLFLOW_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$MLFLOW_ECR_REPO"

# Tag every image with the current commit, not just "latest" -- a
# "latest"-tagged Deployment with an unchanged pod spec won't restart on
# `helm upgrade`, since Kubernetes doesn't see the underlying image as
# having changed. GIT_SHA is what actually forces a rollout.
GIT_SHA=$(git rev-parse --short HEAD)

# -------------------------------
# SETUP
# -------------------------------

if [ "$1" == "up" ]; then
    echo "Starting FULL SETUP..."

    echo "Step 1: Provisioning AWS infrastructure with Terraform..."
    cd aws-provision
    terraform init
    terraform apply -auto-approve
    cd ..

    echo "Step 2: Creating EKS cluster with eksctl..."
    if eksctl get cluster --name $CLUSTER_NAME --region $REGION > /dev/null 2>&1; then
        echo "EKS cluster already exists. Skipping creation."
    else
        # Fill eks-cluster.yaml's placeholders from Terraform outputs.
        ./eks/render-cluster-config.sh
        eksctl create cluster -f eks/tmp-cluster.yaml
    fi

    echo "Step 3: Update kubeconfig for kubectl access..."
    aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME

    echo "Step 4: Ensure namespaces exist..."
    kubectl apply -f eks/namespaces.yaml

    echo "Step 5: Create IRSA Service Accounts (one per workload, least-privilege S3 policy)..."
    eksctl create iamserviceaccount \
        --name asie-irsa-sa \
        --namespace $INFERENCE_NAMESPACE \
        --cluster $CLUSTER_NAME \
        --region $REGION \
        --attach-policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AsieInferenceS3Policy" \
        --override-existing-serviceaccounts \
        --approve

    eksctl create iamserviceaccount \
        --name airflow-irsa-sa \
        --namespace $AIRFLOW_NAMESPACE \
        --cluster $CLUSTER_NAME \
        --region $REGION \
        --attach-policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AsieAirflowS3Policy" \
        --override-existing-serviceaccounts \
        --approve

    eksctl create iamserviceaccount \
        --name mlflow-irsa-sa \
        --namespace $MLFLOW_NAMESPACE \
        --cluster $CLUSTER_NAME \
        --region $REGION \
        --attach-policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AsieMlflowS3Policy" \
        --override-existing-serviceaccounts \
        --approve

    echo "Step 6: Bootstrapping RDS (airflow_db/mlflow_db, DB roles, ported schema, app secrets)..."
    ./eks/db-bootstrap/run.sh

    echo "Step 7: Uploading exported_model/ + model_registry.yaml to S3..."
    ./scripts/upload-models.sh

    echo "Step 8: Building and pushing images to ECR..."
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

    docker build -t $INFERENCE_ECR_REPO:$GIT_SHA -f dockerfile .
    docker tag $INFERENCE_ECR_REPO:$GIT_SHA $INFERENCE_ECR_URI:$GIT_SHA
    docker tag $INFERENCE_ECR_REPO:$GIT_SHA $INFERENCE_ECR_URI:latest
    docker push $INFERENCE_ECR_URI:$GIT_SHA
    docker push $INFERENCE_ECR_URI:latest

    docker build -t $AIRFLOW_ECR_REPO:$GIT_SHA -f Dockerfile.airflow .
    docker tag $AIRFLOW_ECR_REPO:$GIT_SHA $AIRFLOW_ECR_URI:$GIT_SHA
    docker tag $AIRFLOW_ECR_REPO:$GIT_SHA $AIRFLOW_ECR_URI:latest
    docker push $AIRFLOW_ECR_URI:$GIT_SHA
    docker push $AIRFLOW_ECR_URI:latest

    docker build -t $MLFLOW_ECR_REPO:$GIT_SHA -f Dockerfile.mlflow .
    docker tag $MLFLOW_ECR_REPO:$GIT_SHA $MLFLOW_ECR_URI:$GIT_SHA
    docker tag $MLFLOW_ECR_REPO:$GIT_SHA $MLFLOW_ECR_URI:latest
    docker push $MLFLOW_ECR_URI:$GIT_SHA
    docker push $MLFLOW_ECR_URI:latest

    echo "Step 9: Ensure the Airflow webserver secret key exists (fixed, not chart-regenerated -- regenerating invalidates all sessions)..."
    kubectl -n $AIRFLOW_NAMESPACE get secret airflow-webserver-secret > /dev/null 2>&1 || \
        kubectl -n $AIRFLOW_NAMESPACE create secret generic airflow-webserver-secret \
            --from-literal=webserver-secret-key=$(openssl rand -hex 16)

    echo "Step 10: Deploying MLflow (before Airflow -- the DAG's env points at its Service DNS)..."
    helm upgrade --install $MLFLOW_RELEASE ./helm/asie-mlflow \
        --namespace $MLFLOW_NAMESPACE \
        --set image.repository=$MLFLOW_ECR_URI \
        --set image.tag=$GIT_SHA

    echo "Step 11: Deploying Airflow..."
    helm repo add apache-airflow https://airflow.apache.org > /dev/null 2>&1 || true
    helm repo update apache-airflow > /dev/null
    helm upgrade --install $AIRFLOW_RELEASE apache-airflow/airflow \
        --version 1.16.0 \
        --namespace $AIRFLOW_NAMESPACE \
        -f eks/airflow-values.yaml \
        --set images.airflow.repository=$AIRFLOW_ECR_URI \
        --set images.airflow.tag=$GIT_SHA

    echo "Step 12: Deploying inference application..."
    helm upgrade --install $INFERENCE_RELEASE ./helm/asie-inference \
        --namespace $INFERENCE_NAMESPACE \
        --set image.repository=$INFERENCE_ECR_URI \
        --set image.tag=$GIT_SHA \
        --set serviceAccount.name=asie-irsa-sa

    echo "Step 13: Waiting for LoadBalancer to be ready..."
    kubectl get svc -n $INFERENCE_NAMESPACE $INFERENCE_RELEASE -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' -w &
    WPID=$!
    sleep 60
    kill $WPID 2>/dev/null || true
    kubectl get svc -n $INFERENCE_NAMESPACE
    echo "Setup complete! Your inference service is now accessible via the LoadBalancer endpoint above."

fi
# -------------------------------
# TEARDOWN
# -------------------------------
if [ "$1" == "down" ]; then
    echo "Starting CLEAN TEARDOWN..."

    # Helm releases (and their LoadBalancer/ELB-owning Services) must go
    # before the cluster -- leftover ELB-attached ENIs block VPC teardown
    # otherwise, causing terraform destroy to hang or fail.
    echo "Step 1: Deleting Helm releases..."
    helm uninstall $INFERENCE_RELEASE -n $INFERENCE_NAMESPACE || true
    helm uninstall $AIRFLOW_RELEASE -n $AIRFLOW_NAMESPACE || true
    helm uninstall $MLFLOW_RELEASE -n $MLFLOW_NAMESPACE || true

    echo "Step 2: Deleting namespaces..."
    kubectl delete namespace $INFERENCE_NAMESPACE $AIRFLOW_NAMESPACE $MLFLOW_NAMESPACE --ignore-not-found

    echo "Step 3: Deleting EKS Cluster..."
    eksctl delete cluster --name $CLUSTER_NAME --region $REGION || true

    # ECR repos are Terraform-owned (aws-provision/main.tf) -- destroyed by
    # Step 4 below, not deleted here separately.
    echo "Step 4: Destroying AWS infrastructure with Terraform..."
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
