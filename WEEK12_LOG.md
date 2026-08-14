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

### Blocked on

1. **Is the cluster up?** Day 3's remainder is install + first sync; `./asie.sh up` is real spend and the user's call.
2. **Repo credential** — read-only deploy key vs PAT. A GitHub-side action nobody else can do.
3. **A second, write-scoped credential** for the promotion commit from Airflow. Deliberately separate, so a compromised ArgoCD cannot rewrite desired state.
