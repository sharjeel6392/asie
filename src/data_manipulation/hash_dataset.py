import hashlib
from pathlib import Path

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

if __name__ == '__main__':
    data_path = Path('data/financial_phrasebank.csv')
    print(hash_file(data_path))