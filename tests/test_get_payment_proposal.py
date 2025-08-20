import io
import json
import os
import pytest

from flask_server import app, proposals


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EXCEL_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_financial_data.xlsx'))
CONFIG_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_request.json'))


def _load_excel_bytes():
    with open(EXCEL_PATH, 'rb') as f:
        return f.read()


def _load_config():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    cfg.setdefault('private_key', 'test-key')
    return cfg


@pytest.fixture(autouse=True)
def clear_storage():
    proposals.clear()
    yield
    proposals.clear()


def test_get_payment_proposal_not_found():
    unknown_id = 'does-not-exist'
    with app.test_client() as client:
        resp = client.get(f'/get_payment_proposal/{unknown_id}')
        assert resp.status_code == 404
        assert resp.content_type.startswith('application/json')
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_get_payment_proposal_internal_error(monkeypatch):
    class BadDict:
        def __contains__(self, key):
            raise RuntimeError('boom contains')
        def __getitem__(self, key):
            raise RuntimeError('boom getitem')

    # Replace proposals in the flask_server module with a failing dict
    monkeypatch.setattr('flask_server.proposals', BadDict(), raising=True)

    with app.test_client() as client:
        resp = client.get('/get_payment_proposal/any')
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_get_payment_proposal_happy_path(monkeypatch):
    # Stub crew adapter to return deterministic proposal using generated proposal_id
    def fake_generate(context):
        pid = context.get('proposal_id') or 'pid-test'
        return {
            "proposal_id": pid,
            "report": "Risk analysis OK. Generated payments.",
            "payments": [
                {
                    "payment_id": "pay-1",
                    "recipient_wallet": "0x123",
                    "amount": 100.0,
                    "reference": "INV-001"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    cfg = _load_config()

    data = {
        'json': json.dumps(cfg),
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    }

    with app.test_client() as client:
        post_resp = client.post('/submit_request', data=data)
        assert post_resp.status_code in (200, 202)
        post_body = post_resp.get_json()
        pid = post_body['proposal_id']

        # Now fetch the stored proposal
        get_resp = client.get(f'/get_payment_proposal/{pid}')
        assert get_resp.status_code == 200
        assert get_resp.content_type.startswith('application/json')
        body = get_resp.get_json()

        # Should match stored in-memory object
        assert pid in proposals
        expected = proposals[pid]
        assert body == expected
        assert 'proposal_id' in body and 'report' in body and 'payments' in body
