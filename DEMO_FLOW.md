# ASIE — Demo Flow

A runnable script for presenting the platform. Timings are measured from the 2026-08-14 run.

**Total: ~35 minutes** live, or ~8 minutes if you skip the retraining wait and narrate §3 from `DEMO_REPORT.md`.

---

## 0. Before you start (~30 min, do it beforehand)

```bash
./asie.sh resume          # ~25 min: cluster, addons, IRSA, RDS, ArgoCD, sync
kubectl get ingress -A    # grab the ALB hostname
export ALB=<hostname>
```

Then generate traffic so the promotion gate has evidence to reason about — the gate needs ≥1000 samples, and an empty database makes for a dull demo:

```bash
for i in $(seq 1 300); do
  curl -4 -s -o /dev/null -X POST "http://$ALB/predict" \
    -H 'Content-Type: application/json' \
    -d '{"text":"quarterly profits rose sharply"}'
done
```

> **Always use `curl -4`.** Without it, curl on some hosts alternates between the ALB's two A records in a way that yields ~50% connection failures — a client-side artifact that looks exactly like a broken service. This cost an hour to diagnose once.

---

## 1. "It serves" (2 min)

```bash
curl -4 -s "http://$ALB/health" | jq
curl -4 -s -X POST "http://$ALB/predict" -H 'Content-Type: application/json' \
     -d '{"text":"the company reported record quarterly profits"}' | jq
```

**Point out:** `model_version` in the response is the MLflow `run_id` — one identifier spanning training, S3 storage, the pod annotation, and the database row. Not a hand-maintained label.

```bash
kubectl -n asie-inference get rollout asie -o jsonpath='{.spec.template.metadata.annotations}' | jq
```

**Point out:** primary *and* shadow are deployed. Shadow runs on 100% of traffic with its output logged and never returned — full-traffic evaluation at zero blast radius.

---

## 2. "Git is the source of truth" (3 min)

```bash
kubectl -n argocd get applications
```

Seven Applications, all `Synced`. Then show the deploy lever:

```bash
cat gitops/values/inference.yaml | grep -A3 "^model:"
```

**The line to land:** *"There is no deploy command. Deploying a model is a commit to this file. Rolling back is `git revert`."*

Then demonstrate that the cluster is not a place you fix things:

```bash
kubectl -n asie-inference scale rollout asie --replicas=3
sleep 60
kubectl -n asie-inference get rollout asie      # back to 1 — selfHeal reverted it
```

---

## 3. "It notices, retrains, and refuses bad models" (~12 min, or narrate)

```bash
POD=$(kubectl -n asie-inference get pod -l app=asie -o jsonpath='{.items[0].metadata.name}')
kubectl -n asie-inference exec $POD -- python -c "
from src.drift.storage.drift_metrics_repository import get_latest_drift_metric
print('drift:', get_latest_drift_metric())"
```

Induce real drift — send inputs the model was never trained on:

```bash
for t in "preheat the oven to 200 degrees" "the cat sat on the mat" \
         "she ran twelve kilometres at sunrise" "mix flour sugar and eggs"; do
  for i in $(seq 1 12); do
    curl -4 -s -o /dev/null -X POST "http://$ALB/predict" \
      -H 'Content-Type: application/json' -d "{\"text\":\"$t\"}"
  done
done

kubectl -n asie-inference exec $POD -- python -c "
from src.drift.worker import run_drift_job
r = run_drift_job(window_hours=1.0)
print('drift score:', float(r['final_drift_score']))"
```

**Expect ~0.7** against a 0.5 threshold. Show *why* it drifted — `input_length`, `word_count` and `prediction_drift` are the movers, which is exactly right for cooking sentences hitting a financial model.

Trigger the pipeline:

```bash
kubectl -n airflow exec airflow-scheduler-0 -c scheduler -- \
  airflow dags trigger asie_retraining_pipeline --run-id demo-$(date +%s)
```

Training takes ~10 minutes on CPU. **If it rejects the model, that is the best possible outcome — lean into it:**

> "It trained a model, compared it against the incumbent, found it worse, and deployed nothing. The gate isn't decoration."

---

## 4. "It decides on evidence" (3 min) — the centrepiece

```bash
kubectl -n airflow exec airflow-scheduler-0 -c scheduler -- python -c "
from src.models.model_registry import load_registry
from src.models.promotion import evaluate_promotion, collect_shadow_evidence
reg = load_registry()
print(collect_shadow_evidence(reg['shadow']['run_id']))
print(evaluate_promotion(reg).decision, evaluate_promotion(reg).reasons)"
```

**The idea to convey:** `true_label` is NULL on every production row. There is no ground truth online. So:

- **offline** `eval_f1` on a held-out set decides *better*
- **online** evidence decides *safe* — sample count, soak duration, shadow failure rate, p95 latency ratio

And the subtle one: **disagreement is not a correctness signal.** With no ground truth, a candidate disagreeing on 40% of traffic means the models differ, not that the candidate is wrong. So it returns `HOLD` for review rather than rejecting. That is the only place a human enters the loop, and deliberately so.

Then promote with a compressed soak, saying openly that it is compressed:

```bash
kubectl -n airflow exec airflow-scheduler-0 -c scheduler -- python -c "
from src.models.model_registry import load_registry, promote_to_primary
from src.models.promotion import evaluate_promotion
from src.gitops.values_writer import update_deployed_version
reg = load_registry(); sh = reg['shadow']['run_id']
print(evaluate_promotion(reg, min_soak_hours=1.0).decision)
promote_to_primary(force=True, approved_by='demo')
print(update_deployed_version(key='primaryVersion', version=sh,
      message='promote: primary -> ' + sh))"
```

---

## 5. "It ships safely" (~8 min) — run the poller in a second terminal

```bash
# terminal 2, START THIS FIRST
while true; do
  curl -4 -s -m 10 -X POST "http://$ALB/predict" -H 'Content-Type: application/json' \
    -d '{"text":"quarterly profits rose sharply"}' \
  | grep -o '"model_version":"[^"]*"' | cut -c18-25
  sleep 2
done
```

```bash
# terminal 1
kubectl -n argocd annotate app asie-inference argocd.argoproj.io/refresh=hard --overwrite

watch -n5 'kubectl -n asie-inference get ingress asie-inference \
  -o jsonpath="{.metadata.annotations.alb\.ingress\.kubernetes\.io/actions\.asie}" \
  | grep -o "\"Weight\":[0-9]*"'
```

Terminal 2 shows the served version **changing mid-stream** as weights move `20/80 → 50/50 → 0/100`, with no failed requests. That is the moment worth pausing on: users are being served by two different model versions simultaneously, in the ratio the ALB was told to use.

```bash
kubectl -n asie-inference get analysisrun    # the gates that let each step through
```

---

## 6. "It heals itself" (3 min)

```bash
kubectl -n airflow exec airflow-scheduler-0 -c scheduler -- python -c "
from datetime import datetime, timezone
from src.models.rollback import evaluate_rollback
reg = {'primary': {'run_id':'CURRENT','promoted_at': datetime.now(timezone.utc).isoformat()},
       'history': [{'stage':'primary','run_id':'PREVIOUS'},{'stage':'primary','run_id':'CURRENT'}]}
bad = {'request_rate':5.0,'error_rate_abs':2.0,'error_ratio':0.4,'primary_loaded':1}
d = evaluate_rollback(reg, prometheus_address='http://unused', health=bad)
print(d.action, '->', d.target_version, '|', d.reasons[0])"
```

**Two guards worth explaining, because they are what separates this from a naive watchdog:**

1. **The age guard.** A model healthy for days that suddenly errors is far more likely a platform failure than a model defect that waited three days to appear. Rolling back fixes none of those and adds a deploy to an incident.
2. **It rolls back to the previous *primary*, never the shadow.** The shadow is the next candidate — rolling "back" onto it deploys something *newer* than what is failing.

Then show the platform's own commits:

```bash
git log --author="ASIE Promoter" --oneline
```

> "Those commits were written by the system, not by me."

---

## 7. Close (1 min)

```bash
./asie.sh pause     # or down
```

**The closing line:** *"The interesting part isn't that it deploys models. It's that it declines to."* Then point at the retraining run that rejected its own model, and the gate that held at `insufficient_data` because a 5-hour soak isn't 24.

---

## Questions you will get, and honest answers

**"Is the promotion gate real, or tuned for the demo?"**
Real, with one threshold compressed. Sample count (1000), failure rate (1%), latency ratio (1.25×) and disagreement (30%) are production values and were met on genuine traffic. The 24-hour soak was relaxed to 1 hour — a demo cannot wait a day, and that is stated rather than hidden.

**"What if the model is wrong but not broken?"**
The system cannot tell, and does not claim to. `true_label` is NULL in production, so there is no online ground truth. Offline `eval_f1` is the only "better" signal; online evidence only establishes "not broken". Closing that gap needs labelled feedback, which is the honest next feature.

**"Why not GPU?"**
p95 is 65–95 ms on CPU at this volume. GPU nodes would cost ~10× for latency nobody is waiting on. It was the planned next week and was deliberately dropped as the lowest-value remaining work.

**"What happens if ArgoCD dies?"**
Running workloads keep serving — ArgoCD reconciles desired state, it is not in the request path. What stops is deploying and self-healing.

**"Could this have shipped a bad model?"**
Yes, and it nearly did in eight distinct ways — all listed in `DEMO_REPORT.md` §6, every one found by running the system rather than reading it. The most instructive: model rollback was *impossible* for a while because S3 exports overwrote a fixed prefix, so a `git revert` would have appeared to succeed and changed nothing.
