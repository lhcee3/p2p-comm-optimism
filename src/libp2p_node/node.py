"""
py-libp2p node implementation for Optimism integration
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
import json

# Note: These imports will need actual libp2p implementation
# For now, we'll create a mock structure that follows libp2p patterns
from config.optimism_config import P2PConfig
from src.protocols import (
    IntentSharingProtocol,
    VotingProtocol,
    GameSyncProtocol,
    GossipProtocol
)


logger = logging.getLogger(__name__)


@dataclass
class PeerInfo:
    """Information about a connected peer"""
    peer_id: str
    addresses: List[str]
    protocols: List[str]
    connected_at: float


class MockStream:
    """Mock stream implementation for testing"""
    
    def __init__(self, peer_id: str):
        self.peer_id = peer_id
        self.closed = False
    
    async def write(self, data: bytes):
        """Write data to stream"""
        if self.closed:
            raise Exception("Stream is closed")
        # In real implementation, this would send over network
        logger.debug(f"Sending {len(data)} bytes to {self.peer_id}")
    
    async def read(self, n: int = -1) -> bytes:
        """Read data from stream"""
        if self.closed:
            raise Exception("Stream is closed")
        # In real implementation, this would read from network
        return b""
    
    def close(self):
        """Close the stream"""
        self.closed = True


class LibP2PNode:
    """Main libp2p node for Optimism integration"""
    
    def __init__(self, config: Optional[P2PConfig] = None):
        self.config = config or P2PConfig()
        self.peer_id: Optional[str] = None
        self.listen_addresses: List[str] = []
        self.connected_peers: Dict[str, PeerInfo] = {}
        self.protocols: Dict[str, Any] = {}
        
        # Protocol handlers
        self.intent_protocol = IntentSharingProtocol()
        self.voting_protocol = VotingProtocol()
        self.game_protocol = GameSyncProtocol()
        self.gossip_protocol = GossipProtocol()
        
        # Register protocols
        self.protocols[self.intent_protocol.protocol_id] = self.intent_protocol
        self.protocols[self.voting_protocol.protocol_id] = self.voting_protocol
        self.protocols[self.game_protocol.protocol_id] = self.game_protocol
        self.protocols[self.gossip_protocol.protocol_id] = self.gossip_protocol
        
        # Event callbacks
        self.peer_connect_callbacks: List[Callable] = []
        self.peer_disconnect_callbacks: List[Callable] = []
        
        self.running = False
    
    async def start(self, listen_port: int = 0) -> str:
        """Start the libp2p node"""
        try:
            # Generate peer ID (in real implementation, this would be cryptographic)
            import hashlib
            import time
            self.peer_id = hashlib.sha256(f"node_{listen_port}_{time.time()}".encode()).hexdigest()[:16]
            
            # Set listen addresses
            self.listen_addresses = [f"/ip4/127.0.0.1/tcp/{listen_port}/p2p/{self.peer_id}"]
            
            self.running = True
            logger.info(f"LibP2P node started with peer ID: {self.peer_id}")
            logger.info(f"Listening on: {self.listen_addresses}")
            
            return self.peer_id
            
        except Exception as e:
            logger.error(f"Failed to start node: {e}")
            raise
    
    async def stop(self):
        """Stop the libp2p node"""
        self.running = False
        
        # Close all connections
        for peer_id in list(self.connected_peers.keys()):
            await self.disconnect_peer(peer_id)
        
        logger.info("LibP2P node stopped")
    
    async def connect_to_peer(self, peer_address: str) -> bool:
        """Connect to a peer using their multiaddr"""
        try:
            # Parse peer address (format: /ip4/127.0.0.1/tcp/4001/p2p/QmPeerID)
            parts = peer_address.split('/')
            if len(parts) < 6:
                raise ValueError("Invalid peer address format")
            
            peer_id = parts[-1]
            host = parts[2]
            port = int(parts[4])
            
            # In real implementation, establish actual connection
            peer_info = PeerInfo(
                peer_id=peer_id,
                addresses=[peer_address],
                protocols=list(self.protocols.keys()),
                connected_at=asyncio.get_event_loop().time()
            )
            
            self.connected_peers[peer_id] = peer_info
            
            # Notify callbacks
            for callback in self.peer_connect_callbacks:
                await callback(peer_id, peer_info)
            
            logger.info(f"Connected to peer: {peer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_address}: {e}")
            return False
    
    async def disconnect_peer(self, peer_id: str):
        """Disconnect from a peer"""
        if peer_id in self.connected_peers:
            peer_info = self.connected_peers.pop(peer_id)
            
            # Notify callbacks
            for callback in self.peer_disconnect_callbacks:
                await callback(peer_id, peer_info)
            
            logger.info(f"Disconnected from peer: {peer_id}")
    
    async def send_message_to_peer(
        self, 
        peer_id: str, 
        protocol_id: str, 
        message: Dict[str, Any]
    ) -> bool:
        """Send a message to a specific peer using a protocol"""
        if peer_id not in self.connected_peers:
            logger.warning(f"Peer {peer_id} not connected")
            return False
        
        if protocol_id not in self.protocols:
            logger.warning(f"Protocol {protocol_id} not registered")
            return False
        
        try:
            # Create mock stream for the peer
            stream = MockStream(peer_id)
            protocol = self.protocols[protocol_id]
            
            await protocol.send_message(stream, message)
            logger.debug(f"Sent message to {peer_id} via {protocol_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to {peer_id}: {e}")
            return False
    
    async def broadcast_message(
        self, 
        protocol_id: str, 
        message: Dict[str, Any],
        exclude_peers: Optional[List[str]] = None
    ) -> int:
        """Broadcast a message to all connected peers"""
        exclude_peers = exclude_peers or []
        sent_count = 0
        
        for peer_id in self.connected_peers:
            if peer_id not in exclude_peers:
                success = await self.send_message_to_peer(peer_id, protocol_id, message)
                if success:
                    sent_count += 1
        
        logger.debug(f"Broadcast message to {sent_count} peers via {protocol_id}")
        return sent_count
    
    def get_connected_peers(self) -> List[str]:
        """Get list of connected peer IDs"""
        return list(self.connected_peers.keys())
    
    def get_peer_info(self, peer_id: str) -> Optional[PeerInfo]:
        """Get information about a connected peer"""
        return self.connected_peers.get(peer_id)
    
    def on_peer_connect(self, callback: Callable):
        """Register callback for peer connection events"""
        self.peer_connect_callbacks.append(callback)
    
    def on_peer_disconnect(self, callback: Callable):
        """Register callback for peer disconnection events"""
        self.peer_disconnect_callbacks.append(callback)
    
    # Protocol-specific convenience methods
    
    async def share_intent(
        self, 
        intent_id: str,
        contract_address: str,
        function_call: str,
        gas_estimate: int,
        target_peers: Optional[List[str]] = None
    ) -> int:
        """Share a transaction intent with peers"""
        message = {
            "msg_type": "intent",
            "intent_id": intent_id,
            "sender_id": self.peer_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": {
                "contract": contract_address,
                "function": function_call,
                "gas": gas_estimate
            },
            "target_contract": contract_address,
            "function_call": function_call,
            "gas_estimate": gas_estimate
        }
        
        if target_peers:
            sent_count = 0
            for peer_id in target_peers:
                success = await self.send_message_to_peer(
                    peer_id, 
                    self.intent_protocol.protocol_id, 
                    message
                )
                if success:
                    sent_count += 1
            return sent_count
        else:
            return await self.broadcast_message(self.intent_protocol.protocol_id, message)
    
    async def submit_vote(
        self,
        proposal_id: str,
        vote: bool,
        voting_power: int,
        proof: str = ""
    ) -> int:
        """Submit a vote and broadcast to peers"""
        message = {
            "msg_type": "vote",
            "proposal_id": proposal_id,
            "sender_id": self.peer_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": {
                "proposal": proposal_id,
                "decision": vote,
                "power": voting_power
            },
            "vote": vote,
            "voting_power": voting_power,
            "proof": proof
        }
        
        return await self.broadcast_message(self.voting_protocol.protocol_id, message)
    
    async def broadcast_game_move(
        self,
        game_id: str,
        move_data: Dict[str, Any],
        sequence_number: int,
        state_hash: str = ""
    ) -> int:
        """Broadcast a game move to all peers"""
        message = {
            "msg_type": "game_move",
            "game_id": game_id,
            "sender_id": self.peer_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": move_data,
            "move_data": move_data,
            "sequence_number": sequence_number,
            "state_hash": state_hash
        }
        
        return await self.broadcast_message(self.game_protocol.protocol_id, message)
    
    async def gossip(self, topic: str, data: Dict[str, Any]) -> int:
        """Gossip a message on a topic"""
        message_id = f"{self.peer_id}_{topic}_{hash(str(data))}"
        
        message = {
            "msg_type": "gossip",
            "topic": topic,
            "sender_id": self.peer_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": data,
            "message_id": message_id
        }
        
        return await self.broadcast_message(self.gossip_protocol.protocol_id, message)
    
    def get_protocol(self, protocol_id: str) -> Optional[Any]:
        """Get a protocol handler by ID"""
        return self.protocols.get(protocol_id)
    
    # Simulation methods for testing
    
    async def simulate_message_received(
        self, 
        from_peer_id: str, 
        protocol_id: str, 
        message: Dict[str, Any]
    ):
        """Simulate receiving a message (for testing)"""
        if protocol_id in self.protocols:
            protocol = self.protocols[protocol_id]
            stream = MockStream(from_peer_id)
            await protocol.handle_message(json.dumps(message).encode(), stream)
