# The Automated Sentiment Intelligence Engine (ASIE)
## 📌 Overview

ASIE (Automated Sentiment Intelligence Engine) is a production-oriented ML system for training, tracking, and eventually serving NLP sentiment models. Instead of a notebook-style experiment, ASIE is designed as a modular, reproducible, and testable pipeline with explicit lifecycle control, experiment tracking, and operational metadata capture.<br>
The goal is to treat ML as a software system, not just a training script.

## 🎯 Milestone-1 System Goals

- Modular pipeline design
- Reproducible training runs
- Configuration-driven execution
- Experiment tracking and artifact persistence
- System-level testing
- Extensibility toward serving and deployment


## 🏗 Architecture (Week-1: Training System)
Week-1 establishes the training and experimentation layer of ASIE.<br>
ASIE executes as a Python application:<br>

```bash
python -m pipeline
```
The training pipeline is organized into clear layers:<br>
```powershell
CLI → Orchestrator → Data → Preprocessing → Model → Evaluation → Artifacts → Tracking
```

---

### 🔁 Training Pipeline Flow
```mermaid
flowchart TD

    A[User / CLI] --> B[argparse Interface]
    B --> C[Pipeline Orchestrator]

    C --> D[Seed + Env Capture]
    D --> E[Dataset Load + Schema Validation]
    E --> F[Dataset Hashing]

    F --> G[Train / Val Split]
    G --> H[Tokenization + Encoding]

    H --> I[Model Initialization]
    I --> J[Trainer / Training Loop]

    J --> K[Evaluation Metrics]
    K --> L[Artifact Assembly]

    L --> M[MLflow Tracking Server]

    subgraph Data Layer
        E
        F
    end

    subgraph Preprocessing Layer
        G
        H
    end

    subgraph Model Layer
        I
        J
        K
    end

    subgraph Systems Layer
        D
        L
        M
    end
```

### 🧩 Component Responsibilities

#### CLI Interface
Controls runtime behavior via `argparse`. Configuration is injected at runtime, separating system logic from experiment parameters.

#### Pipeline Orchestrator
`pipeline.py` coordinates the lifecycle of a run: ingestion → preprocessing → training → evaluation → logging. It acts as ASIE’s control plane.

### Data Layer
- CSV ingestion
- Schema validation
- Dataset hashing
Guarantees input correctness and enables reproducibility across runs.

#### Preprocessing Layer
- Train/validation split
- Tokenization
- Dataset construction
Transforms raw text into model-ready representations.

#### Model Layer
- Model initialization
- Trainer configuration
- Training loop
- Metric computation
Encapsulates ML logic independent of orchestration and logging.

#### Systems Layer
- Seed control
- Environment capture
- Artifact assembly
- MLflow experiment tracking
Provides operational guarantees: reproducibility, traceability, and observability.

### 🧬 Reproducibility & Experiment Tracking
Each ASIE run logs:
- Dataset hash
- Runtime configuration
- Environment snapshot
- Git commit hash
- Metrics
- Auxiliary artifacts
MLflow is used as the experiment backend, enabling inspection, comparison, and lifecycle tracking of training runs.

### 🧪 Testing
ASIE includes a system-level smoke test using pytest that validates full pipeline execution via the CLI:
```python
python -m pytest -v
```
The test launches ASIE using:
```python
subprocess.run([sys.executable, "-m", "src.pipeline", "--epochs", "1"])
```
This validates packaging, imports, environment consistency, and runtime correctness.

## 🚀 Running ASIE
Run training:
```bash
python -m pipeline
```
Run tests:
```bash
python -m pytest -v
```

## 📦 Week 2 — Data Versioning & Dataset Identity

Week 2 focuses on treating data as a first-class system, independent of training code or experiment tracking.<br>

The central realization in this phase is:

<strong>Reproducibility starts before MLflow.</strong>

Instead of treating datasets as files, ASIE treats datasets as identified, versioned artifacts with explicit structure and lineage.

### 🔒 Canonical Data Rules

From Week 2 onward, the system enforces the following rules:
- CSV is ingestion-only
- Parquet is the canonical dataset format
- All training, evaluation, and inference use Parquet only
- Dataset identity is derived from content, not filenames
- Train/validation/test splits are part of the dataset itself
<p>Once data is converted to Parquet, CSV files are never referenced again.</p>

### 🔁 Data Flow
```text
Raw CSV (one-time ingestion)
        ↓
Schema Validation
        ↓
Canonical Parquet Dataset
        ↓
Versioned Parquet Splits (train / val / test)
```
<p> This flow ensures that downstream pipelines are insulated from raw data instability.</p>

### 🧬 Dataset Identity

Each dataset version is uniquely defined by:
- Parquet content hash
- Explicit schema
- Deterministic split logic
- Dataset manifest
<br>
This guarantees that:
- Any training run can be traced to a specific dataset version
- Data leakage is structurally prevented
- Dataset evolution is explicit and auditable
<p>Filenames and directory names are treated as implementation details, not identity.</p>

### 🧬 Dataset Lifecycle
```mermaid
flowchart LR
    A[Raw CSV] --> B[Schema Validation]
    B --> C[Canonical Parquet Dataset]

    C --> D[Dataset Hash Computation]
    D --> E[Dataset Manifest]

    C --> F[Deterministic Split Logic]
    F --> G[Train Parquet]
    F --> H[Validation Parquet]

    E --> G
    E --> H

    G --> J[Training Pipeline]
    H --> J

    J --> L[MLflow Run]
    L --> M[Logged Dataset Metadata]
```

### 🧾 Manifest as the Source of Truth

A dataset manifest records:
- Dataset version
- Parquet file paths
- Split definitions
- Hashes
<br>All downstream systems (training, evaluation, inference) reference the manifest rather than raw files.</p>
This ensures that:
- Changes to data are intentional
- Dataset evolution is observable
- Pipelines fail fast on mismatch

### 📦 Versioning Strategy

Parquet datasets are versioned using DVC, allowing:
- Lightweight tracking of large files
- Clear separation between code and data
- Reproducible dataset checkout by version
<p>
The repository never commits large data files directly.

### 🔗 Preparing for MLflow Integration

By enforcing dataset identity before experiment tracking, MLflow runs can later log:
- Dataset version
- Parquet hash
- Split paths
<br>
This eliminates ambiguity around:
- which CSV was used
- which preprocessing logic ran
- which split logic applied
<p>
MLflow becomes a consumer of data lineage, not its owner.

### 🧠 Key Learnings
- Datasets have identity
- Hash > filename
- Splits are part of the dataset, not training
- Reproducibility begins before model training
- Data systems must be stable before model systems
<p>
This phase establishes the foundation required for reliable model comparison, promotion, and deployment.


## 🚀 Week 3 — Inference & Serving Layer

Week 3 focuses on model consumption, not model creation.<p>
With dataset identity and reproducibility established in Week 2, the system shifts from offline correctness to online reliability. The goal of this phase is to expose trained models via a production-style inference service that is fast, observable, and safe to operate.

### 🎯 Objectives

The serving layer is designed to:
- Load models deterministically at startup
- Avoid cold-start latency
- Support single and batch inference
- Measure inference performance
- Log prediction metadata independently of training
- Remain decoupled from data preparation logic
<p>
Week 3 treats the model as an immutable artifact produced upstream.

### 🏗 Serving Architecture
```mermaid
flowchart LR
    A[Client] --> B[FastAPI API]
    B --> C[Request Validation]
    C --> D[Predictor]
    D --> E[Model Forward Pass]
    E --> F[Post-processing]
    F --> G[Response]

    D --> H[Inference Logger]
    H --> I[MLflow]
```
<p>
The serving layer is intentionally thin and modular. Each component has a single responsibility and can be reasoned about independently.

### 🔁 Application Lifecycle

Model loading is performed during application startup.
```text
Process start
   ↓
Resolve model artifact
   ↓
Download artifacts
   ↓
Load model into memory
   ↓
API becomes ready
```

This guarantees that:
- The model is loaded exactly once
- Requests never trigger model initialization
- Readiness checks reflect real availability

### 🧱 Core Components
#### ModelLoader
Responsible for model lifecycle management.<p>
Responsibilities
- Resolve MLflow artifact URIs
- Download model artifacts
- Load the model into memory
- Select execution device (CPU / CUDA)
<p> Model loading failures surface during startup rather than at inference time.

#### Predictor
Encapsulates all inference logic.<p>
Responsibilities
- Input normalization
- Tokenization
- Batch-aware inference
- Post-processing predictions
- Measuring inference latency
<p> The predictor is stateless, allowing safe reuse across requests.<br>
Batching is handled internally and does not change the API contract.

#### InferenceLogger
Provides observability for online predictions.<p>
Responsibilities
- Log inference metadata to MLflow
- Capture latency and confidence scores
- Preserve model lineage via run IDs
<p>Each inference is logged as a separate MLflow run, preventing parameter collisions and ensuring traceability.<br>
Logging failures do not affect prediction responses.

### 🔌 API Endpoints
<strong>Health Check</strong><br>
Used for readiness probes and operational monitoring.
```http
GET /health
```
**Response**
```json
{
  "status": "ok",
  "model_loader": true,
  "device": "cuda",
  "run_id": "7eb939db74994011841608b40992a2a1"
}
```
---
<strong>Single Prediction</strong>
```http
POST /predict
```
**Request**
```json
{
    "text": "Markets look strong today"
}
```
**Response**
```json
{
  "label": "positive",
  "score": 0.97,
  "latency_ms": 12.4,
  "model_version": "v0"
}
```
---
<strong>Batch Prediction</strong>
The same endpoint supports batch inference.
```http
POST /predict
```
**Request**
```json
{
	"text": [
		"Markets reacted positively to the earnings report",
        "The company reported heavy quarterly losses",
        "Revenue growth exceeded expectations"
	]
}
```
**Response**
```json
{
	"predictions":[
		{"label":"LABEL_2","score":0.9916867613792419},
		{"label":"LABEL_0","score":0.9920489192008972},
		{"label":"LABEL_2","score":0.9911454319953918}
	],
	"model_version":"v0",
	"latency_ms":755.9084892272949
}
```
Batching improves throughput and GPU utilization without changing client behavior.

### ⚡ Performance Considerations
#### Batching
- Requests are dynamically batched
- Tokenization and inference are vectorized
- A single forward pass serves multiple inputs
<p>This reduces per-sample overhead and improves GPU efficiency.</p>

#### Latency Measurement
Latency is measured inside the inference path and includes:
- Tokenization
- Model forward pass
- Post-processing
<br> It explicitly excludes:
- Network IO
- JSON serialization
- Logging overhead
<p> This ensures metrics reflect model performance, not transport noise.</p>

#### Concurrency Model
- FastAPI handles request IO asynchronously
- PyTorch inference runs synchronously
- Compute and IO are intentionally separated
<p> This avoids race conditions while preserving concurrency for inbound traffic. </p>

### 🔍 Observability & Monitoring
MLflow is used as a lightweight observability layer for inference.<br>
Each prediction logs:
- latency_ms
- score
- input length
- predicted label
- model run ID<br>
This enables:
- Latency analysis
- Confidence distribution inspection
- Model behavior auditing over time
<p> Inference logging is intentionally decoupled from training runs.</p>

## 📘 Week 4 - Promotion Architecture, SQLite MLflow & Shadow Deployment
Week 4 marked the transition from the experimentation setup to structured MLOps infrastructure.<br>
We formalized:
- Model promotion workflow
- SQLite-backed MLflow tracking
- Standalone Docker inference
- Structured SQLite inference logging
- Production-safe shadow model execution
This week represents the architectural shift from "local experimentation" to "deployable ML system".

### 🧩 Part 1 - The MLflow File-Based problem
#### Initial Setup
Originally, MLflow used the default file-based backend:
```powershell
mlruns/
```
Artifacts were logged correctly during training:
```powershell
mlruns/<experiment_id>/<run_id>/artifacts/
```
Local inference worked when training and serving shared the same filesystem.

#### 🚨 The Core Issue
When using:
```python
mlflow.set_tracking_uri("file:./mlruns")
```
MLflow internally resolved it to an absolute Window path:
```bash
artifact_uri: file:C:/Users/user/Documents/ASIE/mlruns/<exp>/<run>/artifacts
```
The absolute path became permanently embedded in run metadata.<br>
Inside Docker (Linux), that path does not exist. This caused:
- Run not found errors
- Artifact download failures
- Broken meta.yaml behavior
- Empty MLflow UI runs
- Inconsistent experiment state
<p>Even with proper Docker volume mounts, MLflow followed the absolute Windows path stored in metadata.<br>
Docker was not the problem, the file-based MLflow backend was.

#### 🧠 Architectural Realization
File-based MLflow tracking:
- Is not portable across OS boundaries
- Hardcodes absolute paths
- Couples experiment metadata to filesystem layout
- Is not concurrency-safe
- Does not scale cleanly
<p>For a system intended to evolve, this architecture was fragile.

### 🗄 Part 2 – Moving MLflow to SQLite Backend
I migrated MLflow metadata storage to:
```python
sqlite:///mlflow.db
```
Important distinction:
| Component | Purpose |
| --------- | ------- |
| Backend Store | Experiments, runs, metrics, params |
| Artifact Store | Model weights, tokenizer files |

With SQLite:
- Metadata stored transactionally
- ACID guarantees
- Structured relational schema
- Portable across Windows & Docker
- Clear upgrade path to Postgres
<p> Artifacts remain local. MLflow is now treated as an infrastructure, not just a folder.

### 🏗 Part 3 - Model Promotion Architecture
Key architectural decision:<br>
Inference must NOT dynamically load artifacts from MLflow at runtime, as the runtime MLflow loading introduces dependencies on:
- Tracking server
- Database
- Artifact store
- Network availability
- Mutable experiment metadata
<p> This breaks portability.</p>

#### Promotion Concept
Training produces experimental runs. Serving requires immutable release artifacts. Hence, promotion converts:
```nginx
ExperimentRun → ApprovedReleaseArtifact
```
Promotion freezes:
- Exact weights
- Exact tokenizer
- Exact configuration

Equivalent to tagging a Git release.

#### Final Promotion Flow
##### Training Phase
```scss
train.py
   ↓
MLflow (SQLite backend)
   ↓
Artifacts logged locally
```
##### Promotion Phase
```sql
Select best run
   ↓
export_model.py
   ↓
Copy artifacts into exported_model/
```
##### Serving Phase (Docker)
Docker image contains:
```bash
/app/exported_model/model/
/app/exported_model/tokenizer/
```
No MLflow imports, no tracking URI, no runtime artifact downloads. The container is
- Immutable
- Deterministic
- Portable
- Infrastructure-independent

### 🗂 Part 4 - Structured SQLite Inference Logging
I replaced MLflow-based inference logging with a dedicated SQLite logging system.

Architecture:
```scss
FastAPI Endpoint
        ↓
Predictor (pure inference)
        ↓
Repository Layer
        ↓
SQLite (inference.db)
```
Separation of concerns:
- `predictor.py` → model inference only
- `repository.py` → DB insert logic
- `database.py` → connection + schema init
- `schema.sql` → table definition
- `app.py` → Orchestration

#### Database Schema - `inference_logs`
Each batch prediction logs one row per sample. Key fields are:
- request_id
- timestamp
- input_data
- primary_model_name
- primary_model_version
- primary_predictions
- primary_latency_ms
- shadow_model_name
- shadow_model_version
- shadow_predictions
- shadow_latency_ms
- disagreement
- abs_diff
- request_source

The schema is shadow-ready by design.

#### Batch-Safe Endpoint
Even single inputs are treated as batch size 1:
```python
{'text': ['market look strong today']}
```
Each item:
- Gets its own request_id
- Logs per-sample latency
- Generates independent DB row

This ensures shadow comparability.

#### Debugging Milestones
##### 1. Schema mismatch issue
Cause:
- Existing SQLite DB had outdated schema
- `CREATE TABLE IF NOT EXISTS` does not modify columns

Fix:
- Delete `inference.db`
- Reinitialize schema

##### 2. Batch iteration bug
Issue:
- A strong was iterated character-by-character
- Only first letter of the predicted text was logged

Root cause:
- Endpoint expected list (even a singular text) but recieved string

Fix:
- Enfored list-based request schema

#### 🧪 Docker Compatibility
We ensured:
- `inference.db` is NOT baked into image
- DB created at runtime
- Optional volume mount for persistence:
```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data image_name
```
Logs persist across container restarts.

SQLite inspection:
```bash
sqlite data/inference.db
.tables
PRAGMA table_info(inference_logs);
SELECT * FROM inference_logs;
```

### 🌘 Part 5 - Shadow Model Execution
I implemented a production-grade shadow deployment.

Architecture:
```java
Client → FastAPI → Primary Model (serves response)
                    ↘ Shadow Model (silent execution)
                          ↓
                    SQLite Inference DB
```

#### Dual Model Setup
Two exported DistilBERT variants:
- Primary (v_01) and
- Secondary (v_02)

Loaded once at startup. Here, Primary = required; Shadow = optional

#### Safe Shadow Loading
Shadow loading wrapped in try/except. If shadow directory missing:
- Warning logged
- shadow_model = None
- API continues normally and runs prediction on Primary

Health endpoint:
```json
{
    'primary_ready': True,
    'shadow_ready': False,
    'device': 'cpu'
}
```
#### Safe Shadow Execution
During prediction:
- Shadow executed only if available
- Wrapped in try/catch
- Shadow failures never break request
- DB fields become NULL when shadow absent

Validation performed:
- ✔ Delete shadow directory → API still works
- ✔ Shadow crash → logged, not raised
- ✔ Latency measurable
- ✔ Primary always protected

#### Disagreement and Drift Metrics
Per sample, I logged:
- disagreement (label mismatch)
- abs_diff (score difference)
- shadow_latency_ms
- primary_latency_ms

This enables:
- promotion readiness evaluation
- Drift groundwork
- Offline shadow analysis

### 🧠 Production Properties Achieved
By the end of week 4, I achieved:
- SQLite-backed MLflow tracking
- Explicit model promotion step
- Standalone Docker inference
- Structured inference logging
- Safe shadow deployment
- Failure isolation
- Latency observability
- Promotion architecture foundation

This mirrors the real-world MLOps systems used in:
- Shadow testing
- Canary releases
- Gradual rollouts
- Governance-driven model promotion

### 🏁 Week 4 Status: Complete
The system now cleanly separates:
- Experimentation
- Metadata tracking
- Artifact promotion
- Serving infrastructure
- Production logging
- Shadow experimentation
