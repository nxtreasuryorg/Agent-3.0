from crewai import Crew, Process
from typing import Any, Dict, Optional
from src.tasks import TreasuryTasks
from src.agents import TreasuryAgents
from tools.excel_parser_tool import ExcelParserTool
from tools.treasury_usdt_payment_tool import TreasuryUSDTPaymentTool

class TreasuryCrew:
    def __init__(self, excel_parser_tool: Optional[ExcelParserTool] = None, payment_tool: Optional[TreasuryUSDTPaymentTool] = None):
        # Initialize agents and tasks
        self.tasks = TreasuryTasks()
        self.agents = TreasuryAgents()

        # Tools (injectable for testing/config)
        self.excel_parser = excel_parser_tool or ExcelParserTool()
        self.payment_tool = payment_tool or TreasuryUSDTPaymentTool()

        # Wire tools/expected attributes into TreasuryTasks to avoid hardcoding inside tasks
        # TreasuryTasks expects `self.excel_parser` and `self.payment_executor`
        setattr(self.tasks, "excel_parser", self.excel_parser)
        setattr(self.tasks, "payment_executor", self.payment_tool)
        # Some methods in TreasuryTasks refer to `self.risk_assessor()`; ensure it's available
        if not hasattr(self.tasks, "risk_assessor"):
            setattr(self.tasks, "risk_assessor", self.agents.risk_assessor)

    def build_proposal_crew(self, context: Dict[str, Any]) -> Crew:
        """Build a crew to run risk assessment -> proposal generation sequentially."""
        risk_task = self.tasks.risk_assessment_task(context)
        proposal_task = self.tasks.payment_proposal_task(context)

        return Crew(
            agents=[
                self.agents.risk_assessor(),
                self.agents.proposal_processor(),
            ],
            tasks=[risk_task, proposal_task],
            process=Process.sequential,
        )

    def build_execution_crew(self, context: Dict[str, Any]) -> Crew:
        """Build a crew to run payment execution (after human approval)."""
        exec_task = self.tasks.payment_execution_task(context)

        return Crew(
            agents=[
                self.agents.payment_specialist(),
            ],
            tasks=[exec_task],
            process=Process.sequential,
        )

    def generate_payment_proposal(self, context: Dict[str, Any]):
        """Run the proposal pipeline and return the model output."""
        crew = self.build_proposal_crew(context)
        return crew.kickoff(inputs=context)

    def execute_payments(self, context: Dict[str, Any]):
        """Run the execution pipeline and return the model output."""
        crew = self.build_execution_crew(context)
        return crew.kickoff(inputs=context)


# Convenience singletons/functions for simple imports (e.g., from crew import generate_payment_proposal)
_default_crew = TreasuryCrew()

def generate_payment_proposal(context: Dict[str, Any]):
    return _default_crew.generate_payment_proposal(context)

def execute_payments(context: Dict[str, Any]):
    return _default_crew.execute_payments(context)