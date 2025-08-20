import io
import json
import os
import pytest

from flask_server import app, proposals, generate_payment_proposal_adapter


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EXCEL_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_financial_data.xlsx'))
CONFIG_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_request.json'))


def _load_excel_bytes():
    with open(EXCEL_PATH, 'rb') as f:
        return f.read()


def _load_config():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    # Ensure private_key exists for completeness; docs include it
    cfg.setdefault('private_key', 'test-key')
    return cfg


@pytest.fixture(autouse=True)
def clear_storage():
    proposals.clear()
    yield
    proposals.clear()


def test_submit_request_happy_path(monkeypatch, tmp_path):
    # Stub crew adapter to return deterministic proposal
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
        resp = client.post('/submit_request', data=data)
        assert resp.status_code in (200, 202)
        assert resp.content_type.startswith('application/json')
        body = resp.get_json()
        assert body.get('success') is True
        assert 'proposal_id' in body
        assert 'next_step' in body and '/get_payment_proposal/' in body['next_step']

        pid = body['proposal_id']
        # proposal persisted in memory
        assert pid in proposals
        stored = proposals[pid]
        assert isinstance(stored, dict)
        assert stored.get('proposal_id') == pid
        assert 'payments' in stored and isinstance(stored['payments'], list)


def test_submit_request_missing_excel(monkeypatch):
    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        lambda ctx: {},
        raising=True,
    )

    cfg = _load_config()
    data = {'json': json.dumps(cfg)}
    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_request_missing_json(monkeypatch):
    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        lambda ctx: {},
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    data = {
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_request_invalid_json(monkeypatch):
    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        lambda ctx: {},
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    data = {
        'json': '{not json}',
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_request_invalid_schema(monkeypatch):
    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        lambda ctx: {},
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    cfg = _load_config()
    # Remove required key to trigger schema error
    cfg.pop('risk_config', None)
    data = {
        'json': json.dumps(cfg),
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_request_crew_failure(monkeypatch):
    def boom(context):
        raise RuntimeError('Crew failure')

    monkeypatch.setattr('flask_server.generate_payment_proposal_adapter', boom, raising=True)

    excel_bytes = _load_excel_bytes()
    cfg = _load_config()
    data = {
        'json': json.dumps(cfg),
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    }
    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body
