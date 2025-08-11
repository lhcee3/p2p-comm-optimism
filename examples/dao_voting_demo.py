"""
DAO Voting Demo - P2P coordination of DAO votes before onchain finalization

This demo shows how peers can collect and coordinate DAO votes offchain
before submitting the final result to Optimism L2.

Usage:
    # Terminal 1 (Proposer)
    python examples/dao_voting_demo.py --port 5001 --role proposer
    
    # Terminal 2 (Voter 1)
    python examples/dao_voting_demo.py --port 5002 --role voter --connect /ip4/127.0.0.1/tcp/5001/p2p/<PEER_ID>
    
    # Terminal 3 (Voter 2) 
    python examples/dao_voting_demo.py --port 5003 --role voter --connect /ip4/127.0.0.1/tcp/5001/p2p/<PEER_ID>
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
from src.dapp_logic import DAOVotingCoordinator
from config.optimism_config import OptimismConfig, P2PConfig


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DAOVotingDemo:
    """Demo application for DAO voting coordination"""
    
    def __init__(self, port: int, role: str):
        self.port = port
        self.role = role
        
        # Configure Optimism client
        self.optimism_config = OptimismConfig.for_testnet()
        self.optimism_client = OptimismClient(self.optimism_config)
        
        # Configure P2P node
        self.p2p_config = P2PConfig()
        self.p2p_node = LibP2PNode(self.p2p_config)
        
        # Initialize coordinator
        self.coordinator = DAOVotingCoordinator(self.p2p_node, self.optimism_client)
        
        # Demo state
        self.running = False
        self.voting_power = 10  # Each node has 10 voting power
    
    async def start(self):
        """Start the demo"""
        logger.info(f"Starting DAO Voting Demo as {self.role} on port {self.port}")
        
        # Start P2P node
        peer_id = await self.p2p_node.start(self.port)
        logger.info(f"P2P Node started with ID: {peer_id}")
        
        # Connect to Optimism (mock for demo)
        connected = await self.optimism_client.connect()
        if connected:
            logger.info("Connected to Optimism testnet")
        else:
            logger.warning("Failed to connect to Optimism, running in mock mode")
        
        self.running = True
        
        # Start role-specific behavior
        if self.role == "proposer":
            await self._run_proposer()
        else:
            await self._run_voter()
    
    async def connect_to_peer(self, peer_address: str):
        """Connect to another peer"""
        success = await self.p2p_node.connect_to_peer(peer_address)
        if success:
            logger.info(f"Connected to peer: {peer_address}")
        else:
            logger.error(f"Failed to connect to peer: {peer_address}")
        return success
    
    async def _run_proposer(self):
        """Run as proposal creator"""
        logger.info("Running as proposer - will create proposals")
        
        # Wait for voters to connect
        await asyncio.sleep(5)
        
        # Create sample proposals
        proposals = [
            {
                "title": "Increase Treasury Allocation",
                "description": "Allocate 100 ETH from treasury to development fund",
                "action": "transfer",
                "amount": "100 ETH",
                "recipient": "0x742d35Cc6635C0532925a3b8D6Cf2EE1C8d62ba"
            },
            {
                "title": "Update Governance Parameters",
                "description": "Change minimum proposal threshold to 1000 tokens",
                "action": "update_param",
                "parameter": "min_proposal_threshold",
                "value": 1000
            }
        ]
        
        for i, proposal_data in enumerate(proposals):
            logger.info(f"Creating proposal {i+1}: {proposal_data['title']}")
            
            proposal_id = await self.coordinator.create_proposal(
                proposal_data=proposal_data,
                voting_duration=60  # 1 minute for demo
            )
            
            logger.info(f"Created proposal {proposal_id}")
            
            # Wait before next proposal
            await asyncio.sleep(10)
        
        # Monitor proposals
        await self._monitor_proposals()
    
    async def _run_voter(self):
        """Run as voter"""
        logger.info("Running as voter - will respond to proposals")
        
        # Wait for proposals to arrive
        await asyncio.sleep(15)
        
        # Vote on any active proposals
        await self._vote_on_proposals()
        
        # Keep running to vote on new proposals
        while self.running:
            await asyncio.sleep(10)
            await self._vote_on_proposals()
    
    async def _vote_on_proposals(self):
        """Vote on active proposals"""
        for proposal_id, proposal in self.coordinator.proposals.items():
            if proposal["status"] == "active":
                # Haven't voted yet
                if self.p2p_node.peer_id not in proposal["votes"]:
                    # Simple voting logic based on proposal type
                    vote = self._decide_vote(proposal)
                    
                    logger.info(f"Voting {vote} on proposal {proposal_id}: {proposal['data']['title']}")
                    
                    await self.coordinator.submit_vote(
                        proposal_id=proposal_id,
                        vote=vote,
                        voting_power=self.voting_power
                    )
    
    def _decide_vote(self, proposal: dict) -> bool:
        """Simple voting logic (in real app, this would be user input)"""
        data = proposal["data"]
        
        # Vote based on proposal type and node characteristics
        if "treasury" in data.get("title", "").lower():
            # Conservative approach to treasury proposals
            return self.port % 2 == 0  # Even ports vote yes, odd vote no
        
        if "governance" in data.get("title", "").lower():
            # More liberal on governance changes
            return True
        
        # Default to yes
        return True
    
    async def _monitor_proposals(self):
        """Monitor proposal status"""
        while self.running:
            for proposal_id, proposal in self.coordinator.proposals.items():
                if proposal["status"] in ["passed", "rejected"]:
                    result = proposal.get("result", {})
                    logger.info(
                        f"Proposal {proposal_id} {proposal['status'].upper()}: "
                        f"Yes: {result.get('yes_votes', 0)}, "
                        f"No: {result.get('no_votes', 0)}"
                    )
            
            await asyncio.sleep(5)
    
    async def stop(self):
        """Stop the demo"""
        logger.info("Stopping DAO Voting Demo")
        self.running = False
        await self.p2p_node.stop()


async def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="DAO Voting Demo")
    parser.add_argument("--port", type=int, default=5001, help="P2P listen port")
    parser.add_argument("--role", choices=["proposer", "voter"], default="proposer", help="Node role")
    parser.add_argument("--connect", type=str, help="Peer address to connect to")
    
    args = parser.parse_args()
    
    # Create and start demo
    demo = DAOVotingDemo(args.port, args.role)
    
    try:
        # Start the demo
        start_task = asyncio.create_task(demo.start())
        
        # If connecting to peer, do it after startup
        if args.connect:
            await asyncio.sleep(2)
            await demo.connect_to_peer(args.connect)
        
        # Wait for demo to complete
        await start_task
        
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    finally:
        await demo.stop()


if __name__ == "__main__":
    asyncio.run(main())
