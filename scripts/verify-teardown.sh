#!/bin/bash
# Proves nothing billable survived `./asie.sh down`.
#
# Deliberately broader than what asie.sh creates. A teardown is only trustworthy
# if it is checked against the bill, not against the script's own inventory --
# the resources that cost money after a project ends are precisely the ones
# nobody remembered creating: an EIP orphaned when its NAT went, a volume left
# by a PVC, a snapshot taken automatically, a log group nobody made explicitly.
#
# Read-only. Prints a non-zero count for anything still alive.
#
#   ./scripts/verify-teardown.sh [region]

REGION="${1:-ap-south-1}"
FOUND=0

check() {
    local label="$1" count="$2" detail="$3"
    if [ "$count" = "0" ] || [ -z "$count" ] || [ "$count" = "None" ]; then
        printf '  \033[32mOK\033[0m    %-34s 0\n' "$label"
    else
        printf '  \033[31mALIVE\033[0m %-34s %s\n' "$label" "$count"
        [ -n "$detail" ] && echo "          $detail"
        FOUND=$((FOUND + 1))
    fi
}

q() { aws --region "$REGION" "$@" 2>/dev/null | tr -d '\r'; }

echo ""
echo "Teardown verification -- region $REGION -- $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "-----------------------------------------------------------------"
echo ""
echo "  COMPUTE"
check "EKS clusters"          "$(q eks list-clusters --query 'length(clusters)' --output text)"
check "EC2 instances (running)" "$(q ec2 describe-instances --filters Name=instance-state-name,Values=running,pending --query 'length(Reservations[].Instances[])' --output text)"
check "Auto Scaling groups"   "$(q autoscaling describe-auto-scaling-groups --query 'length(AutoScalingGroups)' --output text)"

echo ""
echo "  NETWORK  (the expensive ones)"
check "NAT gateways"          "$(q ec2 describe-nat-gateways --filter Name=state,Values=available,pending --query 'length(NatGateways)' --output text)"
check "Elastic IPs"           "$(q ec2 describe-addresses --query 'length(Addresses)' --output text)" "unattached EIPs bill hourly"
check "Load balancers"        "$(q elbv2 describe-load-balancers --query 'length(LoadBalancers)' --output text)"
check "Classic load balancers" "$(q elb describe-load-balancers --query 'length(LoadBalancerDescriptions)' --output text)"
check "VPCs (non-default)"    "$(q ec2 describe-vpcs --filters Name=isDefault,Values=false --query 'length(Vpcs)' --output text)"
check "VPC endpoints"         "$(q ec2 describe-vpc-endpoints --query 'length(VpcEndpoints)' --output text)" "interface endpoints bill hourly; gateway endpoints are free"

echo ""
echo "  STORAGE  (survives instance deletion)"
check "EBS volumes"           "$(q ec2 describe-volumes --query 'length(Volumes)' --output text)" "orphaned PVC volumes live here"
check "EBS snapshots (self)"  "$(q ec2 describe-snapshots --owner-ids self --query 'length(Snapshots)' --output text)"
check "S3 buckets"            "$(aws s3api list-buckets --query 'length(Buckets)' --output text 2>/dev/null | tr -d '\r')" "global, not regional"

echo ""
echo "  DATA"
check "RDS instances"         "$(q rds describe-db-instances --query 'length(DBInstances)' --output text)"
check "RDS manual snapshots"  "$(q rds describe-db-snapshots --snapshot-type manual --query 'length(DBSnapshots)' --output text)" "automated snapshots die with the instance; manual ones do not"
check "RDS subnet groups"     "$(q rds describe-db-subnet-groups --query 'length(DBSubnetGroups)' --output text)" "free, but blocks VPC deletion"

echo ""
echo "  REGISTRY / SECRETS / LOGS"
check "ECR repositories"      "$(q ecr describe-repositories --query 'length(repositories)' --output text)"
check "Secrets Manager"       "$(q secretsmanager list-secrets --query 'length(SecretList)' --output text)" "~\$0.40/secret/month; force-delete to purge immediately"
# Counts CUSTOMER-managed keys only. `kms list-keys` returns AWS-managed
# defaults too (aws/rds, aws/ebs, aws/secretsmanager), which are free, cannot
# be deleted, and would otherwise show as a permanent false alarm -- the fastest
# way to make a verification script ignored is to have it cry wolf.
CMK=0
for k in $(q kms list-keys --query 'Keys[].KeyId' --output text); do
    mgr=$(q kms describe-key --key-id "$k" --query 'KeyMetadata.KeyManager' --output text)
    [ "$mgr" = "CUSTOMER" ] && CMK=$((CMK + 1))
done
check "KMS customer-managed keys" "$CMK" "~\$1/month each; AWS-managed defaults are free and excluded"
check "CloudWatch log groups" "$(q logs describe-log-groups --query 'length(logGroups)' --output text)" "EKS control-plane logs persist after the cluster"

echo ""
echo "  LEFTOVER STACKS"
check "CloudFormation stacks" "$(q cloudformation describe-stacks --query 'length(Stacks)' --output text)" "eksctl leaves these if a delete half-fails"

echo ""
echo "-----------------------------------------------------------------"
if [ "$FOUND" = "0" ]; then
    echo "  Clean. Nothing billable remains in $REGION."
else
    echo "  $FOUND resource type(s) still alive -- see ALIVE rows above."
    echo ""
    echo "  Not checked here, because AWS cannot see them:"
    echo "    * GitHub deploy keys (repo Settings > Deploy keys)"
    echo "    * Any resource in another region -- re-run with: $0 <region>"
fi
echo ""
exit 0
