from flask import Flask, request, jsonify
import os
import json
import uuid
from typing import Any, Dict

app = Flask(__name__)

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
    required_top = ["user_id", "custody_wallet", "risk_config"]
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

def _make_output_dir() -> str:
    root = os.path.abspath(os.path.dirname(__file__))
    out = os.path.join(root, 'output')
    os.makedirs(out, exist_ok=True)
    return out

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

    # Normalize result to dict
    if isinstance(result, str):
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
    pass

@app.route('/payment_execution_result/<string:proposal_id>', methods=['GET'])
def get_payment_execution_result(proposal_id):
    """Returns the detailed result of the payment execution."""
    pass

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)


