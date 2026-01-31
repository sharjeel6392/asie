from fastapi.testclient import TestClient

from serving.app import app

def test_health():
    with TestClient(app) as client:
        r = client.get('/health')
        assert r.status_code == 200
        assert r.json()['status'] == 'ok'

def test_predict():
    with TestClient(app) as client:
        r = client.post('/predict', json = {'text': 'Markets look strong today'})
        assert r.status_code == 200
        
        data = r.json()
        assert 'label' in data
        assert 'score' in data
        assert 'latency_ms' in data