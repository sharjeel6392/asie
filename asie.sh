#!/bin/bash
#
# Single entry and exit point for the whole ASIE AWS stack.
#
#   ./asie.sh up      provision everything and deploy
#   ./asie.sh pause    delete compute, KEEP all data (S3, ECR, RDS, VPC)
#   ./asie.sh resume   rebuild compute on top of surviving data
#   ./asie.sh down     destroy everything, irreversibly (asks first)
#
# The phases below are functions rather than one long script so the four
# commands compose from the same building blocks -- `resume` must run exactly
# the steps `up` runs, or it drifts out of sync and only fails in production.

set -e

REGION="ap-south-1"
CLUSTER_NAME="asie-cluster"

INFERENCE_NAMESPACE="asie-inference"
AIRFLOW_NAMESPACE="airflow"
MLFLOW_NAMESPACE="mlflow"
MONITORING_NAMESPACE="monitoring"

MONITORING_RELEASE="kube-prometheus-stack"

# GitOps control plane. ArgoCD owns every workload from here on; this script
# only installs ArgoCD itself and points it at the repo.
# Matches what was installed by hand in Week 11 and verified working.
ALB_CONTROLLER_CHART_VERSION="3.5.0"

ARGOCD_NAMESPACE="argocd"
ARGOCD_CHART_VERSION="7.7.11"
ARGOCD_REPO_SECRET="asie-repo-creds"
# Must match repoURL in gitops/apps/*.yaml and gitops/bootstrap/root-app.yaml
# EXACTLY. ArgoCD pairs a credential to an Application by URL, and the SSH and
# HTTPS forms of the same repo are different URLs to it -- a mismatch means the
# credential silently does not apply and the Application sits in
# ComparisonError with a permission-denied that looks like a bad key.
REPO_URL="git@github.com:sharjeel6392/asie.git"
# Secrets Manager entry holding the read-only deploy key's PRIVATE half.
ARGOCD_REPO_SECRET_SM="asie/argocd-repo-read"
# WRITE-scoped key, mounted by the Airflow pods so the retraining and rollback
# DAGs can commit model versions. Separate from the read key by design: ArgoCD
# needs read only, so a compromised ArgoCD cannot rewrite desired state.
AIRFLOW_REPO_SECRET_SM="asie/airflow-repo-write"
AIRFLOW_REPO_SECRET="asie-gitops-write"

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

# Tag every image with the current commit, not just "latest" -- a
# "latest"-tagged Deployment with an unchanged pod spec won't restart on
# `helm upgrade`, since Kubernetes doesn't see the underlying image as
# having changed. GIT_SHA is what actually forces a rollout.
GIT_SHA=$(git rev-parse --short HEAD)

step() { echo ""; echo "==> $*"; }

# Resolved lazily, not at the top of the script: an unconditional `aws sts`
# call means `./asie.sh` with no arguments needs working connectivity just to
# print its usage, and under `set -e` it dies before printing anything at all.
require_aws() {
    if ! ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
        echo "Cannot reach AWS (sts.$REGION.amazonaws.com). Check connectivity and credentials." >&2
        exit 1
    fi
    INFERENCE_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$INFERENCE_ECR_REPO"
    AIRFLOW_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$AIRFLOW_ECR_REPO"
    MLFLOW_ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$MLFLOW_ECR_REPO"
    S3_BUCKET="asie-platform-$ACCOUNT_ID"
}

# ---------------------------------------------------------------------------
# BUILD-UP PHASES
# ---------------------------------------------------------------------------

provision_infra() {
    step "Provisioning AWS infrastructure with Terraform..."
    cd aws-provision
    terraform init
    terraform apply -auto-approve
    cd ..
}

create_cluster() {
    step "Creating EKS cluster with eksctl..."

    # Status, not mere existence. `eksctl get cluster` succeeds for a cluster
    # in DELETING just as it does for a healthy one, so the old existence check
    # reported "already exists, skipping creation" for a cluster that was
    # disappearing -- and then handed every later step a control plane that
    # vanished underneath it. Hit immediately by running `pause` and `up`
    # back to back, which is the obvious way to test a rebuild.
    local status
    status=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION \
             --query 'cluster.status' --output text 2>/dev/null | tr -d '\r')
    [ -z "$status" ] && status="ABSENT"

    if [ "$status" = "DELETING" ]; then
        echo "Cluster is DELETING; waiting for it to finish before recreating..."
        for _ in $(seq 1 60); do
            sleep 30
            status=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION \
                     --query 'cluster.status' --output text 2>/dev/null | tr -d '\r')
            [ -z "$status" ] && { status="ABSENT"; break; }
            echo "  still $status..."
        done
        if [ "$status" = "DELETING" ]; then
            echo "Cluster still DELETING after 30 minutes; aborting rather than guessing." >&2
            exit 1
        fi
    fi

    if [ "$status" = "ACTIVE" ]; then
        echo "EKS cluster already exists and is ACTIVE. Skipping creation."
    else
        # Fill eks-cluster.yaml's placeholders from Terraform outputs.
        ./eks/render-cluster-config.sh
        eksctl create cluster -f eks/tmp-cluster.yaml
    fi

    step "Updating kubeconfig for kubectl access..."
    aws eks update-kubeconfig --region $REGION --name $CLUSTER_NAME
}

cluster_addons() {
    step "Ensuring the EBS CSI driver addon exists..."
    # eks-cluster.yaml declares this addon, but that only applies on cluster
    # CREATE -- an already-existing cluster needs it added explicitly. Without
    # it every PVC (Prometheus, Grafana) stays Pending forever, since the
    # in-tree EBS provisioner was removed in Kubernetes 1.23.
    if eksctl get addon --cluster $CLUSTER_NAME --region $REGION --name aws-ebs-csi-driver > /dev/null 2>&1; then
        echo "EBS CSI driver addon already present. Skipping."
    else
        eksctl create iamserviceaccount \
            --cluster $CLUSTER_NAME --region $REGION \
            --name ebs-csi-controller-sa --namespace kube-system \
            --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
            --role-only --role-name AmazonEKS_EBS_CSI_DriverRole_asie \
            --override-existing-serviceaccounts --approve
        eksctl create addon --cluster $CLUSTER_NAME --region $REGION \
            --name aws-ebs-csi-driver \
            --service-account-role-arn "arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole_asie" \
            --force
    fi

    step "Applying the gp3 StorageClass and demoting gp2..."
    kubectl apply -f eks/storageclass-gp3.yaml
    # Two StorageClasses both claiming is-default-class makes PVC binding
    # non-deterministic, so explicitly demote the built-in gp2.
    kubectl patch storageclass gp2 \
        -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}' \
        > /dev/null 2>&1 || true
}

install_alb_controller() {
    # Nothing in this repo installed this until now -- it was applied by hand
    # during Week 11 Day 3 and survived only because the cluster did. The first
    # real rebuild proved the gap: both Ingress objects were created by ArgoCD
    # and sat with no ADDRESS for two hours, because the controller that turns
    # an Ingress into an ALB did not exist. Everything looked healthy; nothing
    # was reachable.
    #
    # Deliberately bootstrap rather than an ArgoCD Application: the Ingress in
    # wave 3 depends on it, and a controller that provisions the load balancer
    # the whole stack is reached through belongs with the cluster, not with the
    # workloads it serves.
    step "Installing the AWS Load Balancer Controller..."

    # Cluster-scoped IRSA -- the IAM policy itself is account-scoped and
    # survives cluster deletion, so this re-binds an existing policy.
    eksctl create iamserviceaccount \
        --cluster $CLUSTER_NAME --region $REGION \
        --namespace kube-system --name aws-load-balancer-controller \
        --attach-policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" \
        --override-existing-serviceaccounts --approve

    helm repo add eks https://aws.github.io/eks-charts > /dev/null 2>&1 || true
    helm repo update eks > /dev/null
    helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
        --version $ALB_CONTROLLER_CHART_VERSION \
        --namespace kube-system \
        -f eks/aws-load-balancer-controller-values.yaml \
        --set clusterName=$CLUSTER_NAME \
        --wait --timeout 5m
}

ensure_namespaces() {
    step "Ensuring namespaces exist..."
    kubectl apply -f eks/namespaces.yaml
}

create_irsa() {
    step "Creating IRSA service accounts (one per workload, least-privilege S3 policy)..."
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
}

bootstrap_db() {
    step "Bootstrapping RDS (airflow_db/mlflow_db, DB roles, ported schema, app secrets)..."
    # Also required on `resume`: the connection Secrets live in the cluster and
    # die with it, while the RDS roles survive. 00_create_databases.sql now
    # ALTERs each role's password unconditionally so a regenerated Secret
    # re-syncs instead of silently mismatching.
    ./eks/db-bootstrap/run.sh
}

upload_models() {
    step "Uploading exported_model/ + model_registry.yaml to S3..."
    ./scripts/upload-models.sh
}

build_push_images() {
    step "Building and pushing images to ECR..."
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
}

# ---------------------------------------------------------------------------
# BOOTSTRAP -- everything below hands off to ArgoCD
#
# deploy_workloads() used to live here: five `helm upgrade --install` calls and
# three `kubectl apply`s that WERE the definition of what ran in the cluster.
# Under GitOps that definition lives in gitops/, and this script must not also
# deploy -- two controllers reconciling the same releases fight, and ArgoCD
# wins on a delay, so the symptom is a helm change that "works" and then
# silently reverts minutes later.
#
# What remains is the irreducible bootstrap: ArgoCD cannot install itself, and
# the secrets below cannot live in git.
# ---------------------------------------------------------------------------

bootstrap_secrets() {
    step "Ensuring the Airflow webserver secret key exists (fixed, not chart-regenerated -- regenerating invalidates all sessions)..."
    kubectl -n $AIRFLOW_NAMESPACE get secret airflow-webserver-secret > /dev/null 2>&1 || \
        kubectl -n $AIRFLOW_NAMESPACE create secret generic airflow-webserver-secret \
            --from-literal=webserver-secret-key=$(openssl rand -hex 16)

    step "Ensuring the Grafana admin secret exists..."
    # Created here rather than left to the chart's default admin/prom-operator.
    kubectl -n $MONITORING_NAMESPACE get secret grafana-admin > /dev/null 2>&1 || \
        kubectl -n $MONITORING_NAMESPACE create secret generic grafana-admin \
            --from-literal=admin-user=admin \
            --from-literal=admin-password=$(openssl rand -base64 18 | tr -d '/+=')

    # TODO (Day 3, blocked on a Secrets Manager entry): these two move to
    # External Secrets Operator, at which point this function disappears and
    # the last imperative step in the deploy path goes with it.

    step "Installing the GitOps WRITE deploy key for Airflow..."
    # Airflow is the only workload that commits to the repo: the retraining
    # pipeline deploys a candidate as shadow, and asie_auto_rollback reverts a
    # failing primary. Separate key from ArgoCD's read-only one, so a
    # compromised ArgoCD cannot rewrite desired state.
    #
    # Bootstrapped here rather than via External Secrets for the same reason as
    # the ArgoCD credential: eks/airflow-values.yaml mounts this secret as a
    # volume, so a missing secret is not a degraded feature -- the scheduler
    # and webserver pods never start at all.
    local write_key
    write_key=$(aws secretsmanager get-secret-value \
                  --secret-id "$AIRFLOW_REPO_SECRET_SM" \
                  --region "$REGION" \
                  --query SecretString --output text 2>/dev/null | tr -d '\r')

    if [ -z "$write_key" ]; then
        echo "WARNING: no $AIRFLOW_REPO_SECRET_SM in Secrets Manager." >&2
        echo "  Airflow pods mount this secret and will not start without it." >&2
        echo "  Create a WRITE-scoped deploy key and store it, then re-run." >&2
        exit 1
    fi

    # Same CR strip and trailing newline as the ArgoCD key -- the Windows aws
    # CLI emits CRLF, and an OpenSSH key with carriage returns or without its
    # final newline fails to parse in a way that reads like a revoked key.
    kubectl -n $AIRFLOW_NAMESPACE create secret generic $AIRFLOW_REPO_SECRET \
        --from-literal=ssh-privatekey="${write_key}"$'\n' \
        --dry-run=client -o yaml | kubectl apply -f - > /dev/null
    echo "GitOps write key installed."
}

ensure_repo_credential() {
    # ArgoCD cannot read a private repository without a credential, and the
    # failure is quiet in the worst way: the Application appears, reports
    # "ComparisonError", and nothing ever deploys -- a cluster that looks
    # provisioned and serves nothing.
    #
    # Sourced from Secrets Manager rather than External Secrets, which is NOT
    # an inconsistency: ESO is itself deployed BY ArgoCD, so ArgoCD cannot read
    # the repo to learn how to deploy the thing that would grant it the ability
    # to read the repo. This one credential has to be bootstrapped, and doing
    # it from Secrets Manager is what makes it survive `pause`/`down` instead
    # of needing to be recreated by hand on every rebuild.
    step "Installing the ArgoCD repository credential from Secrets Manager..."

    # `| tr -d '\r'` is load-bearing on Windows. The aws CLI there emits CRLF,
    # and an OpenSSH private key with carriage returns fails to parse -- ssh
    # reports "error in libcrypto" and then "Permission denied (publickey)",
    # which reads exactly like a key that was never added to GitHub. Confirmed
    # by testing the same key with and without the strip.
    local key
    key=$(aws secretsmanager get-secret-value \
            --secret-id "$ARGOCD_REPO_SECRET_SM" \
            --region "$REGION" \
            --query SecretString --output text 2>/dev/null | tr -d '\r')

    if [ -z "$key" ]; then
        cat >&2 <<EOF

ERROR: Secrets Manager has no entry "$ARGOCD_REPO_SECRET_SM".

  ArgoCD needs a read-only deploy key to read $REPO_URL.
  Generate one, add the PUBLIC half to the repo's Deploy keys on GitHub
  (read-only), and store the PRIVATE half:

    ssh-keygen -t ed25519 -N "" -C "argocd-read@asie" -f ./argocd_key
    aws secretsmanager create-secret --name $ARGOCD_REPO_SECRET_SM \\
      --secret-string file://argocd_key --region $REGION
    rm -f ./argocd_key

  Then re-run. Everything before this point is idempotent.

EOF
        exit 1
    fi

    # Recreated every run rather than skipped-if-present: the key can rotate in
    # Secrets Manager, and a stale cluster-side copy would fail authentication
    # in a way that reads like a revoked key rather than a stale cache.
    #
    # The argocd.argoproj.io/secret-type=repository label is what makes ArgoCD
    # DISCOVER this secret at all. Without it the secret exists, looks correct,
    # and is silently ignored.
    # The $'\n' is not cosmetic: $( ) strips every trailing newline, and an
    # OpenSSH key without its final newline is malformed. Same failure mode as
    # the CR above, and just as misleading.
    kubectl -n $ARGOCD_NAMESPACE create secret generic $ARGOCD_REPO_SECRET \
        --from-literal=type=git \
        --from-literal=url="$REPO_URL" \
        --from-literal=sshPrivateKey="${key}"$'\n' \
        --dry-run=client -o yaml \
      | kubectl label --local -f - argocd.argoproj.io/secret-type=repository -o yaml \
      | kubectl apply -f - > /dev/null

    echo "Repository credential installed for $REPO_URL."
}

install_argocd() {
    step "Installing ArgoCD (the one workload git cannot bootstrap)..."
    helm repo add argo https://argoproj.github.io/argo-helm > /dev/null 2>&1 || true
    helm repo update argo > /dev/null

    kubectl create namespace $ARGOCD_NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

    # Pinned: an unpinned chart means the GitOps controller silently upgrades
    # itself on the next `up`, which is a migration wearing a sync's clothes.
    helm upgrade --install argocd argo/argo-cd \
        --version $ARGOCD_CHART_VERSION \
        --namespace $ARGOCD_NAMESPACE \
        -f gitops/bootstrap/argocd-values.yaml \
        --wait --timeout 10m
}

register_root_app() {
    step "Registering the app-of-apps root Application..."
    # The only manifest applied by hand. Everything else is a child of this.
    kubectl apply -f gitops/bootstrap/root-app.yaml

    step "Waiting for ArgoCD to sync the workloads (this is the deploy)..."
    # Sync is asynchronous, so `up` would otherwise return before anything is
    # running and wait_for_alb would look at an Ingress that does not exist.
    for i in $(seq 1 60); do
        synced=$(kubectl -n $ARGOCD_NAMESPACE get applications.argoproj.io \
                 -o jsonpath='{range .items[*]}{.status.sync.status}{"\n"}{end}' 2>/dev/null \
                 | grep -c "Synced" || true)
        total=$(kubectl -n $ARGOCD_NAMESPACE get applications.argoproj.io \
                --no-headers 2>/dev/null | wc -l || echo 0)
        if [ "$total" -gt 0 ] && [ "$synced" -eq "$total" ]; then
            echo "All $total Applications synced."
            break
        fi
        echo "  $synced/$total synced; waiting..."
        sleep 20
    done
    kubectl -n $ARGOCD_NAMESPACE get applications.argoproj.io
}

wait_for_alb() {
    step "Waiting for the ALB to be provisioned..."
    # The Service is ClusterIP now -- the ALB address lives on the Ingress.
    ALB=""
    for i in $(seq 1 30); do
        ALB=$(kubectl get ingress -n $INFERENCE_NAMESPACE asie-inference \
              -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true)
        [ -n "$ALB" ] && break
        sleep 20
    done
    kubectl get ingress -A
    if [ -n "$ALB" ]; then
        echo ""
        echo "  Inference API : http://$ALB/"
        echo "  Grafana       : http://$ALB/grafana"
        echo "  Grafana admin password: kubectl -n $MONITORING_NAMESPACE get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d"
        echo "  Airflow/MLflow UIs are ClusterIP -- use kubectl port-forward (see eks/ingress.yaml)."
    else
        echo "The ALB has no address yet. Check: kubectl describe ingress -n $INFERENCE_NAMESPACE asie-inference"
    fi
}

# ---------------------------------------------------------------------------
# TEAR-DOWN PHASES
# ---------------------------------------------------------------------------

stop_gitops() {
    # MUST run before anything below deletes a workload. Every Application sets
    # selfHeal: true, so a `helm uninstall` while ArgoCD is running is not a
    # teardown -- it is a drift event, and ArgoCD reinstalls the release within
    # minutes. The teardown would appear to succeed and leave a running cluster.
    step "Removing ArgoCD so nothing self-heals during teardown..."

    # Strip the resources-finalizer before deleting. The finalizer makes
    # Application deletion CASCADE to the workloads it owns, which is right for
    # normal operation and wrong here: the teardown below is deliberately
    # ordered -- Ingress first, drained, alone -- and a cascade would delete the
    # Ingress concurrently with everything else, orphaning the shared ALB and
    # hanging `terraform destroy` on subnets whose ENIs are still attached.
    # Orphan the workloads instead and let the ordered teardown do the work.
    for app in $(kubectl -n $ARGOCD_NAMESPACE get applications.argoproj.io -o name 2>/dev/null); do
        kubectl -n $ARGOCD_NAMESPACE patch "$app" --type merge \
            -p '{"metadata":{"finalizers":null}}' > /dev/null 2>&1 || true
    done
    kubectl -n $ARGOCD_NAMESPACE delete applications.argoproj.io --all --ignore-not-found > /dev/null 2>&1 || true

    helm uninstall argocd -n $ARGOCD_NAMESPACE > /dev/null 2>&1 || true
    kubectl delete namespace $ARGOCD_NAMESPACE --ignore-not-found > /dev/null 2>&1 || true
}

teardown_workloads() {
    stop_gitops

    # The Ingress goes FIRST and on its own. It owns the shared ALB, whose ENIs
    # sit in the VPC subnets -- deleting the namespace out from under it can
    # orphan the load balancer, after which terraform destroy hangs trying to
    # delete subnets that still have attachments.
    step "Deleting the shared ALB Ingress and waiting for it to drain..."
    kubectl delete -f eks/ingress.yaml --ignore-not-found || true
    sleep 45

    step "Deleting Helm releases..."
    helm uninstall $INFERENCE_RELEASE -n $INFERENCE_NAMESPACE || true
    helm uninstall $AIRFLOW_RELEASE -n $AIRFLOW_NAMESPACE || true
    helm uninstall $MLFLOW_RELEASE -n $MLFLOW_NAMESPACE || true
    helm uninstall $MONITORING_RELEASE -n $MONITORING_NAMESPACE || true

    # PVCs are not removed by `helm uninstall` -- the operator's volumeClaim
    # templates leave them behind, and an orphaned PVC keeps its EBS volume
    # alive and billing after the cluster is gone.
    step "Deleting monitoring PVCs (helm uninstall leaves these behind)..."
    kubectl delete pvc --all -n $MONITORING_NAMESPACE --ignore-not-found || true

    step "Deleting namespaces..."
    kubectl delete namespace $INFERENCE_NAMESPACE $AIRFLOW_NAMESPACE $MLFLOW_NAMESPACE $MONITORING_NAMESPACE --ignore-not-found || true
}

delete_cluster() {
    step "Deleting the EKS cluster..."
    eksctl delete cluster --name $CLUSTER_NAME --region $REGION || true
}

destroy_infra() {
    # ECR repos and the S3 bucket are Terraform-owned and carry
    # force_delete/force_destroy, so this completes even when they hold
    # images/objects rather than failing halfway through.
    step "Destroying AWS infrastructure with Terraform..."
    cd aws-provision
    terraform destroy -auto-approve
    cd ..

    # These were created with `aws iam create-policy` / eksctl --role-only, so
    # neither Terraform nor `eksctl delete cluster` owns them. Left behind they
    # accumulate and collide with the next `up`.
    step "Removing leftover IAM policies and roles..."
    for p in AsieInferenceS3Policy AsieAirflowS3Policy AsieMlflowS3Policy AWSLoadBalancerControllerIAMPolicy; do
        arn="arn:aws:iam::${ACCOUNT_ID}:policy/$p"
        # A policy can't be deleted while any non-default version exists.
        for v in $(aws iam list-policy-versions --policy-arn "$arn" \
                    --query 'Versions[?!IsDefaultVersion].VersionId' --output text 2>/dev/null); do
            aws iam delete-policy-version --policy-arn "$arn" --version-id "$v" 2>/dev/null || true
        done
        aws iam delete-policy --policy-arn "$arn" 2>/dev/null && echo "  deleted $p" || true
    done
    aws iam detach-role-policy --role-name AmazonEKS_EBS_CSI_DriverRole_asie \
        --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy 2>/dev/null || true
    aws iam delete-role --role-name AmazonEKS_EBS_CSI_DriverRole_asie 2>/dev/null \
        && echo "  deleted AmazonEKS_EBS_CSI_DriverRole_asie" || true

    # The deploy keys, created with `aws secretsmanager create-secret` during
    # the GitOps week and owned by neither Terraform nor eksctl. Left behind
    # they bill ~$0.40/secret/month indefinitely -- small enough to go
    # unnoticed on a credit-funded account and to start charging a card the
    # moment those credits lapse.
    #
    # --force-delete-without-recovery, not the default 30-day window: a
    # teardown that leaves resources scheduled for deletion has not finished,
    # and the private keys are regenerable in seconds. Recovery would only
    # matter if the key were the irreplaceable thing, and it is not -- the
    # GitHub side has to be re-registered either way.
    step "Removing GitOps deploy keys from Secrets Manager..."
    for s in "$ARGOCD_REPO_SECRET_SM" "$AIRFLOW_REPO_SECRET_SM"; do
        aws secretsmanager delete-secret --secret-id "$s" --region "$REGION" \
            --force-delete-without-recovery > /dev/null 2>&1 \
            && echo "  deleted $s" || true
    done

    cat <<EOF

NOTE: the GitHub deploy keys are now orphaned -- their private halves are gone
but the public halves remain registered on the repo. Remove them under
Settings > Deploy keys; nothing here can do that for you.
EOF
}

confirm_destroy() {
    # `down` is the only irreversible command here, and the things it destroys
    # (models in S3, RDS with skip_final_snapshot) are expensive or impossible
    # to restore. Everything else in this script is safe to re-run.
    local models dbsize
    models=$(aws s3 ls "s3://$S3_BUCKET/models/" --recursive --summarize 2>/dev/null \
             | grep "Total Objects" || echo "  Total Objects: unknown")

    cat <<EOF

  ============================================================
   asie.sh down -- THIS PERMANENTLY DESTROYS DATA
  ============================================================

  Will be destroyed, with no backup and no recovery:

    * S3 bucket $S3_BUCKET
      including all versions of:
        - models/           ($(echo "$models" | tr -s ' ' | cut -d: -f2 | tr -d ' ') objects)
        - mlflow-artifacts/ (all experiment artifacts)
        - dvc-data/         (the DVC remote)
    * RDS instance asie-db
      skip_final_snapshot is on: inference_logs, drift_metrics and
      all Airflow/MLflow history are gone, with NO final snapshot.
    * All 3 ECR repositories and every image in them
    * The EKS cluster, VPC, NAT gateway and subnets
    * The IAM policies and roles created outside Terraform

  Re-uploading models to S3 needs a working, sustained upload --
  if that is currently unreliable, use './asie.sh pause' instead:
  it removes compute cost but keeps every byte of data.

EOF

    if [ ! -t 0 ]; then
        echo "Refusing to destroy non-interactively. Re-run from a terminal." >&2
        exit 1
    fi

    printf "  Type exactly 'destroy asie' to proceed: "
    read -r reply
    if [ "$reply" != "destroy asie" ]; then
        echo "  Aborted. Nothing has been changed."
        exit 1
    fi
}

usage() {
    cat <<EOF
Usage: ./asie.sh <command>

  up       Provision infrastructure, build and push images, install ArgoCD and
           hand off. ArgoCD deploys the workloads from gitops/ -- this script
           no longer decides what runs. Safe to re-run; every step is
           idempotent.

  pause    Delete the EKS cluster and workloads. KEEPS S3, ECR, RDS and the
           VPC, so no data is lost. Removes most of the hourly cost (the
           nodes and the control plane); NAT gateway and RDS keep running.

  resume   Rebuild the cluster on top of the surviving data and re-register
           ArgoCD, which redeploys from git. Skips Terraform and the image
           build, since neither was torn down.

  down     Destroy EVERYTHING, including all data in S3 and RDS.
           Irreversible. Asks for confirmation first.
EOF
}

# ---------------------------------------------------------------------------
# COMMANDS
# ---------------------------------------------------------------------------

case "$1" in
    up)
        require_aws
        echo "Starting FULL SETUP..."
        provision_infra
        create_cluster
        cluster_addons
        install_alb_controller
        ensure_namespaces
        create_irsa
        bootstrap_db
        upload_models
        build_push_images
        bootstrap_secrets
        install_argocd
        ensure_repo_credential
        register_root_app
        wait_for_alb
        echo ""
        echo "Setup complete."
        ;;

    pause)
        require_aws
        echo "PAUSING -- deleting compute, keeping all data..."
        teardown_workloads
        delete_cluster
        cat <<EOF

Paused. Still present (and still billing, but far less):
  - S3 bucket $S3_BUCKET (models, artifacts, DVC data)
  - ECR repositories and images
  - RDS instance asie-db
  - VPC and NAT gateway

Bring it back with: ./asie.sh resume
EOF
        ;;

    resume)
        require_aws
        echo "RESUMING -- rebuilding compute on existing data..."
        # No provision_infra: Terraform-managed resources were never removed.
        # No upload_models / build_push_images: S3 and ECR survived the pause.
        create_cluster
        cluster_addons
        install_alb_controller
        ensure_namespaces
        create_irsa
        bootstrap_db
        bootstrap_secrets
        install_argocd
        ensure_repo_credential
        register_root_app
        wait_for_alb
        echo ""
        echo "Resume complete."
        ;;

    down)
        require_aws
        confirm_destroy
        echo "Starting CLEAN TEARDOWN..."
        teardown_workloads
        delete_cluster
        destroy_infra
        echo ""
        echo "Teardown complete. All resources destroyed."
        ;;

    *)
        usage
        exit 1
        ;;
esac
