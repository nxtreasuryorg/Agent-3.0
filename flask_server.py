from flask import Flask, request, jsonify
import os
import json
import uuid
from typing import Any, Dict
from dotenv import load_dotenv, find_dotenv

app = Flask(__name__)

# Prefer local .env for development; fall back to process env (e.g., Render)
_env_path = find_dotenv()
if _env_path:
    load_dotenv(_env_path, override=True)

# In-memory storage for proposals (for demonstration purposes)
proposals = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

def _error(message: str, code: int):
    return jsonify({"error": message, "success": False}), code

def _validate_config(cfg: Dict[str, Any]) -> None:
    """Raises ValueError if config is invalid per api_documentation.md."""
    required_top = ["user_id", "risk_config"]
    for k in required_top:
        if k not in cfg:
            raise ValueError(f"Missing required field: {k}")
    risk = cfg.get("risk_config")
    if not isinstance(risk, dict):
        raise ValueError("risk_config must be an object")
    if "min_balance_usd" not in risk:
        raise ValueError("risk_config.min_balance_usd is required")
    tx = risk.get("transaction_limits")
    if not isinstance(tx, dict):
        raise ValueError("risk_config.transaction_limits is required")
    for k in ("single", "daily"):
        if k not in tx:
            raise ValueError(f"risk_config.transaction_limits.{k} is required")
    # user_notes is optional per API documentation

def _validate_payment_approval(data: Dict[str, Any]) -> None:
    """Raises ValueError if payment approval data is invalid per api_documentation.md."""
    required_fields = ["proposal_id", "custody_wallet", "private_key", "approval_decision"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    approval_decision = data.get("approval_decision")
    valid_decisions = ["approve_all", "reject_all", "partial"]
    if approval_decision not in valid_decisions:
        raise ValueError(f"Invalid approval_decision. Must be one of: {', '.join(valid_decisions)}")
    
    # For partial approval, approved_payments is required
    if approval_decision == "partial":
        if "approved_payments" not in data:
            raise ValueError("approved_payments is required for partial approval")
        if not isinstance(data["approved_payments"], list):
            raise ValueError("approved_payments must be an array")
    
    # comments is optional per API documentation

def _make_output_dir() -> str:
    root = os.path.abspath(os.path.dirname(__file__))
    # Allow override via environment for deploys; default to project-local 'tmp'
    configured = os.environ.get('AGENT_STORAGE_DIR')
    out = os.path.abspath(configured) if configured else os.path.join(root, 'tmp')
    os.makedirs(out, exist_ok=True)
    return out

def _cleanup_proposal_artifacts(proposal_id: str) -> None:
    """Best-effort cleanup of on-disk artifacts for a proposal.
    Does not touch in-memory 'proposals'. Swallows all IO errors.
    """
    try:
        out_dir = _make_output_dir()
        candidates = [
            os.path.join(out_dir, f"temp_excel_{proposal_id}.xlsx"),
            os.path.join(out_dir, f"proposal_{proposal_id}.json"),
            os.path.join(out_dir, f"execution_result_{proposal_id}.json"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        # Also remove any other files that include the proposal_id substring
        try:
            for name in os.listdir(out_dir):
                if proposal_id in name:
                    p = os.path.join(out_dir, name)
                    if os.path.isfile(p):
                        try:
                            os.remove(p)
                        except Exception:
                            pass
        except Exception:
            pass
        # Optional: if the directory is empty, leave it as-is to avoid race conditions
    except Exception:
        pass

def id_provider() -> str:
    """DI-friendly proposal id provider."""
    return str(uuid.uuid4())

def generate_payment_proposal_adapter(context: Dict[str, Any]):
    """DI-friendly adapter to call the crew. Tests monkeypatch this symbol.
    Import crew lazily to avoid side effects at import-time.
    """
    from crew import TreasuryCrew
    crew = TreasuryCrew()
    return crew.generate_payment_proposal(context)

def execute_payment_approval_adapter(context: Dict[str, Any]):
    """DI-friendly adapter to execute payment approvals. Tests monkeypatch this symbol.
    Import crew lazily to avoid side effects at import-time.
    """
    from crew import TreasuryCrew
    crew = TreasuryCrew()
    return crew.execute_payments(context)

@app.route('/submit_request', methods=['POST'])
def submit_request():
    """Accepts an Excel file and JSON configuration to generate a payment proposal."""
    if 'excel' not in request.files:
        return _error("Missing 'excel' file part", 400)
    if 'json' not in request.form:
        return _error("Missing 'json' config part", 400)

    excel_file = request.files['excel']
    try:
        raw_json = request.form['json']
        cfg = json.loads(raw_json)
    except Exception:
        return _error("Invalid JSON in 'json' part", 400)

    # Basic schema validation per docs
    try:
        _validate_config(cfg)
    except ValueError as ve:
        return _error(str(ve), 400)

    # Read Excel bytes
    try:
        excel_bytes = excel_file.read()
        if not excel_bytes:
            return _error("Uploaded 'excel' file is empty", 400)
    except Exception:
        return _error("Failed to read 'excel' file", 400)

    pid = id_provider()

    # Save Excel bytes to temporary file for crew processing
    out_dir = _make_output_dir()
    temp_excel_path = os.path.join(out_dir, f"temp_excel_{pid}.xlsx")
    try:
        with open(temp_excel_path, 'wb') as f:
            f.write(excel_bytes)
    except Exception as e:
        return _error(f"Failed to save Excel file: {e}", 500)

    context: Dict[str, Any] = {
        "proposal_id": pid,
        "config": cfg,
        "excel_file_path": temp_excel_path,
        "excel_filename": getattr(excel_file, 'filename', 'uploaded.xlsx'),
    }

    try:
        result = generate_payment_proposal_adapter(context)
    except Exception as e:
        return _error(f"Crew error: {e}", 500)

    # Normalize result to dict - handle CrewOutput objects
    if hasattr(result, 'raw'):
        # CrewOutput object - extract the raw JSON string
        try:
            result = json.loads(result.raw)
        except Exception:
            result = {"raw": result.raw}
    elif isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {"raw": result}

    # Persist in-memory and to disk
    proposals[pid] = result

    out_dir = _make_output_dir()
    out_path = os.path.join(out_dir, f"proposal_{pid}.json")
    try:
        with open(out_path, 'w') as f:
            json.dump(result, f, indent=2)
    except Exception:
        # Don't fail request purely due to IO; log silently in real app
        pass

    body = {
        "success": True,
        "proposal_id": pid,
        "message": "Proposal generated successfully.",
        "next_step": f"GET /get_payment_proposal/{pid}",
    }

    # 202 Accepted with Location is preferred, but tests accept 200 or 202
    resp = jsonify(body)
    resp.status_code = 202
    resp.headers['Location'] = f"/get_payment_proposal/{pid}"
    return resp

@app.route('/get_payment_proposal/<string:proposal_id>', methods=['GET'])
def get_payment_proposal(proposal_id):
    """Returns the stored payment proposal for human review."""
    try:
        if proposal_id in proposals:
            return jsonify(proposals[proposal_id]), 200
        return _error("Proposal not found", 404)
    except Exception as e:
        return _error(f"Internal error: {e}", 500)

@app.route('/submit_payment_approval', methods=['POST'])
def submit_payment_approval():
    """Submits the human decision on the payment proposal."""
    # Check if request has JSON data
    if not request.is_json:
        return _error("Request must be JSON", 400)
    
    try:
        data = request.get_json()
        if not data:
            return _error("Missing JSON body", 400)
    except Exception:
        return _error("Invalid JSON syntax", 400)
    
    # Validate request data per API documentation
    try:
        _validate_payment_approval(data)
    except ValueError as ve:
        return _error(str(ve), 400)
    
    proposal_id = data["proposal_id"]
    
    # Check if proposal exists
    if proposal_id not in proposals:
        return _error("Proposal not found", 404)
    
    # Get existing proposal data
    proposal_data = proposals[proposal_id]
    
    # Prepare context for payment execution
    context = {
        "proposal_id": proposal_id,
        "proposal_data": proposal_data,
        "custody_wallet": data["custody_wallet"],
        "private_key": data["private_key"],
        "approval_decision": data["approval_decision"],
        "approved_payments": data.get("approved_payments", []),
        "comments": data.get("comments", "")
    }
    
    # Execute payment approval via crew
    try:
        execution_result = execute_payment_approval_adapter(context)
    except Exception as e:
        return _error(f"Payment execution failed: {e}", 500)
    
    # Normalize execution result - handle CrewOutput objects
    if hasattr(execution_result, 'raw'):
        # CrewOutput object - extract the raw JSON string
        try:
            execution_result = json.loads(execution_result.raw)
        except Exception:
            execution_result = {"execution_status": "FAILURE", "message": execution_result.raw}
    elif isinstance(execution_result, str):
        try:
            execution_result = json.loads(execution_result)
        except Exception:
            execution_result = {"execution_status": "FAILURE", "message": execution_result}
    
    # Extract execution status and message
    execution_status = execution_result.get("execution_status", "FAILURE")
    message = execution_result.get("message", "Payment execution completed")
    
    # Update proposal with execution results
    proposals[proposal_id]["execution_result"] = execution_result
    
    # Save execution results to file
    out_dir = _make_output_dir()
    result_path = os.path.join(out_dir, f"execution_result_{proposal_id}.json")
    try:
        with open(result_path, 'w') as f:
            json.dump(execution_result, f, indent=2)
    except Exception:
        # Don't fail request purely due to IO
        pass
    
    # Return success response per API documentation
    response_body = {
        "success": True,
        "execution_status": execution_status,
        "message": message,
        "next_step": f"GET /payment_execution_result/{proposal_id}"
    }
    
    return jsonify(response_body), 200

@app.route('/payment_execution_result/<string:proposal_id>', methods=['GET'])
def get_payment_execution_result(proposal_id):
    """Returns the detailed result of the payment execution."""
    try:
        # Check if proposal exists
        if proposal_id not in proposals:
            return _error("Proposal not found", 404)
        
        proposal_data = proposals[proposal_id]
        
        # Check if execution result exists
        if 'execution_result' not in proposal_data:
            return _error("No execution result found for this proposal", 404)
        
        execution_result = proposal_data['execution_result']
        
        # Best-effort cleanup of disk artifacts for this proposal before returning
        try:
            _cleanup_proposal_artifacts(proposal_id)
        except Exception:
            pass
        
        # Return execution result per API documentation
        return jsonify(execution_result), 200
        
    except Exception as e:
        return _error(f"Internal error: {e}", 500)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)


