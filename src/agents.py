from crewai import Agent, LLM
import os
from dotenv import load_dotenv, find_dotenv

class TreasuryAgents:
    def __init__(self):
        # Load environment variables from .env if present, giving .env precedence locally
        # If no .env is found, keep existing environment (e.g., Render-provided vars)
        env_path = find_dotenv()
        if env_path:
            load_dotenv(env_path, override=True)

        # Require per-agent model configuration (no fallback)
        self._risk_model = os.getenv("RISK_ASSESSOR_MODEL")
        self._proposal_model = os.getenv("PROPOSAL_PROCESSOR_MODEL")
        self._payment_model = os.getenv("PAYMENT_SPECIALIST_MODEL")

        missing = []
        if not self._risk_model:
            missing.append("RISK_ASSESSOR_MODEL")
        if not self._proposal_model:
            missing.append("PROPOSAL_PROCESSOR_MODEL")
        if not self._payment_model:
            missing.append("PAYMENT_SPECIALIST_MODEL")

        if missing:
            raise ValueError(
                "Missing required per-agent model env variables: " + ", ".join(missing) +
                ". Please set them in Agent-3.0/.env."
            )

        # Per-agent LLM runtime configuration (coded here as requested)
        # Credentials are read from environment by CrewAI/underlying provider libraries.
        self._risk_llm = LLM(
            model=self._risk_model,
            temperature=0.3,
            max_tokens=2000,
        )
        self._proposal_llm = LLM(
            model=self._proposal_model,
            temperature=0.1,
            max_tokens=3000,
        )
        self._payment_llm = LLM(
            model=self._payment_model,
            temperature=0.1,
            max_tokens=1500,
        )

    def risk_assessor(self):
        return Agent(
            role="Risk Assessor",
            goal="Analyze financial data to identify and quantify risks",
            backstory=(
                "With a keen eye for detail and a deep understanding of financial markets, "
                "you specialize in identifying potential risks in payment proposals. Your mission is to ensure every transaction is scrutinized for compliance and financial stability."
            ),
            verbose=True,
            allow_delegation=False,
            llm=self._risk_llm,
        )

    def proposal_processor(self):
        return Agent(
            role="Payment Proposal Processor",
            goal="Create structured, clear, and accurate payment proposals based on risk assessment",
            backstory=(
                "You are a meticulous planner, skilled in translating complex financial data and risk assessments into actionable payment proposals. Your work ensures that all necessary information is presented clearly for human review."
            ),
            verbose=True,
            allow_delegation=False,
            llm=self._proposal_llm,
        )

    def payment_specialist(self):
        return Agent(
            role="Payment Execution Specialist",
            goal="Execute approved payments accurately and securely",
            backstory=(
                "As a specialist in financial transactions, you are responsible for the final step of the payment process. You handle the execution of payments with precision, ensuring that funds are transferred correctly and securely after human approval."
            ),
            verbose=True,
            allow_delegation=False,
            llm=self._payment_llm,
        )