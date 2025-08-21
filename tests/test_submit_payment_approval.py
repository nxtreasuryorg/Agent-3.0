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


def test_submit_payment_approval_missing_json():
    """Test missing JSON body returns 400."""
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval')
        assert resp.status_code == 400
        assert resp.content_type.startswith('application/json')
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_invalid_json():
    """Test invalid JSON syntax returns 400."""
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval', 
                          data='{"invalid": json syntax}',
                          content_type='application/json')
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_missing_required_fields():
    """Test missing required fields returns 400."""
    incomplete_data = {
        "proposal_id": "test-id"
        # Missing custody_wallet, private_key, approval_decision
    }
    
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval',
                          json=incomplete_data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_invalid_approval_decision():
    """Test invalid approval_decision returns 400."""
    invalid_data = {
        "proposal_id": "test-id",
        "custody_wallet": "0x123",
        "private_key": "test-key",
        "approval_decision": "invalid_decision",  # Not in: approve_all, reject_all, partial
        "comments": "test"
    }
    
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval',
                          json=invalid_data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_partial_missing_approved_payments():
    """Test partial approval without approved_payments array returns 400."""
    partial_data = {
        "proposal_id": "test-id",
        "custody_wallet": "0x123",
        "private_key": "test-key",
        "approval_decision": "partial",
        "comments": "test"
        # Missing approved_payments for partial approval
    }
    
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval',
                          json=partial_data)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_proposal_not_found():
    """Test unknown proposal_id returns 404."""
    approval_data = {
        "proposal_id": "non-existent-id",
        "custody_wallet": "0x123",
        "private_key": "test-key",
        "approval_decision": "approve_all",
        "comments": "test"
    }
    
    with app.test_client() as client:
        resp = client.post('/submit_payment_approval',
                          json=approval_data)
        assert resp.status_code == 404
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_crew_failure(monkeypatch):
    """Test crew execution failure returns 500."""
    # First create a proposal
    def fake_generate(context):
        return {
            "proposal_id": "test-proposal-crew-fail",
            "report": "Test proposal for crew failure",
            "payments": [
                {
                    "payment_id": "pay-1",
                    "recipient_wallet": "0x456",
                    "amount": 100.0,
                    "reference": "TEST-001"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    # Create proposal first
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

        # Mock payment execution to fail
        def failing_payment_executor(context):
            raise RuntimeError("Payment execution failed")

        monkeypatch.setattr(
            'flask_server.execute_payment_approval_adapter',
            failing_payment_executor,
            raising=True,
        )

        # Now test approval with crew failure
        approval_data = {
            "proposal_id": pid,
            "custody_wallet": "0x123",
            "private_key": "test-key",
            "approval_decision": "approve_all",
            "comments": "test approval"
        }

        resp = client.post('/submit_payment_approval',
                          json=approval_data)
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_submit_payment_approval_approve_all_success(monkeypatch):
    """Test successful approve_all scenario."""
    # First create a proposal
    def fake_generate(context):
        return {
            "proposal_id": "test-proposal-approve-all",
            "report": "Test proposal for approve all",
            "payments": [
                {
                    "payment_id": "pay-1",
                    "recipient_wallet": "0x456",
                    "amount": 100.0,
                    "reference": "TEST-001"
                },
                {
                    "payment_id": "pay-2",
                    "recipient_wallet": "0x789",
                    "amount": 200.0,
                    "reference": "TEST-002"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    # Create proposal first
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

        # Mock successful payment execution
        def successful_payment_executor(context):
            return {
                "execution_status": "SUCCESS",
                "message": "All payments executed successfully",
                "executed_payments": ["pay-1", "pay-2"],
                "failed_payments": []
            }

        monkeypatch.setattr(
            'flask_server.execute_payment_approval_adapter',
            successful_payment_executor,
            raising=True,
        )

        # Test approve_all
        approval_data = {
            "proposal_id": pid,
            "custody_wallet": "0x123",
            "private_key": "test-key",
            "approval_decision": "approve_all",
            "comments": "Approve all payments"
        }

        resp = client.post('/submit_payment_approval',
                          json=approval_data)
        assert resp.status_code == 200
        assert resp.content_type.startswith('application/json')
        body = resp.get_json()
        
        # Verify response matches API doc
        assert body.get('success') is True
        assert body.get('execution_status') == "SUCCESS"
        assert 'message' in body
        assert body.get('next_step') == f"GET /payment_execution_result/{pid}"


def test_submit_payment_approval_reject_all_success(monkeypatch):
    """Test successful reject_all scenario."""
    # First create a proposal
    def fake_generate(context):
        return {
            "proposal_id": "test-proposal-reject-all",
            "report": "Test proposal for reject all",
            "payments": [
                {
                    "payment_id": "pay-1",
                    "recipient_wallet": "0x456",
                    "amount": 100.0,
                    "reference": "TEST-001"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    # Create proposal first
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

        # Mock rejection (no payments executed)
        def rejection_executor(context):
            return {
                "execution_status": "SUCCESS",
                "message": "All payments rejected as requested",
                "executed_payments": [],
                "failed_payments": []
            }

        monkeypatch.setattr(
            'flask_server.execute_payment_approval_adapter',
            rejection_executor,
            raising=True,
        )

        # Test reject_all
        approval_data = {
            "proposal_id": pid,
            "custody_wallet": "0x123",
            "private_key": "test-key",
            "approval_decision": "reject_all",
            "comments": "Reject all payments"
        }

        resp = client.post('/submit_payment_approval',
                          json=approval_data)
        assert resp.status_code == 200
        body = resp.get_json()
        
        # Verify response matches API doc
        assert body.get('success') is True
        assert body.get('execution_status') == "SUCCESS"
        assert 'message' in body
        assert body.get('next_step') == f"GET /payment_execution_result/{pid}"


def test_submit_payment_approval_partial_success(monkeypatch):
    """Test successful partial approval scenario."""
    # First create a proposal
    def fake_generate(context):
        return {
            "proposal_id": "test-proposal-partial",
            "report": "Test proposal for partial approval",
            "payments": [
                {
                    "payment_id": "pay-1",
                    "recipient_wallet": "0x456",
                    "amount": 100.0,
                    "reference": "TEST-001"
                },
                {
                    "payment_id": "pay-2",
                    "recipient_wallet": "0x789",
                    "amount": 200.0,
                    "reference": "TEST-002"
                },
                {
                    "payment_id": "pay-3",
                    "recipient_wallet": "0xabc",
                    "amount": 300.0,
                    "reference": "TEST-003"
                }
            ]
        }

    monkeypatch.setattr(
        'flask_server.generate_payment_proposal_adapter',
        fake_generate,
        raising=True,
    )

    # Create proposal first
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

        # Mock partial execution
        def partial_executor(context):
            approved_payments = context.get('approved_payments', [])
            return {
                "execution_status": "PARTIAL_SUCCESS",
                "message": f"Executed {len(approved_payments)} of 3 payments",
                "executed_payments": approved_payments,
                "failed_payments": []
            }

        monkeypatch.setattr(
            'flask_server.execute_payment_approval_adapter',
            partial_executor,
            raising=True,
        )

        # Test partial approval
        approval_data = {
            "proposal_id": pid,
            "custody_wallet": "0x123",
            "private_key": "test-key",
            "approval_decision": "partial",
            "approved_payments": ["pay-1", "pay-3"],  # Only approve 2 of 3
            "comments": "Partial approval - only pay-1 and pay-3"
        }

        resp = client.post('/submit_payment_approval',
                          json=approval_data)
        assert resp.status_code == 200
        body = resp.get_json()
        
        # Verify response matches API doc
        assert body.get('success') is True
        assert body.get('execution_status') == "PARTIAL_SUCCESS"
        assert 'message' in body
        assert body.get('next_step') == f"GET /payment_execution_result/{pid}"
