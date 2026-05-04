from src.pipelines.retraining_pipeline import retraining_pipeline
def main():
    configs = [
        # {
        #     "model_type": "transformer",
        #     "model_name": "bert-base-uncased",
        #     "lr": 2e-5,
        #     "epochs":2,
        #     "batch_size": 16,
        # },
        # {
        #     "model_type": "transformer",
        #     "model_name": "roberta-base",
        #     "lr": 2e-5,
        #     "epochs": 2,
        #     "batch_size": 16,
        # },
        # {
        #     "model_type": "transformer",
        #     "model_name": "distilbert-base-uncased",
        #     "lr": 2e-5,
        #     "epochs": 2,
        #     "batch_size": 16,
        # },
        # {
        #     "model_type": "transformer",
        #     "model_name": "albert-base-v2",
        #     "lr": 2e-5,
        #     "epochs": 2,
        #     "batch_size": 16,
        # }
        {
            "model_type": "transformer",
            "model_name": "bert-base-uncased",
            "lr": 2e-5,
            "epochs":3,
            "batch_size": 32,
        },
        {
            "model_type": "transformer",
            "model_name": "roberta-base",
            "lr": 2e-5,
            "epochs": 3,
            "batch_size": 32,
        },
        {
            "model_type": "transformer",
            "model_name": "distilbert-base-uncased",
            "lr": 2e-5,
            "epochs": 3,
            "batch_size": 32,
        },
        {
            "model_type": "transformer",
            "model_name": "albert-base-v2",
            "lr": 2e-5,
            "epochs": 3,
            "batch_size": 32,
        }
    ]

    retraining_pipeline(configs)

if __name__ == '__main__':
    main()