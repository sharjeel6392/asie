def test_health_endpoint(client):
    r = client.get('/health')
    assert r.status_code == 200

    data = r.json()
    assert data['status'] == 'ok'
    assert data['model_loader'] is True
    assert data['run_id'] is not None

def test_startup_model_loaded(client):
    r = client.get('/health')
    data = r.json()
    assert data['model_loader'] is True