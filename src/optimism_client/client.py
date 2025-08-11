"""
Optimism L2 client for blockchain interactions
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from web3 import Web3
try:
    from web3.middleware import geth_poa_middleware
except ImportError:
    # Newer web3 versions
    try:
        from web3.middleware.proof_of_authority import geth_poa_middleware
    except ImportError:
        # Mock for compatibility
        def geth_poa_middleware(make_request, web3):
            return make_request

from eth_account import Account
from eth_utils import to_checksum_address
import json

from config.optimism_config import OptimismConfig


logger = logging.getLogger(__name__)


class OptimismClient:
    """Client for interacting with Optimism L2 network"""
    
    def __init__(self, config: OptimismConfig):
        self.config = config
        self.w3 = Web3(Web3.HTTPProvider(config.rpc_url))
        
        # Add PoA middleware for Optimism
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Set up account if private key is provided
        self.account = None
        if config.private_key:
            self.account = Account.from_key(config.private_key)
    
    async def connect(self) -> bool:
        """Test connection to Optimism network"""
        try:
            latest_block = await self._get_latest_block()
            logger.info(f"Connected to Optimism. Latest block: {latest_block}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Optimism: {e}")
            return False
    
    async def _get_latest_block(self) -> int:
        """Get the latest block number"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.w3.eth.block_number)
    
    async def get_balance(self, address: str) -> float:
        """Get ETH balance for an address"""
        loop = asyncio.get_event_loop()
        balance_wei = await loop.run_in_executor(
            None, 
            lambda: self.w3.eth.get_balance(to_checksum_address(address))
        )
        return self.w3.from_wei(balance_wei, 'ether')
    
    async def send_transaction(
        self, 
        to_address: str, 
        value: int = 0, 
        data: bytes = b'',
        gas_limit: Optional[int] = None
    ) -> str:
        """Send a transaction to the network"""
        if not self.account:
            raise ValueError("No account configured for sending transactions")
        
        # Get current gas price
        gas_price = await self._get_gas_price()
        
        # Build transaction
        transaction = {
            'to': to_checksum_address(to_address),
            'value': value,
            'gas': gas_limit or self.config.gas_limit,
            'gasPrice': gas_price,
            'nonce': await self._get_nonce(self.account.address),
            'data': data,
            'chainId': self.config.chain_id
        }
        
        # Sign and send transaction
        signed_txn = self.account.sign_transaction(transaction)
        
        loop = asyncio.get_event_loop()
        tx_hash = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        )
        
        return tx_hash.hex()
    
    async def call_contract_function(
        self,
        contract_address: str,
        function_name: str,
        function_args: List[Any],
        contract_abi: List[Dict],
        value: int = 0
    ) -> str:
        """Call a smart contract function"""
        contract = self.w3.eth.contract(
            address=to_checksum_address(contract_address),
            abi=contract_abi
        )
        
        # Build transaction data
        function_call = getattr(contract.functions, function_name)(*function_args)
        transaction_data = function_call.build_transaction({
            'from': self.account.address if self.account else None,
            'value': value,
            'gas': self.config.gas_limit,
            'gasPrice': await self._get_gas_price(),
            'nonce': await self._get_nonce(self.account.address) if self.account else 0,
            'chainId': self.config.chain_id
        })
        
        if self.account:
            # Send transaction
            signed_txn = self.account.sign_transaction(transaction_data)
            loop = asyncio.get_event_loop()
            tx_hash = await loop.run_in_executor(
                None,
                lambda: self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            )
            return tx_hash.hex()
        else:
            # Call (read-only)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: function_call.call()
            )
            return str(result)
    
    async def wait_for_transaction_receipt(
        self, 
        tx_hash: str, 
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """Wait for transaction to be mined"""
        timeout = timeout or self.config.transaction_timeout
        
        loop = asyncio.get_event_loop()
        receipt = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.wait_for_transaction_receipt(
                tx_hash, 
                timeout=timeout
            )
        )
        
        return dict(receipt)
    
    async def get_transaction_status(self, tx_hash: str) -> Optional[Dict[str, Any]]:
        """Get transaction status and receipt"""
        try:
            loop = asyncio.get_event_loop()
            receipt = await loop.run_in_executor(
                None,
                lambda: self.w3.eth.get_transaction_receipt(tx_hash)
            )
            return {
                'status': receipt.status,
                'block_number': receipt.blockNumber,
                'gas_used': receipt.gasUsed,
                'transaction_hash': receipt.transactionHash.hex()
            }
        except Exception:
            return None
    
    async def estimate_gas(
        self, 
        to_address: str, 
        data: bytes = b'',
        value: int = 0,
        from_address: Optional[str] = None
    ) -> int:
        """Estimate gas for a transaction"""
        transaction = {
            'to': to_checksum_address(to_address),
            'data': data,
            'value': value
        }
        
        if from_address:
            transaction['from'] = to_checksum_address(from_address)
        elif self.account:
            transaction['from'] = self.account.address
        
        loop = asyncio.get_event_loop()
        gas_estimate = await loop.run_in_executor(
            None,
            lambda: self.w3.eth.estimate_gas(transaction)
        )
        
        return gas_estimate
    
    async def _get_gas_price(self) -> int:
        """Get current gas price"""
        loop = asyncio.get_event_loop()
        gas_price = await loop.run_in_executor(None, lambda: self.w3.eth.gas_price)
        return min(gas_price, self.config.max_gas_price)
    
    async def _get_nonce(self, address: str) -> int:
        """Get nonce for address"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.w3.eth.get_transaction_count(to_checksum_address(address))
        )


class ContractManager:
    """Manages smart contract interactions"""
    
    def __init__(self, optimism_client: OptimismClient):
        self.client = optimism_client
        self.contracts = {}
    
    def add_contract(self, name: str, address: str, abi: List[Dict]):
        """Add a contract to the manager"""
        self.contracts[name] = {
            'address': to_checksum_address(address),
            'abi': abi,
            'contract': self.client.w3.eth.contract(
                address=to_checksum_address(address),
                abi=abi
            )
        }
    
    async def call_function(
        self, 
        contract_name: str, 
        function_name: str, 
        *args, 
        **kwargs
    ) -> Any:
        """Call a function on a managed contract"""
        if contract_name not in self.contracts:
            raise ValueError(f"Contract {contract_name} not found")
        
        contract_info = self.contracts[contract_name]
        return await self.client.call_contract_function(
            contract_info['address'],
            function_name,
            list(args),
            contract_info['abi'],
            kwargs.get('value', 0)
        )
    
    def get_contract_address(self, contract_name: str) -> str:
        """Get the address of a managed contract"""
        if contract_name not in self.contracts:
            raise ValueError(f"Contract {contract_name} not found")
        return self.contracts[contract_name]['address']
