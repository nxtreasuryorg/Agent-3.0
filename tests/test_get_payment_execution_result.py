import io
import json
import os
import pytest

from flask_server import app, proposals


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
EXCEL_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_financial_data.xlsx'))
CONFIG_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, '..', 'Agent', 'test_data', 'dummy_request.json'))


@pytest.fixture(autouse=True)
def clear_storage():
    proposals.clear()
    yield
    proposals.clear()


def test_get_payment_execution_result_proposal_not_found():
    """Test unknown proposal_id returns 404."""
    unknown_id = 'does-not-exist'
    with app.test_client() as client:
        resp = client.get(f'/payment_execution_result/{unknown_id}')
        assert resp.status_code == 404
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_get_payment_execution_result_no_execution_yet():
    """Test proposal exists but no execution result yet returns 404."""
    # Create a proposal without execution result
    proposal_id = 'test-proposal-no-execution'
    proposals[proposal_id] = {
        'proposal_id': proposal_id,
        'report': 'Test proposal without execution',
        'payments': [
            {
                'payment_id': 'pay-1',
                'recipient_wallet': '0x456',
                'amount': 100.0,
                'reference': 'TEST-001'
            }
        ]
        # Note: no 'execution_result' key
    }
    
    with app.test_client() as client:
        resp = client.get(f'/payment_execution_result/{proposal_id}')
        assert resp.status_code == 404
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body


def test_get_payment_execution_result_success():
    """Test successful retrieval of execution result."""
    proposal_id = 'test-proposal-executed'
    execution_result = {
        'proposal_id': proposal_id,
        'execution_status': 'SUCCESS',
        'executed_payments': [
            {
                'payment_id': 'pay-1',
                'recipient_wallet': '0x456',
                'amount': 100.0,
                'reference': 'TEST-001',
                'transaction_hash': '0xabc123',
                'status': 'SUCCESS'
            }
        ],
        'failed_payments': [],
        'message': 'All payments executed successfully',
        'execution_timestamp': '2025-08-21T08:00:00Z'
    }
    
    # Create proposal with execution result
    proposals[proposal_id] = {
        'proposal_id': proposal_id,
        'report': 'Test proposal with execution',
        'payments': [
            {
                'payment_id': 'pay-1',
                'recipient_wallet': '0x456',
                'amount': 100.0,
                'reference': 'TEST-001'
            }
        ],
        'execution_result': execution_result
    }
    
    with app.test_client() as client:
        resp = client.get(f'/payment_execution_result/{proposal_id}')
        assert resp.status_code == 200
        body = resp.get_json()
        
        # Verify response structure matches API documentation
        assert body['proposal_id'] == proposal_id
        assert body['execution_status'] == 'SUCCESS'
        assert len(body['executed_payments']) == 1
        assert len(body['failed_payments']) == 0
        assert body['executed_payments'][0]['payment_id'] == 'pay-1'
        assert body['executed_payments'][0]['transaction_hash'] == '0xabc123'


def test_get_payment_execution_result_partial_success():
    """Test execution result with both successful and failed payments."""
    proposal_id = 'test-proposal-partial'
    execution_result = {
        'proposal_id': proposal_id,
        'execution_status': 'PARTIAL_SUCCESS',
        'executed_payments': [
            {
                'payment_id': 'pay-1',
                'recipient_wallet': '0x456',
                'amount': 100.0,
                'reference': 'TEST-001',
                'transaction_hash': '0xabc123',
                'status': 'SUCCESS'
            }
        ],
        'failed_payments': [
            {
                'payment_id': 'pay-2',
                'recipient_wallet': '0x789',
                'amount': 200.0,
                'reference': 'TEST-002',
                'status': 'FAILED',
                'error': 'Insufficient balance'
            }
        ],
        'message': 'Partial execution: 1 success, 1 failure',
        'execution_timestamp': '2025-08-21T08:00:00Z'
    }
    
    proposals[proposal_id] = {
        'proposal_id': proposal_id,
        'report': 'Test proposal with partial execution',
        'payments': [
            {'payment_id': 'pay-1', 'recipient_wallet': '0x456', 'amount': 100.0, 'reference': 'TEST-001'},
            {'payment_id': 'pay-2', 'recipient_wallet': '0x789', 'amount': 200.0, 'reference': 'TEST-002'}
        ],
        'execution_result': execution_result
    }
    
    with app.test_client() as client:
        resp = client.get(f'/payment_execution_result/{proposal_id}')
        assert resp.status_code == 200
        body = resp.get_json()
        
        assert body['proposal_id'] == proposal_id
        assert body['execution_status'] == 'PARTIAL_SUCCESS'
        assert len(body['executed_payments']) == 1
        assert len(body['failed_payments']) == 1
        assert body['executed_payments'][0]['status'] == 'SUCCESS'
        assert body['failed_payments'][0]['status'] == 'FAILED'
        assert 'error' in body['failed_payments'][0]


def test_get_payment_execution_result_failure():
    """Test execution result with all payments failed."""
    proposal_id = 'test-proposal-failed'
    execution_result = {
        'proposal_id': proposal_id,
        'execution_status': 'FAILURE',
        'executed_payments': [],
        'failed_payments': [
            {
                'payment_id': 'pay-1',
                'recipient_wallet': '0x456',
                'amount': 100.0,
                'reference': 'TEST-001',
                'status': 'FAILED',
                'error': 'Network timeout'
            }
        ],
        'message': 'All payments failed',
        'execution_timestamp': '2025-08-21T08:00:00Z'
    }
    
    proposals[proposal_id] = {
        'proposal_id': proposal_id,
        'report': 'Test proposal with failed execution',
        'payments': [
            {'payment_id': 'pay-1', 'recipient_wallet': '0x456', 'amount': 100.0, 'reference': 'TEST-001'}
        ],
        'execution_result': execution_result
    }
    
    with app.test_client() as client:
        resp = client.get(f'/payment_execution_result/{proposal_id}')
        assert resp.status_code == 200
        body = resp.get_json()
        
        assert body['proposal_id'] == proposal_id
        assert body['execution_status'] == 'FAILURE'
        assert len(body['executed_payments']) == 0
        assert len(body['failed_payments']) == 1
        assert body['failed_payments'][0]['error'] == 'Network timeout'


def test_get_payment_execution_result_internal_error(monkeypatch):
    """Test internal server error during result retrieval."""
    class BadDict:
        def __contains__(self, key):
            raise RuntimeError('boom contains')
        def __getitem__(self, key):
            raise RuntimeError('boom getitem')

    # Replace proposals with a failing dict
    monkeypatch.setattr('flask_server.proposals', BadDict(), raising=True)

    with app.test_client() as client:
        resp = client.get('/payment_execution_result/any')
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False
        assert 'error' in body
