#!/bin/bash

set -e

REGION="ap-south-1"
CLUSTER_NAME="asie-cluster"

INFERENCE_NAMESPACE="asie-inference"
AIRFLOW_NAMESPACE="airflow"
MLFLOW_NAMESPACE="mlflow"
MONITORING_NAMESPACE="monitoring"

MONITORING_RELEASE="kube-prometheus-stack"

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

    echo "Step 4a: Ensure the EBS CSI driver addon exists..."
    # eks-cluster.yaml declares this addon, but that only applies on cluster
    # CREATE -- an already-existing cluster needs it added explicitly. Without
    # it every PVC (Prometheus, Grafana) stays Pending forever, since the
    # in-tree EBS provisioner was removed in Kubernetes 1.23.
    if eksctl get addon --cluster $CLUSTER_NAME --region $REGION --name aws-ebs-csi-driver > /dev/null 2>&1; then
        echo "EBS CSI driver addon already present. Skipping."
    else
        eksctl create addon --cluster $CLUSTER_NAME --region $REGION \
            --name aws-ebs-csi-driver \
            --service-account-role-arn "$(eksctl create iamserviceaccount \
                --cluster $CLUSTER_NAME --region $REGION \
                --name ebs-csi-controller-sa --namespace kube-system \
                --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
                --role-only --role-name AmazonEKS_EBS_CSI_DriverRole_asie \
                --override-existing-serviceaccounts --approve > /dev/null 2>&1; \
                aws iam get-role --role-name AmazonEKS_EBS_CSI_DriverRole_asie \
                    --query 'Role.Arn' --output text)" \
            --force
    fi

    echo "Step 4b: Apply the gp3 StorageClass and demote gp2..."
    kubectl apply -f eks/storageclass-gp3.yaml
    # Two StorageClasses both claiming is-default-class makes PVC binding
    # non-deterministic, so explicitly demote the built-in gp2.
    kubectl patch storageclass gp2 \
        -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}' \
        > /dev/null 2>&1 || true

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

    echo "Step 12: Ensure the Grafana admin secret exists..."
    # Created here rather than left to the chart's default admin/prom-operator.
    # Generated once and reused -- regenerating on every run would silently
    # change the password out from under whoever has it saved.
    kubectl -n $MONITORING_NAMESPACE get secret grafana-admin > /dev/null 2>&1 || \
        kubectl -n $MONITORING_NAMESPACE create secret generic grafana-admin \
            --from-literal=admin-user=admin \
            --from-literal=admin-password=$(openssl rand -base64 18 | tr -d '/+=')

    echo "Step 13: Deploying kube-prometheus-stack (before inference -- it owns the ServiceMonitor CRD)..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts > /dev/null 2>&1 || true
    helm repo update prometheus-community > /dev/null
    helm upgrade --install $MONITORING_RELEASE prometheus-community/kube-prometheus-stack \
        --namespace $MONITORING_NAMESPACE \
        -f eks/monitoring-values.yaml \
        --wait --timeout 10m

    echo "Step 14: Applying PrometheusRule and Grafana dashboard..."
    # After the stack, since both depend on CRDs/labels it establishes.
    kubectl apply -f eks/monitoring-rules.yaml
    kubectl apply -f eks/grafana-dashboard-asie.yaml

    echo "Step 15: Deploying inference application..."
    # serviceMonitor.enabled is off by default so the chart installs on a
    # cluster without the Prometheus Operator; it's safe to turn on here
    # because Step 13 has just installed the CRD.
    helm upgrade --install $INFERENCE_RELEASE ./helm/asie-inference \
        --namespace $INFERENCE_NAMESPACE \
        --set image.repository=$INFERENCE_ECR_URI \
        --set image.tag=$GIT_SHA \
        --set serviceAccount.name=asie-irsa-sa \
        --set serviceMonitor.enabled=true

    echo "Step 16: Applying the shared ALB Ingress..."
    kubectl apply -f eks/ingress.yaml

    echo "Step 17: Waiting for the ALB to be provisioned..."
    # The Service is ClusterIP now -- the ALB address lives on the Ingress.
    for i in $(seq 1 30); do
        ALB=$(kubectl get ingress -n $INFERENCE_NAMESPACE asie-inference \
              -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
        [ -n "$ALB" ] && break
        sleep 20
    done
    kubectl get ingress -A
    if [ -n "$ALB" ]; then
        echo "Setup complete!"
        echo "  Inference API : http://$ALB/"
        echo "  Grafana       : http://$ALB/grafana"
        echo "  Grafana admin password: kubectl -n $MONITORING_NAMESPACE get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d"
        echo "  Airflow/MLflow UIs are ClusterIP -- reach them with kubectl port-forward (see eks/ingress.yaml)."
    else
        echo "Setup complete, but the ALB has no address yet. Check: kubectl describe ingress -n $INFERENCE_NAMESPACE asie-inference"
    fi

fi
# -------------------------------
# TEARDOWN
# -------------------------------
if [ "$1" == "down" ]; then
    echo "Starting CLEAN TEARDOWN..."

    # The Ingress goes FIRST and on its own. It owns the shared ALB, and the
    # ALB's ENIs sit in the VPC subnets -- deleting the namespace out from
    # under it can orphan the load balancer, after which terraform destroy
    # hangs trying to delete subnets that still have attachments. Deleting the
    # Ingress lets the controller tear the ALB down cleanly first.
    echo "Step 1: Deleting the shared ALB Ingress and waiting for it to drain..."
    kubectl delete -f eks/ingress.yaml --ignore-not-found
    sleep 45

    # Helm releases (and any LoadBalancer/ELB-owning Services) must also go
    # before the cluster, for the same ENI reason.
    echo "Step 2: Deleting Helm releases..."
    helm uninstall $INFERENCE_RELEASE -n $INFERENCE_NAMESPACE || true
    helm uninstall $AIRFLOW_RELEASE -n $AIRFLOW_NAMESPACE || true
    helm uninstall $MLFLOW_RELEASE -n $MLFLOW_NAMESPACE || true
    helm uninstall $MONITORING_RELEASE -n $MONITORING_NAMESPACE || true

    # PVCs are not removed by `helm uninstall` -- the operator's volumeClaim
    # templates leave them behind, and an orphaned PVC keeps its EBS volume
    # alive and billing after the cluster is gone.
    echo "Step 3: Deleting monitoring PVCs (helm uninstall leaves these behind)..."
    kubectl delete pvc --all -n $MONITORING_NAMESPACE --ignore-not-found || true

    echo "Step 4: Deleting namespaces..."
    kubectl delete namespace $INFERENCE_NAMESPACE $AIRFLOW_NAMESPACE $MLFLOW_NAMESPACE $MONITORING_NAMESPACE --ignore-not-found

    echo "Step 5: Deleting EKS Cluster..."
    eksctl delete cluster --name $CLUSTER_NAME --region $REGION || true

    # ECR repos are Terraform-owned (aws-provision/main.tf) -- destroyed by
    # the step below, not deleted here separately.
    echo "Step 6: Destroying AWS infrastructure with Terraform..."
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
