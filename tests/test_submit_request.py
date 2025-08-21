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


def test_submit_request_new_api_spec_without_custody_wallet(monkeypatch):
    """Test that submit_request works with NEW API spec (no custody_wallet/private_key required)."""
    def fake_generate(context):
        pid = context.get('proposal_id') or 'pid-test-new-api'
        return {
            "proposal_id": pid,
            "report": "Risk analysis OK. Generated payments with new API spec.",
            "payments": [
                {
                    "payment_id": "pay-new-1",
                    "recipient_wallet": "0x456",
                    "amount": 200.0,
                    "reference": "INV-002"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    # Create config per NEW API documentation (no custody_wallet, no private_key)
    new_api_config = {
        "user_id": "test_user_new_api",
        "risk_config": {
            "min_balance_usd": 1500.0,
            "transaction_limits": {
                "single": 20000.0,
                "daily": 40000.0
            }
        },
        "user_notes": "Testing new API specification without custody credentials"
    }

    data = {
        'json': json.dumps(new_api_config),
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


def test_submit_request_optional_user_notes(monkeypatch):
    """Test that user_notes is optional in the new API spec."""
    def fake_generate(context):
        pid = context.get('proposal_id') or 'pid-test-no-notes'
        return {
            "proposal_id": pid,
            "report": "Risk analysis OK. No user notes provided.",
            "payments": [
                {
                    "payment_id": "pay-no-notes-1",
                    "recipient_wallet": "0x789",
                    "amount": 300.0,
                    "reference": "INV-003"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    # Config without user_notes
    minimal_config = {
        "user_id": "test_user_minimal",
        "risk_config": {
            "min_balance_usd": 1000.0,
            "transaction_limits": {
                "single": 15000.0,
                "daily": 30000.0
            }
        }
        # No user_notes field
    }

    data = {
        'json': json.dumps(minimal_config),
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    }

    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code in (200, 202)
        body = resp.get_json()
        assert body.get('success') is True
        assert 'proposal_id' in body


def test_submit_request_backward_compatibility_with_extra_fields(monkeypatch):
    """Test that endpoint accepts extra fields (like old custody_wallet) but doesn't require them."""
    def fake_generate(context):
        pid = context.get('proposal_id') or 'pid-test-backward-compat'
        # Verify context still contains the old fields if provided
        cfg = context.get('config', {})
        assert 'custody_wallet' in cfg  # Should be present in context even if not required
        return {
            "proposal_id": pid,
            "report": "Risk analysis OK. Backward compatibility confirmed.",
            "payments": [
                {
                    "payment_id": "pay-compat-1",
                    "recipient_wallet": "0xabc",
                    "amount": 400.0,
                    "reference": "INV-004"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    excel_bytes = _load_excel_bytes()
    # Use old config format (should still work)
    old_format_config = _load_config()  # This includes custody_wallet

    data = {
        'json': json.dumps(old_format_config),
        'excel': (io.BytesIO(excel_bytes), os.path.basename(EXCEL_PATH), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    }

    with app.test_client() as client:
        resp = client.post('/submit_request', data=data)
        assert resp.status_code in (200, 202)
        body = resp.get_json()
        assert body.get('success') is True
        assert 'proposal_id' in body
