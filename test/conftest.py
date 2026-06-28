import pytest
from fastapi.testclient import TestClient
from src.serving.app import app

@pytest.fixture(scope='session')
def client():
    return TestClient(app)