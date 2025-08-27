# Agent-3.0

Treasury agent server that ingests an Excel file and a JSON config to produce a payment proposal, accepts human approval, and executes USDT payments via Web3. LLM reasoning is handled by CrewAI agents configured via environment variables.

## Quickstart (local)

1. Create `.env` in `Agent-3.0/` (see Environment Variables below).
2. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python flask_server.py
   # or production
   gunicorn -w 2 -b 0.0.0.0:5001 --timeout 600 flask_server:app
   ```
4. Health check: `GET http://localhost:5001/health`

## API Endpoints

- **GET /health**
  - Returns `{ "status": "healthy" }`.

- **POST /submit_request**
  - Multipart form-data:
    - `excel`: Excel file (.xlsx)
    - `json`: JSON string payload. Minimal shape:
      ```json
      {
        "user_id": "<string>",
        "risk_config": {
          "min_balance_usd": <number>,
          "transaction_limits": { "single": <number>, "daily": <number> }
        },
        "user_notes": "<optional string>"
      }
      ```
  - Response: `202 Accepted` with headers `Location: /get_payment_proposal/{proposal_id}` and body:
    ```json
    { "success": true, "proposal_id": "...", "message": "...", "next_step": "GET /get_payment_proposal/{id}" }
    ```

- **GET /get_payment_proposal/{proposal_id}**
  - Returns the generated proposal JSON for human review.

- **POST /submit_payment_approval**
  - JSON body:
    ```json
    {
      "proposal_id": "<string>",
      "custody_wallet": "<0xAddress>",
      "private_key": "<hex_private_key>",
      "approval_decision": "approve_all | reject_all | partial",
      "approved_payments": [ { /* payment items if partial */ } ],
      "comments": "<optional string>"
    }
    ```
  - Response: `200 OK` with execution summary and `next_step` to fetch detailed result.

- **GET /payment_execution_result/{proposal_id}**
  - Returns detailed execution result JSON. Performs best-effort cleanup of temporary artifacts.

### Error format

Errors follow:
```json
{ "error": "<message>", "success": false }
```

## Environment Variables

LLM models (Amazon Bedrock in current setup):
- `RISK_ASSESSOR_MODEL` (e.g., `bedrock/us.amazon.nova-pro-v1:0`)
- `PROPOSAL_PROCESSOR_MODEL` (e.g., `bedrock/us.amazon.nova-pro-v1:0`)
- `PAYMENT_SPECIALIST_MODEL` (e.g., `bedrock/us.amazon.nova-pro-v1:0`)

AWS credentials for Bedrock:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION_NAME` (e.g., `us-east-1`)

Blockchain access:
- `INFURA_API_KEY` (required for Ethereum/Web3 interactions in USDT tool)

Operational (optional):
- `AGENT_STORAGE_DIR` (e.g., `/tmp` on Render). Defaults to `Agent-3.0/tmp` if unset.
- `PORT` (Render sets automatically; for local dev defaults to `5001`).

Note: The server prefers `.env` values locally via `python-dotenv`; in hosted environments without `.env`, it uses process environment variables (e.g., Render).

## Deploy to Render

- Root Directory: `Agent-3.0`
- Build Command:
  ```bash
  pip install -r requirements.txt
  ```
- Start Command:
  ```bash
  gunicorn -w 2 -b 0.0.0.0:$PORT --timeout 600 flask_server:app
  ```
- Environment Variables: set the ones listed above (LLM models, AWS creds, `INFURA_API_KEY`, optional `AGENT_STORAGE_DIR=/tmp`).

## Notes

- Inputs/outputs may be persisted temporarily under the storage directory. Cleanup is best-effort after returning execution results.
- Keep secrets out of source control. Rotate any exposed credentials.