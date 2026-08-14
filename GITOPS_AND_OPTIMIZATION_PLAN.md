# GitOps & Optimization — Plan and Rationale

Covers the next two weekly phases of ASIE, **in the order they will actually be done**:

1. **GitOps Deployment** (Weekly Plan Week 12) — *now*
2. **GPU & Cost Optimization** (Weekly Plan Week 13) — *after*

Companion to `AWS_ARCHITECTURE.md`, which covers Week 11. Same intent: record the plan *and* the reasoning, including what was rejected, so the decisions are legible later.

---

## 0. Why these two weeks are being swapped

The Weekly Plan originally numbered GPU & Cost as 12 and GitOps as 13. They have been **renumbered in Notion** rather than merely reordered: GitOps is now Week 12 (2026-08-14 → 08-20), GPU & Cost is Week 13 (08-21 → 08-27), and Week 14 follows (08-28 → 09-03). Numbering follows execution order, so "Week 12" means the same thing in Notion, in this document, and in conversation.

The reasoning:

**The Week 14 demo is "drift → retrain → deploy end-to-end." GitOps is the only missing leg.** Drift detection works. Retraining works — the last of it was fixed on 2026-08-14. The deploy leg does not exist at all: `retraining_pipeline.py` pushes new weights to S3, but serving pods hold whatever their initContainer synced at startup, and nothing triggers a rollout. GPU & Cost makes a working leg faster; GitOps builds a leg that isn't there.

**The ordering risk is asymmetric.** Running short on time with GPU-accelerated retraining but no auto-deploy leaves the closed loop visibly broken — the single most compelling property of the project. Running short with GitOps done but CPU-only retraining is a complete story that is merely slower.

**Cost work done first would be done twice.** Spot instances, node selectors, tolerations, right-sized resource requests, HPA tuning — every one of those edits the Helm values and manifests ArgoCD is about to take ownership of. Done by hand now, they get re-encoded declaratively next week. Done after, each cost change ships as a pull request *through* the pipeline, and the GPU/cost week becomes live demo material for the GitOps week's work.

**Spot instances introduce random pod death.** Declarative reconciliation and one-click rollback should exist *before* that failure mode is introduced, not while debugging it.

The one real argument for cost-first is that the cluster bills while it is up (EKS control plane + NAT Gateway + RDS + ALB, roughly $130–140/month if left running). That is already mitigated operationally by `./asie.sh pause` and `down`. It is a habit, not a week of engineering.

**Action independent of ordering:** file the AWS GPU quota increase (`g4dn`/`g5` On-Demand vCPUs) now. New accounts frequently have a limit of 0 and approval can take several days — otherwise it silently consumes the first two days of the GPU & Cost week.

---

## 1. Week 12 — GitOps Deployment

### 1.1 The problem being solved

`asie.sh deploy_workloads()` is currently the source of truth for what runs in the cluster: five `helm upgrade --install` invocations and three `kubectl apply`s, with the image tag resolved at runtime from ECR. That has three specific failure properties:

1. **Cluster state is not knowable from the repo.** What is actually running is whatever the last person to run the script produced, with whatever `--set` flags were in effect. Drift is invisible.
2. **No automated rollout path for a retrained model.** This is the concrete gap above.
3. **No rollback primitive.** Recovering from a bad deploy means re-running the script against an older commit and hoping the imperative steps are idempotent in the right order.

### 1.2 What GitOps means here, concretely

Git becomes the desired state. ArgoCD runs in-cluster, watches the repo, and continuously reconciles. The deliverable is not "ArgoCD is installed" — it is *`asie.sh` no longer decides what runs.*

**Structure — app-of-apps.** A `gitops/` tree at the repo root:

```
gitops/
  bootstrap/        ArgoCD install + the root Application
  apps/             one ArgoCD Application per workload
  values/           environment-specific Helm values ArgoCD reads
```

A single root Application points at `gitops/apps/`; each child Application owns one workload (inference, mlflow, airflow, kube-prometheus-stack, ingress + monitoring rules). Adding a workload becomes adding a file, which is the property that makes the structure worth having.

**Ordering — sync waves.** `deploy_workloads()` encodes two real ordering constraints in comments: MLflow must precede Airflow (the DAG's env points at its Service DNS), and kube-prometheus-stack must precede the inference chart (it owns the ServiceMonitor CRD). These become `argocd.argoproj.io/sync-wave` annotations. This is a genuine improvement over a shell script: the constraint is declared on the object that has it, rather than implied by line order in a function.

**Image tags — the actual model-rollout mechanism.** Today the tag is resolved at deploy time by querying ECR, with a `:latest` fallback. Under GitOps the tag lives in a values file in git. Promotion becomes a commit. This is what closes the loop:

```
drift detected → retrain → register/promote in model registry
   → new image tag (or model version) committed to gitops/values/
   → ArgoCD detects drift from desired state → syncs → rolling update
```

Note that ASIE has *two* things that can change independently: the container image and the model artifact in S3. The image tag handles the former. For the latter, the pod spec needs to carry the promoted model version so that a model promotion changes the pod spec and therefore triggers a rollout — a model version annotation on the pod template, written by the promotion step. Without that, S3 changes underneath a running pod and nothing restarts, which is exactly today's bug.

**Secrets stay out of git.** `deploy_workloads()` currently generates the Airflow webserver key and Grafana admin password imperatively with `openssl rand` if absent. Those cannot move into the repo. They move to AWS Secrets Manager, read into the cluster by External Secrets Operator, which is itself an ArgoCD Application. The RDS credential already lives in Secrets Manager, so this extends an existing pattern rather than inventing one.

**What `asie.sh` keeps.** There is an irreducible bootstrap: something must create the cluster before ArgoCD can run on it. `asie.sh` shrinks to provisioning and bootstrap — Terraform, `eksctl`, cluster addons, IRSA, install ArgoCD, register the root Application — and then stops. Everything past that point is git's job. `pause`/`resume`/`down` still work, because they operate on infrastructure, not workloads.

### 1.3 Rejected alternatives

| Option | Why not |
|---|---|
| `kubectl rollout restart` in the retraining DAG | Treats the symptom. Gives no rollback, no audit trail, no drift detection, and would be deleted a week later. Explicitly declined 2026-08-14. |
| Flux instead of ArgoCD | Reasonable and lighter, but ArgoCD's UI makes sync state and drift *visible*, which matters for a portfolio project that has to be demonstrable to someone watching. |
| Convert Helm charts to Kustomize | Large rewrite of working, already-validated charts for no gain — ArgoCD renders Helm natively. |
| Separate config repo | Standard at organizational scale, where cluster config and app code have different reviewers. Here it splits one project across two repos and doubles the bookkeeping for one person. |

### 1.4 Definition of done

- `./asie.sh up` on an empty account produces a fully running stack with ArgoCD owning every workload.
- All five workloads show **Synced / Healthy** in ArgoCD.
- A model promotion commit triggers an automatic rolling update with no manual step and no downtime — verified by polling `/health` through the ALB across the rollout.
- Reverting that commit rolls back.
- A hand-edited live resource is detected as drift and reverted by ArgoCD.

---

## 2. Week 13 — GPU & Cost Optimization

Deferred to second, and shaped by the fact that GitOps will already exist: every change below lands as a pull request, not a `--set` flag.

**Primary goal (per the Weekly Plan): make retraining production-real.**

- **GPU training jobs.** A GPU node group (`g4dn.xlarge`), tainted so nothing else schedules on it, with the retraining pods carrying matching tolerations and node selectors. Requires the quota request above.
- **FP16 / mixed precision.** Straightforward in the existing HuggingFace `Trainer` config; the meaningful work is confirming that accuracy holds versus the FP32 baseline already in MLflow — the existing experiment tracking is what makes that a measurement rather than an assumption.
- **Spot instances.** The largest cost lever, and the one that needs GitOps in place first. Training jobs are interruption-tolerant if checkpointing is correct; serving is not, and should stay on-demand. This split is the actual design decision.
- **Right-sizing.** The inference pods' current requests/limits were set before any real load data existed. Prometheus has been collecting since Week 11 Day 6 — the numbers now exist to set these from evidence.
- **Scale-to-zero for the GPU group.** Idle GPU nodes are the most expensive way to run nothing.

**Definition of done:** a retraining run executes on GPU infrastructure, cost per training run is measured against the CPU baseline, and serving remains on-demand and uninterrupted throughout.

---

## 3. Status

| | |
|---|---|
| Week 11 — AWS Migration | ✅ Completed 2026-08-14 |
| Week 12 — GitOps Deployment | 🔵 Active, 2026-08-14 → 08-20 — branch `gitops-deployment` (off `main`). Day 1 design: `DEPLOYMENT_ARCHITECTURE.md` |
| Week 13 — GPU & Cost Optimization | ⚪ Next, 2026-08-21 → 08-27 |
| Week 14 — Closed Loop & Demo | ⚪ Planned, 2026-08-28 → 09-03 |

This document is updated as reality diverges from the plan, in the manner of `AWS_ARCHITECTURE.md` §"what the first real deploy surfaced" — the divergences are the part worth reading later.
