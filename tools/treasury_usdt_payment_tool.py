from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
import random
import string
import os
import json
from web3 import Web3
from web3.exceptions import (
    TransactionNotFound, TimeExhausted, MismatchedABI, 
    InvalidTransaction, BlockNotFound, InvalidAddress, ValidationError
)


class USDTPaymentInput(BaseModel):
    """Input schema for TreasuryUSDTPaymentTool."""
    action: str = Field(..., description="Action to perform: 'check_balance', 'estimate_gas', 'execute_payment', 'validate_address', or 'check_status'")
    wallet_address: str = Field(default="", description="Ethereum wallet address")
    recipient_address: str = Field(default="", description="Recipient wallet address")
    amount_usdt: float = Field(default=0.0, description="Amount of USDT to transfer")
    private_key: str = Field(default="", description="Private key for transaction signing (encrypted)")
    transaction_id: str = Field(default="", description="Transaction ID for status checks")


class TreasuryUSDTPaymentTool(BaseTool):
    name: str = "USDT Payment Tool"
    description: str = (
        "USDT payment processing tool for Ethereum blockchain. "
        "Supports balance checking, gas estimation, payment execution, address validation, and transaction status tracking. "
        "Uses user-provided wallet information for self-custody transactions."
    )
    args_schema: Type[BaseModel] = USDTPaymentInput

    def __init__(self):
        super().__init__()
        # Initialize instance variables after super().__init__()
        self._infura_key = os.getenv('INFURA_API_KEY')
        self._usdt_contract_address = '0xdAC17F958D2ee523a2206206994597C13D831ec7'
        self._w3 = None
        self._usdt_contract = None
        self._max_usdt_gas = 401000
        self._min_eth_balance_for_transaction = 0.0005
        
        # Initialize Web3 if Infura key is available
        if self._infura_key:
            self._initialize_web3()
            self._load_usdt_contract()

    def _initialize_web3(self):
        """Initialize Web3 connection to Ethereum mainnet."""
        try:
            self._w3 = Web3(Web3.HTTPProvider(f'https://mainnet.infura.io/v3/{self._infura_key}'))
            if not self._w3.is_connected():
                print("Warning: Failed to connect to Ethereum node. Using simulation mode.")
                self._w3 = None
            else:
                print("Connected to Ethereum mainnet")
        except Exception as e:
            print(f"Warning: Could not initialize Web3: {str(e)}. Using simulation mode.")
            self._w3 = None

    def _load_usdt_contract(self):
        """Load USDT contract ABI and initialize contract instance."""
        if not self._w3:
            return
            
        # USDT contract ABI (simplified version with essential functions)
        usdt_abi = [
            {
                "constant": True,
                "inputs": [{"name": "who", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_to", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "transfer",
                "outputs": [],
                "type": "function"
            }
        ]
        
        try:
            self._usdt_contract = self._w3.eth.contract(
                address=self._usdt_contract_address, 
                abi=usdt_abi
            )
        except Exception as e:
            print(f"Warning: Could not load USDT contract: {str(e)}")

    def _run(self, action: str, wallet_address: str = "", recipient_address: str = "", 
             amount_usdt: float = 0.0, private_key: str = "", transaction_id: str = "") -> str:
        
        if action == "check_balance":
            return self._check_balance(wallet_address)
        elif action == "estimate_gas":
            return self._estimate_gas()
        elif action == "execute_payment":
            return self._execute_payment(wallet_address, recipient_address, amount_usdt, private_key)
        elif action == "validate_address":
            return self._validate_address(wallet_address or recipient_address)
        elif action == "check_status":
            return self._check_status(transaction_id)
        else:
            return f"Unknown action: {action}. Available actions: check_balance, estimate_gas, execute_payment, validate_address, check_status"

    def _check_balance(self, wallet_address: str) -> str:
        """Check USDT and ETH balance for a wallet address."""
        if not wallet_address:
            return "Error: Wallet address is required for balance check."
        
        if not self._w3:
            # Simulation mode
            eth_balance = random.uniform(0.001, 0.1)
            usdt_balance = random.uniform(10.0, 1000.0)
            eth_usd_value = eth_balance * 3500  # Mock ETH price
        else:
            try:
                address = Web3.to_checksum_address(wallet_address)
                
                # Get ETH balance
                balance_wei = self._w3.eth.get_balance(address)
                eth_balance = self._w3.from_wei(balance_wei, 'ether')
                
                # Get USDT balance
                balance_wei = self._usdt_contract.functions.balanceOf(address).call()
                usdt_balance = float(balance_wei) / 10**6
                
                # Get ETH price (simplified)
                eth_usd_value = float(eth_balance) * 3500  # Mock price
                
            except Exception as e:
                return f"Error checking balance: {str(e)}"
        
        result = f"Wallet Balance Check:\n"
        result += f"Address: {wallet_address}\n"
        result += f"ETH Balance: {eth_balance:.6f} ETH (≈${eth_usd_value:.2f})\n"
        result += f"USDT Balance: {usdt_balance:.2f} USDT\n"
        result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Add balance status
        if eth_balance < self._min_eth_balance_for_transaction:
            result += f"⚠️  Warning: ETH balance may be insufficient for gas fees\n"
        
        return result

    def _estimate_gas(self) -> str:
        """Estimate gas cost for USDT transaction."""
        if not self._w3:
            # Simulation mode
            gas_price_gwei = random.uniform(20, 50)
            gas_limit = self._max_usdt_gas
            adjusted_gas_price = gas_price_gwei * 1.35
        else:
            try:
                gas_price_gwei = self._w3.eth.gas_price
                gas_price_gwei = self._w3.from_wei(gas_price_gwei, 'gwei')
                gas_limit = self._max_usdt_gas
                adjusted_gas_price = gas_price_gwei * 1.35  # Add 35% buffer for USDT
            except Exception as e:
                return f"Error estimating gas: {str(e)}"
        
        gas_cost_eth = (adjusted_gas_price * gas_limit) / 1_000_000_000
        
        result = f"Gas Estimation for USDT Transaction:\n"
        result += f"Current Gas Price: {gas_price_gwei:.2f} Gwei\n"
        result += f"Adjusted Gas Price: {adjusted_gas_price:.2f} Gwei (35% buffer)\n"
        result += f"Gas Limit: {gas_limit:,} units\n"
        result += f"Estimated Cost: {gas_cost_eth:.6f} ETH\n"
        result += f"Estimated Cost USD: ${gas_cost_eth * 3500:.2f} (at $3500/ETH)\n"
        result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        return result

    def _execute_payment(self, wallet_address: str, recipient_address: str, 
                        amount_usdt: float, private_key: str) -> str:
        """Execute USDT payment (simulated for testing)."""
        if not wallet_address or not recipient_address:
            return "Error: Both wallet address and recipient address are required."
        
        if amount_usdt <= 0:
            return "Error: Amount must be greater than 0."
        
        if not private_key:
            return "Error: Private key is required for transaction signing."
        
        # Generate mock transaction ID
        tx_id = 'TX' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # Validate addresses
        try:
            if self._w3:
                Web3.to_checksum_address(wallet_address)
                Web3.to_checksum_address(recipient_address)
        except Exception as e:
            return f"Error: Invalid address format - {str(e)}"
        
        # Check minimum amount
        if amount_usdt < 0.1:
            return f"Error: Amount too low: {amount_usdt} USDT. Minimum is 0.1 USDT."
        
        # Simulate processing time
        processing_time = random.randint(1, 3)  # 1-3 seconds simulation
        
        # Mock execution with realistic scenarios
        success_rate = 0.98  # 98% success rate
        
        if random.random() < success_rate:
            status = "SUCCESS"
            estimated_completion = datetime.now() + timedelta(
                minutes=random.randint(1, 5)
            )
            
            # SIMULATION MODE - Return success message instead of actual transaction
            result = f"USDT Payment Execution Result (SIMULATION MODE):\n"
            result += f"Transaction ID: {tx_id}\n"
            result += f"Status: {status}\n"
            result += f"From: {wallet_address}\n"
            result += f"To: {recipient_address}\n"
            result += f"Amount: {amount_usdt} USDT\n"
            result += f"Processing Time: {processing_time} seconds\n"
            result += f"Estimated Completion: {estimated_completion.strftime('%Y-%m-%d %H:%M:%S')}\n"
            result += f"Gas Cost: ~0.0001 ETH (estimated)\n"
            result += f"✅ SIMULATION: Transaction would be successful\n"
            result += f"📝 Note: This is a simulation. Real transaction would execute here.\n"
            result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return result
            
        else:
            # Simulate various failure scenarios
            failures = [
                "INSUFFICIENT_USDT_BALANCE",
                "INSUFFICIENT_ETH_FOR_GAS", 
                "INVALID_RECIPIENT_ADDRESS",
                "NETWORK_TIMEOUT"
            ]
            status = random.choice(failures)
            
            result = f"USDT Payment Execution Result (SIMULATION MODE):\n"
            result += f"Transaction ID: {tx_id}\n"
            result += f"Status: {status}\n"
            result += f"From: {wallet_address}\n"
            result += f"To: {recipient_address}\n"
            result += f"Amount: {amount_usdt} USDT\n"
            result += f"Processing Time: {processing_time} seconds\n"
            result += f"❌ SIMULATION: Transaction would fail due to {status.replace('_', ' ').lower()}\n"
            result += f"📝 Note: This is a simulation. Real transaction would fail here.\n"
            result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return result

    def _validate_address(self, address: str) -> str:
        """Validate if an address is a valid Ethereum address."""
        if not address:
            return "Error: Address is required for validation."
        
        try:
            if self._w3:
                Web3.to_checksum_address(address)
            else:
                # Basic validation for simulation mode
                if not address.startswith('0x') or len(address) != 42:
                    raise ValueError("Invalid address format")
            
            result = f"Address Validation Result:\n"
            result += f"Address: {address}\n"
            result += f"Status: ✅ VALID\n"
            result += f"Format: Ethereum address\n"
            result += f"Checksum: {Web3.to_checksum_address(address) if self._w3 else 'N/A (simulation)'}\n"
            result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return result
            
        except Exception as e:
            result = f"Address Validation Result:\n"
            result += f"Address: {address}\n"
            result += f"Status: ❌ INVALID\n"
            result += f"Error: {str(e)}\n"
            result += f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return result

    def _check_status(self, transaction_id: str) -> str:
        """Check transaction status (simulated)."""
        if not transaction_id:
            return "Error: Transaction ID is required for status checks."
        
        # Mock status responses
        statuses = [
            ("PROCESSING", "Transaction is being processed on the Ethereum network"),
            ("CONFIRMED", "Transaction has been confirmed on the blockchain"),
            ("COMPLETED", "USDT transfer has been successfully delivered to recipient"),
            ("PENDING", "Transaction is pending network confirmation"),
            ("FAILED", "Transaction failed due to insufficient gas or network error"),
            ("CANCELLED", "Transaction was cancelled due to low gas price")
        ]
        
        status, description = random.choice(statuses)
        
        result = f"Transaction Status Check (SIMULATION MODE):\n"
        result += f"Transaction ID: {transaction_id}\n"
        result += f"Current Status: {status}\n"
        result += f"Description: {description}\n"
        result += f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if status == "COMPLETED":
            result += f"✅ SIMULATION: Transaction would be completed successfully!\n"
        elif status == "FAILED":
            result += f"❌ SIMULATION: Transaction would have failed.\n"
        elif status in ["PROCESSING", "PENDING"]:
            result += f"⏳ SIMULATION: Transaction would be in progress.\n"
        
        result += f"📝 Note: This is a simulation. Real status would be checked here.\n"
        
        return result 