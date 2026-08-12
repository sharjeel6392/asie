FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

COPY requirements/requirements_serving.txt .
COPY pyproject.toml .

RUN pip install --upgrade pip

# torch is CPU-only here (the app hardcodes INFERENCE_DEVICE=cpu) — installed
# separately, in its own layer, from its own index so this doesn't drag the
# default PyPI wheel's bundled CUDA/nvidia-* deps into the resolution below
# (and doesn't leak that index into it either — keep this as its own RUN,
# not chained with `&&` into the next install).
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.6.0

RUN pip install --no-cache-dir -r requirements_serving.txt

COPY src/ ./src/
# Model is no longer baked into the image — fetched from S3 by an
# initContainer at pod startup (see helm/asie-inference).

EXPOSE 8000

CMD ["uvicorn", "src.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]