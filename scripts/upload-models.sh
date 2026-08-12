#!/bin/bash
# One-time (and re-runnable) upload of the currently-exported model to S3,
# so a fresh EKS deploy has something to fetch. Excludes training_args.bin
# — from_pretrained() never reads it, pure dead weight in S3.
set -e

BUCKET="asie-platform-818111885210"

aws s3 sync exported_model/ "s3://${BUCKET}/models/" --exclude "*/training_args.bin"

if [ -f "model/model_registry.yaml" ]; then
  aws s3 cp model/model_registry.yaml "s3://${BUCKET}/models/model_registry.yaml"
else
  echo "model/model_registry.yaml not found locally — skipping (will be created on first S3-aware registry write)."
fi

echo "Uploaded exported_model/ -> s3://${BUCKET}/models/"
