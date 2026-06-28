FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app

COPY requirements-inference.txt .
COPY pyproject.toml .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements-inference.txt


COPY src/ ./src/
COPY exported_model/ ./exported_model

EXPOSE 8000

CMD ["uvicorn", "src.serving.app:app", "--host", "0.0.0.0", "--port", "8000"]