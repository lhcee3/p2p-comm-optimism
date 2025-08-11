"""
NFT Mint Intent Demo - P2P coordination of NFT minting to avoid gas wars

This demo shows how peers can share NFT mint intentions, coordinate 
to avoid competition, and batch submit to Optimism L2.

Usage:
    # Terminal 1 (Coordinator)
    python examples/nft_mint_intent_demo.py --port 4001 --role coordinator
    
    # Terminal 2 (Participant) 
    python examples/nft_mint_intent_demo.py --port 4002 --role participant --connect /ip4/127.0.0.1/tcp/4001/p2p/<PEER_ID>
"""
import asyncio
import argparse
import logging
import os
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.libp2p_node import LibP2PNode
from src.optimism_client import OptimismClient
from src.dapp_logic import NFTMintCoordinator
from config.optimism_config import OptimismConfig, P2PConfig


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NFTMintDemo:
    """Demo application for NFT mint intent coordination"""
    
    def __init__(self, port: int, role: str):
        self.port = port
        self.role = role
        
        # Configure Optimism client (using testnet for demo)
        self.optimism_config = OptimismConfig.for_testnet()
        self.optimism_client = OptimismClient(self.optimism_config)
        
        # Configure P2P node
        self.p2p_config = P2PConfig()
        self.p2p_node = LibP2PNode(self.p2p_config)
        
        # Initialize coordinator
        self.coordinator = NFTMintCoordinator(self.p2p_node, self.optimism_client)
        
        # Demo state
        self.running = False
        self.demo_nft_contract = "0x1234567890123456789012345678901234567890"  # Example address
    
    async def start(self):
        """Start the demo"""
        logger.info(f"Starting NFT Mint Demo as {self.role} on port {self.port}")
        
        # Start P2P node
        peer_id = await self.p2p_node.start(self.port)
        logger.info(f"P2P Node started with ID: {peer_id}")
        
        # Connect to Optimism (mock connection for demo)
        connected = await self.optimism_client.connect()
        if connected:
            logger.info("Connected to Optimism testnet")
        else:
            logger.warning("Failed to connect to Optimism, running in mock mode")
        
        self.running = True
        
        # Start role-specific behavior
        if self.role == "coordinator":
            await self._run_coordinator()
        else:
            await self._run_participant()
    
    async def connect_to_peer(self, peer_address: str):
        """Connect to another peer"""
        success = await self.p2p_node.connect_to_peer(peer_address)
        if success:
            logger.info(f"Connected to peer: {peer_address}")
        else:
            logger.error(f"Failed to connect to peer: {peer_address}")
        return success
    
    async def _run_coordinator(self):
        """Run as coordinator node"""
        logger.info("Running as coordinator - will initiate mint intents")
        
        # Wait for participants to connect
        await asyncio.sleep(5)
        
        # Create multiple mint intents to demonstrate coordination
        mint_tasks = []
        for token_id in range(1, 4):  # Mint tokens 1, 2, 3
            task = asyncio.create_task(
                self._create_mint_intent_with_delay(token_id, delay=token_id * 2)
            )
            mint_tasks.append(task)
        
        # Wait for all mint intents to complete
        await asyncio.gather(*mint_tasks)
        
        # Keep running to handle coordination
        while self.running:
            await asyncio.sleep(1)
    
    async def _run_participant(self):
        """Run as participant node"""
        logger.info("Running as participant - will respond to coordination")
        
        # Wait a bit then create some competing intents
        await asyncio.sleep(10)
        
        # Create competing mint intent
        await self._create_mint_intent_with_delay(2, priority=7)  # Higher priority
        
        # Keep running to participate in coordination
        while self.running:
            await asyncio.sleep(1)
    
    async def _create_mint_intent_with_delay(self, token_id: int, delay: int = 0, priority: int = 5):
        """Create a mint intent with optional delay"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        logger.info(f"Creating mint intent for token {token_id} with priority {priority}")
        
        intent_id = await self.coordinator.create_mint_intent(
            nft_contract=self.demo_nft_contract,
            token_id=token_id,
            priority=priority
        )
        
        logger.info(f"Created mint intent {intent_id}")
        
        # Monitor intent status
        await self._monitor_intent(intent_id)
    
    async def _monitor_intent(self, intent_id: str):
        """Monitor the status of an intent"""
        for _ in range(30):  # Monitor for 30 seconds
            if intent_id in self.coordinator.intents:
                intent = self.coordinator.intents[intent_id]
                logger.info(f"Intent {intent_id} status: {intent.status}")
                
                if intent.status in ["confirmed", "failed", "executed_by_peer"]:
                    break
            
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the demo"""
        logger.info("Stopping NFT Mint Demo")
        self.running = False
        await self.p2p_node.stop()


async def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="NFT Mint Intent Demo")
    parser.add_argument("--port", type=int, default=4001, help="P2P listen port")
    parser.add_argument("--role", choices=["coordinator", "participant"], default="coordinator", help="Node role")
    parser.add_argument("--connect", type=str, help="Peer address to connect to")
    
    args = parser.parse_args()
    
    # Create and start demo
    demo = NFTMintDemo(args.port, args.role)
    
    try:
        # Start the demo
        start_task = asyncio.create_task(demo.start())
        
        # If connecting to peer, do it after startup
        if args.connect:
            await asyncio.sleep(2)  # Wait for startup
            await demo.connect_to_peer(args.connect)
        
        # Wait for demo to complete
        await start_task
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    finally:
        await demo.stop()


if __name__ == "__main__":
    asyncio.run(main())
