from src.experiments.runner import run_experiments
from src.experiments.selector import select_best_model
from src.experiments.schemas import ExperimentResult
from typing import List

def main():
    configs = [
        {
            "model_type": "transformer",
            "model_name": "bert-base-uncased",
            "lr": 2e-5,
            "epochs":2,
            "batch_size": 16,
        },
        {
            "model_type": "transformer",
            "model_name": "roberta-base",
            "lr": 2e-5,
            "epochs": 2,
            "batch_size": 16,
        },
        {
            "model_type": "transformer",
            "model_name": "distilbert-base-uncased",
            "lr": 2e-5,
            "epochs": 2,
            "batch_size": 16,
        },
        {
            "model_type": "transformer",
            "model_name": "albert-base-v2",
            "lr": 2e-5,
            "epochs": 2,
            "batch_size": 16,
        }
    ]

    results: List[ExperimentResult] = run_experiments(configs)

    print("\n============ Experiment Results ============\n")
    for r in results:
        print(r)

    best: ExperimentResult | None = select_best_model(results)

    print("\n============ Best Model ==============\n")
    print(best)

if __name__ == "__main__":
    main()
