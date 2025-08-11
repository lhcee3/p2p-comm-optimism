"""
Optimism L2 Configuration
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class OptimismConfig:
    """Configuration for Optimism L2 connection"""
    
    # Network settings
    rpc_url: str = "https://mainnet.optimism.io"
    chain_id: int = 10
    
    # For testing, use Optimism Goerli
    testnet_rpc_url: str = "https://goerli.optimism.io"
    testnet_chain_id: int = 420
    
    # Contract addresses (example NFT contract)
    nft_contract_address: str = "0x1234567890123456789012345678901234567890"
    
    # Gas settings
    max_gas_price: int = 20_000_000_000  # 20 gwei
    gas_limit: int = 300_000
    
    # Private key for transactions (should be loaded from env)
    private_key: Optional[str] = None
    
    # Block confirmation requirements
    confirmation_blocks: int = 1
    
    # Timeout settings
    transaction_timeout: int = 60  # seconds
    
    @classmethod
    def for_testnet(cls) -> "OptimismConfig":
        """Create configuration for testnet"""
        return cls(
            rpc_url=cls.testnet_rpc_url,
            chain_id=cls.testnet_chain_id
        )


@dataclass
class P2PConfig:
    """Configuration for libp2p networking"""
    
    # Default listen addresses
    listen_addresses: list = None
    
    # Bootstrap peers for discovery
    bootstrap_peers: list = None
    
    # Protocol configurations
    gossip_protocol: str = "/op/gossip/1.0.0"
    intent_protocol: str = "/op/intent/1.0.0"
    sync_protocol: str = "/op/sync/1.0.0"
    
    # Message limits
    max_message_size: int = 1024 * 1024  # 1MB
    message_cache_size: int = 1000
    
    # Peer limits
    max_peers: int = 50
    min_peers: int = 3
    
    def __post_init__(self):
        if self.listen_addresses is None:
            self.listen_addresses = ["/ip4/0.0.0.0/tcp/0"]
        
        if self.bootstrap_peers is None:
            self.bootstrap_peers = []
