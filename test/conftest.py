import pytest
from fastapi.testclient import TestClient
from serving.app import app

@pytest.fixture(scope='session')
def client():
    return TestClient(app)