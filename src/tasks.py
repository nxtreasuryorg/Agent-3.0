from crewai import Task, Process
from .agents import TreasuryAgents
# Placeholder for tool imports, assuming they will be created.
# from .tools import ExcelParserTool, PaymentExecutorTool

class TreasuryTasks:
    def __init__(self):
        self.agents = TreasuryAgents()
        # self.excel_parser = ExcelParserTool()
        # self.payment_executor = PaymentExecutorTool()

    def risk_assessment_task(self, context):
        excel_file_path = context.get('excel_file_path', 'unknown')
        risk_assessment_task = Task(
            description=f"""
            Analyze the financial data provided in the Excel file and evaluate risks based on:
            - Data integrity and completeness.
            - User-defined constraints: {context.get('config', {}).get('risk_config', {})}
            - Payment amounts and recipients.
            - Overall financial exposure.
            
            IMPORTANT: Use the Excel Parser Tool with file_path: {excel_file_path}
            
            Generate a detailed risk assessment report with risk scores and recommendations.
            """,
            expected_output="""
            Valid payment list: Recipient Wallet, Amount, Reference
            Risk Assessment: Low/Medium/High
            """,
            expected_output_type="text",
            agent=self.risk_assessor(),
            tools=[self.excel_parser],
        )
        return risk_assessment_task

    def payment_proposal_task(self, context):
        payment_proposal_task = Task(
            description=f"""
            Create a structured payment proposal based on the risk assessment. The report should be
            well-formatted and structured. The content should be about the payment proposal, and each payment
            must include a unique payment_id, recipient_wallet, amount, and reference.
            
            Use proposal_id: {context.get('proposal_id', 'unknown')}
            """,
            expected_output="""
            A JSON object with 'proposal_id', 'report', and a list of 'payments', where each payment has
            'payment_id', 'recipient_wallet', 'amount', and 'reference'.
            Example:
            {{ 
                "proposal_id": "unique-proposal-id",
                "report": "Generated proposal based on risk analysis.",
                "payments": [
                    {{
                        "payment_id": "pay-12345",
                        "recipient_wallet": "0xABC...",
                        "amount": 1500.00,
                        "reference": "string"
                    }}
                ]
            }}
            """,
            agent=self.agents.proposal_processor()
        )
        return payment_proposal_task

    def payment_execution_task(self, context):
        approval_decision = context.get('approval_decision', 'unknown')
        approved_payments = context.get('approved_payments', [])
        proposal_data = context.get('proposal_data', {})
        
        payment_execution_task = Task(
            description=f"""
            Execute the approved payments based on the user's approval details:
            - Approval Decision: {approval_decision}
            - Approved Payments: {approved_payments}
            - Proposal Data: {proposal_data}
            - Custody Wallet: {context.get('custody_wallet', 'not provided')}
            
            Use the Treasury USDT Payment Tool to execute the approved payments.
            The final report should be well-formatted and structured.
            """,
            expected_output="""
            A JSON object containing the 'proposal_id', 'execution_status', and a detailed breakdown of
            'executed_payments' and 'failed_payments'.
            Example:
            {{
                "proposal_id": "unique-proposal-id",
                "execution_status": "SUCCESS | PARTIAL_SUCCESS | FAILURE",
                "executed_payments": [
                    {{ "payment_id": "pay-12345", "status": "SUCCESS", "transaction_hash": "0x123..." }}
                ],
                "failed_payments": [
                    {{ "payment_id": "pay-67890", "status": "FAILED", "reason": "Insufficient funds." }}
                ]
            }}
            """,
            expected_output_type="json",
            agent=self.agents.payment_specialist(),
            tools=[self.payment_executor],
            human_in_the_loop=False
        )
        return payment_execution_task

            
