# Treasury Manager AI Agent: Requirements Specification


## 1. Overview
The Treasury Manager AI Agent automates financial processes, including risk assessment, payment proposal generation, and payment execution. The system uses **CrewAI for agent orchestration** and **CrewAI Flow** for workflow sequencing, with **human-in-the-loop (HITL)** checkpoints to ensure compliance.

---

## 2. Core Components

### 2.1 Agents
- **Manager Agent**: Oversees the workflow, coordinates tasks, and enforces rules.
- **Risk Assessor Agent**:  
  - Evaluates financial data extracted from Excel files.  
  - Considers **user input constraints** (minimum balance, transaction limits, special conditions).  
  - Returns risk assessment report to Manager Agent.
- **Payment Specialist Agent**: Generates and formats payment proposals based on validated data.

### 2.2 Tools
- **Excel Parser & Normalizer**: Handles unpredictable Excel uploads, extracts, and standardizes data for agents.
- **Proposal Formatter**: Standardizes payment proposals for human review.
- **Execution Tools**: Interfaces for executing payments in connected financial systems.
- **HITL Interface**: User-friendly interface for human approval/rejection of proposals and investment plans.
- **Notification System**: Alerts human reviewers when approvals are needed.

---

## 3. Workflow Structure
Hierarchical workflow coordinated by **Manager Agent**:

1. **Excel Upload Handling**:  
   - User uploads Excel file (unpredictable format).  
   - **Excel Parser & Normalizer** extracts and standardizes data.

2. **Risk Assessment**:  
   - **Risk Assessor Agent** evaluates financial data **and user constraints**.  
   - Returns risk report to Manager Agent.

3. **Payment Proposal Generation**:  
   - **Payment Specialist Agent** generates and formats the payment proposal.

4. **HITL #1: Human Approval of Payment Proposal**  
   - Human approves/rejects via interface.  
   - Reject → Workflow ends; Approve → Proceed to payment execution.

5. **Payment Execution**:  
   - Manager triggers execution after approval.

6. **Workflow Completion**:  
   - Ends after payment execution or rejection at the HITL point.

---

## 4. Integration with CrewAI & CrewAI Flow
- **CrewAI**: Manages agents and task delegation.  
- **CrewAI Flow**: Defines hierarchical workflow with branching, sequencing, and HITL integration.

---

## 5. Input/Output Specifications
- **Input**: Required user info + unpredictable Excel file.  
- **Output**:  
  - Risk assessment report.  
  - Formatted payment proposal for HITL.  
  - Executed payment confirmation.  
  

- **Format requirements**: Structured JSON schema for agent communication.

---

## 6. Error Handling and Recovery
- Handle unpredictable Excel formats.  
- Handle invalid user inputs (e.g., negative balances, limit exceeded).  
- Retry mechanisms for failed tasks.  
- Logging and alerts for errors.

---

## 7. Human-in-the-Loop (HITL) Requirements
- Approval after payment proposal generation.  
- HITL interface with structured views of proposals and plans.  
- Notifications and reminders for pending approvals.  
- Escalation policies if humans do not respond in time.

---


## 8. Performance and Scalability
- Maximum concurrent workflows.  
- Expected Excel file sizes.  
- Performance targets (latency, throughput).  

---

## 9. Extensibility
- Ability to add new agents or tasks in the future.  
- Modular tools for easy replacement (e.g., Excel parser, investment allocator).

---

## 11. Testing and Validation
- Unit testing for each agent.  
- Integration testing for CrewAI workflow.  
- Simulation of HITL approvals and Excel variations.

---

## 12. Deployment and Monitoring
- Deployment method for CrewAI and CrewAI Flow.  
- Monitoring of agent health, workflow status, and errors.

---

## 13. Agent Capabilities
- Limitations and scope of each agent.  
- Tool usage boundaries.  
- Reporting structure to Manager Agent.

---

## 14. Workflow Logic
- Hierarchical orchestration with Manager Agent controlling task delegation.  
- Sequencing rules enforced by Manager Agent.  
- Conditional branching (e.g., skip investment if no remaining balance).

---

## 15. Tools & Implementation Suggestions

### 1. Excel Parser & Normalizer
- **Purpose**: Handle unpredictable Excel uploads, extract data, and standardize it for agents.
- **Suggested Libraries**: `pandas`, `openpyxl`, `xlrd`.
- **Implementation Notes**: Detect sheets/headers dynamically, normalize columns, handle merged cells/empty rows, output JSON/DataFrame.

### 2. Risk Assessor Tools
- **Purpose**: Validate financial data and user constraints.
- **Suggested Libraries**: `pandas`, custom Python rules.
- **Notes**: Integrate with CrewAI agent; return structured JSON risk reports.

### 3. Payment Proposal Tools
- **Purpose**: Generate and format payment proposals.
- **Libraries**: `jinja2`, `pandas`, `tabulate`.
- **Notes**: Standardize layout, include metadata; output HTML, PDF, or JSON.

### 4. Execution Tools
- **Purpose**: Execute payments.
- **Libraries**: REST clients (`requests`), platform SDKs.
- **Notes**: Ensure transactional safety, confirm execution, handle retries/failures.


### 6. HITL Interface Tools
- **Purpose**: Allow human approvals/rejections.
- **Libraries/Frameworks**: `Streamlit`, `Flask`, `FastAPI`, HTML/JS.
- **Notes**: Display proposals/plans clearly, capture decisions/timestamps, trigger notifications.

### 7. Logging and Monitoring
- **Purpose**: Audit workflow execution and errors.
- **Libraries**: Python `logging`, optional `Sentry`, `Prometheus`, ELK stack.
- **Notes**: Log agent outputs, HITL approvals, executions; include timestamps and workflow IDs.


Workflow:

[Frontend User]
     |
     v
[Submit Excel + Required Info]
     |
     v
[Backend Server Starts CrewAI Flow]
     |
     v
[Manager Agent]  <-- Controls flow & enforces rules
     |
     ├──> [Risk Assessor Agent]
     |       └─ Analyze user input (constraints: min balance, transaction limits)
     |       └─ Return risk report to Manager
     |
     ├──> [Payment Specialist Agent]
     |       └─ Generate Payment Proposal
     |       └─ Format proposal (structured output)
     |       └─ Return formatted proposal to Manager
     |
     ├── HITL #1: Human Approval of Payment Proposal
     |       ├─ Approve → Proceed to payment
     |       └─ Reject → End Workflow
     |
     ├──> [Execute Payment]  <-- Triggered only after approval
     |
     v
[End Workflow]

