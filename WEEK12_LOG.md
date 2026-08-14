# Week 12 — GitOps Deployment: Daily Log

One entry per day: the plan written before the work, the outcome written after. Design lives in `DEPLOYMENT_ARCHITECTURE.md`; the week's rationale in `GITOPS_AND_OPTIMIZATION_PLAN.md`.

**Test environment note.** The Windows Python (Anaconda) lacks `transformers` and `mlflow`, and `test/conftest.py` imports the FastAPI app at collection time — so *nothing* collects there. The project's real test env is the WSL/Ubuntu venv at `.venv/` (Python 3.12), which has the full dependency set. All test runs below are from there.

**Baseline before Day 2 (2026-08-14):** `28 passed, 5 failed`. The five are pre-existing and environmental — `test_health` (2), `test_pipeline` (1), `test_predict` (2) — all needing loaded model artifacts. Every later run is judged against this number, not against zero.

---

## Day 1 — Deployment Architecture ✅

**Delivered:** `DEPLOYMENT_ARCHITECTURE.md` — GitOps architecture, deployment workflow, promotion policy, rollback strategy. Plus the `gitops/` app-of-apps scaffold and the `asie.io/model-version` pod annotation (committed earlier as `62f4c98`).

**Surfaced two blocking defects** (§6 of that doc), which set the Day 2 agenda:
- **6.1** — `export_models()` overwrites a fixed S3 prefix, so model rollback is impossible: reverting the git pointer re-syncs the same overwritten weights.
- **6.2** — `PRIMARY_MODEL_VERSION` etc. are hardcoded constants written into every `inference_logs` row, so rows from different shadow models are indistinguishable and the online promotion gate would compute over a mixture.

---

## Day 2 — Automated Model Promotion

**Notion deliverables:** MLflow promotion automation · stage transition logic · approval workflow.

### Plan

Defect fixes first — both are prerequisites, not cleanup. The promotion gate cannot be written correctly on top of either bug.

1. **Fix 6.2 — version plumbing.** Replace the hardcoded version constants with values resolved from the pod environment, sourced from `gitops/values/inference.yaml` via the chart ConfigMap. `/predict` then records the *actual* primary and shadow versions on every row.
2. **Fix 6.1 — versioned S3 layout.** `export_models()` writes to `models/<run_id>/…` instead of overwriting `models/primary/…`. The initContainer syncs only the prefixes the pod's values name. Exports become append-only, making `model.version` a real content pointer and `git revert` a real rollback.
3. **Promotion gate** — a new module implementing §4 of the architecture: the offline gate already exists in `register_shadow_model()`; add the online gate over `inference_logs` (sample count, shadow failure rate, p95 latency, disagreement band) returning an explicit decision with reasons.
4. **Tests** against the WSL venv, held to the 28-pass baseline.

### Outcome ✅

**Tests: 47 passed, 5 failed** — up from 28 passed, and the 5 failures are the same pre-existing ones. No regressions. 21 of the new tests cover the promotion policy.

**6.2 fixed — version plumbing.** `PRIMARY_MODEL_VERSION`/`SHADOW_MODEL_VERSION`/`SERVED_MODEL_VERSION` are gone as literals; a single `DEFAULT_MODEL_VERSION = "unset"` remains as a fallback that is deliberately implausible, so a broken env shows up as obviously wrong rather than as plausible data. Real values flow `gitops/values/inference.yaml` → chart ConfigMap → pod env → `Settings` → every `inference_logs` row. The version is now the MLflow `run_id`, so one identifier spans training, S3 storage, the pod annotation, and the database row. `/predict` also reports the actual primary version in its response instead of the static `"v0"`.

**6.1 fixed — versioned S3 layout.** `export_models()` uploads to `models/<run_id>/` instead of overwriting `models/primary/`. Exports are append-only, so a git revert of a version pointer now reaches content that still exists. Added a skip when the prefix is already populated — a run that is already the shadow would otherwise re-upload ~250 MB on every promotion. The initContainer fetches only the two prefixes its values name, with three branches (distinct / shadow==primary / no shadow), all four cases exercised against a stubbed `aws` since there is no cluster to run them on.

**Promotion policy implemented** (`src/models/promotion.py`). Offline decides *better*, online decides *safe*, and the module owns only the decision — deliberately separable from S3, MLflow and Kubernetes, which is what makes it testable at all. Two things worth recording:

- The offline half compares shadow against **primary**, which is *not* the gate `register_shadow_model()` applies — that one compares a new candidate against the current *shadow*. A model can therefore be legitimately registered as the best candidate so far while still being worse than what is serving. Promoting on the registration gate alone would regress production, and this was not obvious until the two gates were written next to each other.
- `promote_to_primary()` was unconditional *and* uncalled — a mechanism with no policy. It is now gated, with `force=True` as the human-approval path for the `HOLD` verdict, recording who approved it.

**A test caught a real bug.** `_percentile` used `round()`, and Python's banker's rounding turned rank 95.5 into 96, returning the 96th value for p95 of 100 samples. Fixed to `ceil`, which is the nearest-rank definition.

**Not done today:** the DAG task that commits the promoted version to git. It needs a repo deploy key in the cluster, which lands with the ArgoCD wiring on Day 3.

**Follow-on (same day):** S3 lifecycle expiry for the now-append-only `models/` prefix — 90 days, chosen against the rollback window rather than storage price. Rolling back to something that has not served since last quarter is a re-deploy, not a rollback. `terraform validate` passes; not applied.

---

## Day 3 — GitOps with ArgoCD 🔵 In progress

**Notion deliverables:** ArgoCD installation · Git repository configuration · automatic synchronization.

### Plan

Blocked on two decisions (cluster up? repo credential type?), so this day splits: everything that does not need a live cluster first, then the install itself.

1. Cut `asie.sh` back to bootstrap-only — the blocking correctness issue, since until it is done both `asie.sh` and ArgoCD can deploy and will fight.
2. External Secrets manifests for the two imperative secrets, with a placeholder ARN.
3. Install + first sync — needs the cluster.

### Outcome so far

**`asie.sh` no longer deploys.** `deploy_workloads()` removed; `bootstrap_secrets`, `install_argocd`, `ensure_repo_credential`, `register_root_app` replace it in both `up` and `resume`. `register_root_app` waits for Applications to reach Synced, because sync is asynchronous and `up` would otherwise return before anything was running.

**Teardown was the bigger find.** With `selfHeal: true` on every Application, the existing `helm uninstall` path had silently stopped being a teardown — ArgoCD would reinstall each release within minutes and the script would report success over a still-running cluster. `stop_gitops()` now runs first, and strips the `resources-finalizer` rather than letting deletion cascade: cascade is correct in normal operation but would delete the Ingress concurrently with everything else, orphaning the shared ALB and hanging `terraform destroy` on subnets with live ENIs. The existing carefully-ordered teardown still does the deleting.

`bash -n` passes. **Nothing here has been run against a cluster** — there isn't one up.

### Outcome ✅ — full rebuild, GitOps deploy verified end to end

`./asie.sh pause` then `./asie.sh up` against a real account. Cluster destroyed and recreated from scratch (14:29), ArgoCD installed (15:08), all seven Applications created and syncing from `origin/gitops-deployment`.

**Verified live, through the ALB:**

```
/health   {"status":"ok","primary_ready":true,"shadow_ready":true,...}
/predict  {"predictions":[{"label":"LABEL_2","score":0.9944}],
           "model_version":"ddb90ee0a2654f5cac1bff3f66fe76f3","latency_ms":93.1}
```

Both Day 2 fixes are confirmed against reality, not just tests:

- **6.1** — the initContainer fetched two run_id-keyed S3 prefixes and the app loaded both models. The pod template carries `asie.io/primary-model-version` and `asie.io/shadow-model-version`.
- **6.2** — `inference_logs` now shows the before/after in one query: the newest row carries `ddb90ee0…`/`286aecc6…`, the 37 older rows carry `v_01`/`v_02`. That is exactly the mixture the promotion gate would have computed over.

**The promotion gate, run against live production data:**

```
samples=1, failures=0, disagreement=0.0,
shadow_p95=99.6ms vs primary_p95=93.1ms (ratio 1.07, limit 1.25)
DECISION: insufficient_data — "only 1 shadow predictions, need 1000"
```

Correctly scoped to the shadow's run_id and correctly refusing: the shadow is offline-better (0.9824 vs 0.9715) but has no online evidence yet.

### What the rebuild caught that nothing offline could

**The ALB controller gap, and it was worse than predicted.** Nothing in the repo installed it. Both Ingress objects were created by ArgoCD and sat with **no address for two hours** — every Application `Healthy`, every pod `Running`, and nothing reachable from outside. The same "looks healthy, isn't" failure mode as Week 11. Added `install_alb_controller()` to `asie.sh`, wired into `up` and `resume`; the ALB now provisions and both Ingresses share one load balancer, confirming the `group.name` merge.

**`create_cluster` tested existence, not status.** `eksctl get cluster` succeeds for a `DELETING` cluster, so a back-to-back `pause`/`up` — the obvious way to test a rebuild — reported "already exists, skipping creation" and handed every later step a control plane vanishing underneath it. Now reads `cluster.status` and waits it out.

**The deploy key round-trip was broken twice.** The Windows `aws` CLI emits CRLF, which makes an OpenSSH key fail to parse as `error in libcrypto` → `Permission denied (publickey)` — indistinguishable from a key never added to GitHub. And `$( )` strips the trailing newline an OpenSSH key requires. Both caught by testing the key against GitHub *before* relying on it.

**The gate cannot run in the serving image.** `boto3` is absent from the slimmed serving requirements (correct — the initContainer does the S3 work), so `load_registry()` fails there. The promotion task belongs in the Airflow image, which has the full dependency set. Worth knowing before Day 4 wires it.

### Open, carried to Day 4

- **`airflow` OutOfSync** on `StatefulSet/airflow-scheduler`, and **`asie-root` OutOfSync** on exactly the two *multi-source* Applications. All workloads are Healthy with zero restarts, so this is phantom drift — most likely ArgoCD defaulting fields on `sources:`/`ref:` that the plain YAML doesn't carry. Needs `argocd app diff` to confirm rather than guess. Harmless now, but with `selfHeal: true` a permanent diff is a standing re-sync loop.
- **Process-liveness checks proved unreliable here.** A run that was very much alive showed no matching processes and an empty (block-buffered) log, and I reported it as dead. AWS state was the accurate signal. Poll the thing being built, not the builder.

### Still blocked

- **Write-scoped credential** for the promotion commit from Airflow — deliberately separate from ArgoCD's read key so a compromised ArgoCD cannot rewrite desired state.

---

## Day 4 — Rolling Deployments ✅

**Notion deliverables:** rolling updates · zero-downtime deployment · deployment verification.

### Outcome

**The phantom drift was a real bug, found by diffing rather than guessing.** Comparing the live Application spec against the git manifest gave `retry: git={...} live=null`. `spec.retry` is not a field on the Application CRD — ArgoCD nests it inside `syncPolicy` — so the API server pruned it. Two silent consequences: the retry/backoff policy never applied (added precisely for CRD-heavy syncs that exceed one attempt), and the pruned field read as permanent drift, which is why `asie-root` sat OutOfSync on exactly those two Applications. The multi-source shape was a red herring; they were simply the only two carrying a `retry` block. Under `selfHeal: true` a diff that can never close is a standing re-sync loop. Fixed; `asie-root` is now Synced.

**Zero-downtime was NOT free, contrary to the Day 1 assumption.** A rolling update polled every 2s gave:

```
144 x 200, 1 x 502  — the 502 landing exactly at the version transition
286aecc6 (34 polls) -> [502] -> ddb90ee0 (110 polls)
```

`maxUnavailable` floors to 0 at one replica, so the new pod is Ready before the old is told to stop — but Kubernetes and the ALB deregister independently. The kubelet terminates the old pod while its IP is still a registered target, and the ALB keeps routing there for the seconds deregistration takes. Day 1's §5 "Layer 0 — already in place" was too generous: probes prevent a *broken* model taking traffic, they do not make a *healthy* rollout seamless.

Fixed on both sides of the race — preStop `sleep 20` with `terminationGracePeriodSeconds` derived as delay+25 (deregistration), and `pod-readiness-gate-inject` on the namespace so a pod is not Ready until the ALB has registered it (registration). **Verified: 150/150 × 200, zero failures.**

Note the intermediate run still showed one 502: the rollout that *installs* the drain hook replaces a pod that predates it. A fix to termination behaviour cannot validate itself on the deploy that introduces it.

**Rollback proven end to end.** `git revert` of a model-version commit rolled production back, ArgoCD syncing automatically. That only reaches real weights because Day 2 made exports run_id-keyed and append-only — under the old fixed-prefix layout the revert would have re-fetched the same overwritten bytes and silently changed nothing. Day 6's Layer 1 is therefore already demonstrated.

### A measurement lesson worth keeping

An apparent **50% failure rate** was entirely client-side: `curl` against the ALB hostname without `-4` alternates `000`/`200` on this Windows host, while both A records return 200 addressed directly and `-4` gives 6/6. I nearly reported a healthy stack as half-broken. Combined with the earlier "no processes running" during a live run, the pattern is consistent: **verify the instrument before believing the measurement.**
