# Treasury Manager AI Agent API Documentation

## 1. Overview

The Treasury Manager AI Agent API automates a comprehensive treasury workflow for payment processing. The system uses a multi-agent architecture orchestrated by CrewAI to handle complex financial tasks, with Human-in-the-Loop (HITL) checkpoints for critical decisions.

**Base URL**: `http://localhost:5001`

## 2. Architecture

The API follows a stateful, multi-step workflow:

1.  **Submit Request**: Upload an Excel file and JSON configuration to generate payment proposals.
2.  **Review Payment Proposal**: Retrieve and review the generated payment proposal.
3.  **Approve Payment Proposal**: Approve, reject, or partially approve payments (HITL #1).
4.  **Get Payment Execution Result**: Retrieve the results of the payment execution.

## 3. API Endpoints

### Health Check

*   **Endpoint**: `GET /health`
*   **Description**: Checks if the service is running.
*   **Response**: `{"status": "healthy"}`

---

### Workflow Step 1: Submit Request

*   **Endpoint**: `POST /submit_request`
*   **Description**: Accepts an Excel file and JSON configuration, processes them with an AI agent crew, and returns a unique `proposal_id`.
*   **Request**: `multipart/form-data` with `excel` (file) and `json` (string).
*   **JSON Configuration**:
    ```json
    {
      "user_id": "string",
      "custody_wallet": "string",
      "private_key": "string",
      "risk_config": {
        "min_balance_usd": "number",
        "transaction_limits": {
          "single": "number",
          "daily": "number"
        }
      },
      "user_notes": "string"
    }
    ```
*   **Success Response**:
    ```json
    {
      "success": true,
      "proposal_id": "unique-proposal-id",
      "message": "Proposal generated successfully.",
      "next_step": "GET /get_payment_proposal/{proposal_id}"
    }
    ```

---

### Workflow Step 2: Get Payment Proposal

*   **Endpoint**: `GET /get_payment_proposal/<proposal_id>`
*   **Description**: Returns the stored payment proposal for human review.
*   **Success Response Body**:
    ```json
    {
      "proposal_id": "unique-proposal-id",
      "report": "string",
      "payments": [
        {
          "payment_id": "unique-payment-id-1",
          "recipient_wallet": "string",
          "amount": "number",
          "reference": "string"
        }
      ]
    }
    ```

---

### Workflow Step 3: Submit Payment Proposal Approval

*   **Endpoint**: `POST /submit_payment_approval`
*   **Description**: Submits the human decision on the payment proposal.
*   **Request Body**:
    ```json
    {
      "proposal_id": "string",
      "approval_decision": "approve_all | reject_all | partial",
      "approved_payments": ["payment_id_1", ...],
      "comments": "string"
    }
    ```
*   **Success Response**:
    ```json
    {
      "success": true,
      "execution_status": "SUCCESS | PARTIAL_SUCCESS | FAILURE",
      "message": "Execution summary.",
      "next_step": "GET /payment_execution_result/{proposal_id}"
    }
    ```

---

### Workflow Step 4: Get Payment Execution Result

*   **Endpoint**: `GET /payment_execution_result/<proposal_id>`
*   **Description**: Returns the detailed result of the payment execution.
*   **Success Response**: A JSON object containing `proposal_id`, `execution_status`, `executed_payments`, and `failed_payments`.

---

## 4. Data Models

### Payment Proposal

```json
{
  "payment_id": "string",
  "recipient_wallet": "string",
  "amount": "number",
  "currency": "USDT",
  "purpose": "string"
}
```


## 5. Error Handling

The API uses standard HTTP status codes (`400`, `404`, `500`) with a consistent JSON error body:

```json
{
  "error": "Error description",
  "success": false
}
```