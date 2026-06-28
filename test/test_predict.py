def test_predict_single_text(client):
    payload = {
        'text': 'Markets reacted positively to the earnings report'
    }
    r = client.post('/predict', json=payload)
    assert r.status_code == 200

    data = r.json()
    assert 'prediction' in data
    assert len(data['prediction']) == 1

    pred = data['predictions'][0]
    assert 'label' in pred
    assert 'score' in pred
    assert 0.0 <= pred['score'] <= 1.0


def test_predict_batch(client):
    payload = {
        "text": [
            "Markets are optimistic today",
            "The company posted record losses"
        ]
    }
    r = client.post('/predict', json=payload)
    assert r.status_code == 200

    data = r.json()
    assert (len(data['predictions'])) == 2
    
    for pred in data['predictions']:
        assert 0.0 <= pred['score'] <= 1.0

def test_predict_invalid_input(client):
    payload = {'text': 123}

    r = client.post('/predict', json=payload)
    assert r.status_code == 422 # Pydantic Validation