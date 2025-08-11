"""
Custom libp2p protocols for Optimism integration
"""
from typing import Dict, Any, Callable, Optional
import asyncio
import json
import logging

from src.message_encoding import MessageEncoder, MessageValidator


logger = logging.getLogger(__name__)


class BaseProtocol:
    """Base class for libp2p protocols"""
    
    def __init__(self, protocol_id: str):
        self.protocol_id = protocol_id
        self.message_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, message_type: str, handler: Callable):
        """Register a message handler for a specific message type"""
        self.message_handlers[message_type] = handler
    
    async def handle_message(self, message: bytes, stream) -> None:
        """Handle incoming message"""
        try:
            # Decode message
            message_dict = MessageEncoder.decode_json(message)
            
            # Validate message structure
            if not MessageValidator.validate_message(message_dict):
                logger.warning(f"Invalid message structure: {message_dict}")
                return
            
            # Get message type and handler
            msg_type = message_dict.get("msg_type")
            handler = self.message_handlers.get(msg_type)
            
            if handler:
                await handler(message_dict, stream)
            else:
                logger.warning(f"No handler for message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def send_message(self, stream, message_dict: Dict[str, Any]) -> None:
        """Send a message through the stream"""
        try:
            message_bytes = MessageEncoder.encode_json(message_dict)
            await stream.write(message_bytes)
        except Exception as e:
            logger.error(f"Error sending message: {e}")


class IntentSharingProtocol(BaseProtocol):
    """Protocol for sharing transaction intents between peers"""
    
    def __init__(self):
        super().__init__("/op/intent/1.0.0")
        self.intent_cache: Dict[str, Dict[str, Any]] = {}
        self.intent_callbacks: Dict[str, Callable] = {}
    
    def register_intent_callback(self, intent_type: str, callback: Callable):
        """Register callback for specific intent types"""
        self.intent_callbacks[intent_type] = callback
    
    async def share_intent(
        self, 
        stream, 
        intent_id: str, 
        contract_address: str,
        function_call: str,
        gas_estimate: int,
        sender_id: str
    ):
        """Share a transaction intent with peers"""
        intent_message = {
            "msg_type": "intent",
            "intent_id": intent_id,
            "sender_id": sender_id,
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
        
        await self.send_message(stream, intent_message)
        logger.info(f"Shared intent {intent_id} with peer")
    
    async def handle_intent_message(self, message_dict: Dict[str, Any], stream):
        """Handle incoming intent message"""
        intent_id = message_dict.get("intent_id")
        
        # Cache the intent
        self.intent_cache[intent_id] = message_dict
        
        # Call registered callback if available
        intent_type = message_dict["data"].get("function", "").split("(")[0]
        callback = self.intent_callbacks.get(intent_type)
        
        if callback:
            await callback(message_dict, stream)
        
        logger.info(f"Received intent {intent_id} from {message_dict['sender_id']}")


class VotingProtocol(BaseProtocol):
    """Protocol for DAO voting coordination"""
    
    def __init__(self):
        super().__init__("/op/vote/1.0.0")
        self.votes: Dict[str, Dict[str, Any]] = {}  # proposal_id -> votes
        self.vote_callbacks: Dict[str, Callable] = {}
    
    def register_vote_callback(self, proposal_id: str, callback: Callable):
        """Register callback for vote on specific proposal"""
        self.vote_callbacks[proposal_id] = callback
    
    async def submit_vote(
        self,
        stream,
        proposal_id: str,
        vote: bool,
        voting_power: int,
        sender_id: str,
        proof: str = ""
    ):
        """Submit a vote for a proposal"""
        vote_message = {
            "msg_type": "vote",
            "proposal_id": proposal_id,
            "sender_id": sender_id,
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
        
        await self.send_message(stream, vote_message)
        logger.info(f"Submitted vote for proposal {proposal_id}")
    
    async def handle_vote_message(self, message_dict: Dict[str, Any], stream):
        """Handle incoming vote message"""
        proposal_id = message_dict.get("proposal_id")
        sender_id = message_dict.get("sender_id")
        
        # Store vote
        if proposal_id not in self.votes:
            self.votes[proposal_id] = {}
        
        self.votes[proposal_id][sender_id] = message_dict
        
        # Call registered callback
        callback = self.vote_callbacks.get(proposal_id)
        if callback:
            await callback(message_dict, stream)
        
        logger.info(f"Received vote for proposal {proposal_id} from {sender_id}")
    
    def get_vote_tally(self, proposal_id: str) -> Dict[str, int]:
        """Get current vote tally for a proposal"""
        if proposal_id not in self.votes:
            return {"yes": 0, "no": 0, "total_power": 0}
        
        yes_votes = 0
        no_votes = 0
        total_power = 0
        
        for vote_data in self.votes[proposal_id].values():
            power = vote_data.get("voting_power", 0)
            total_power += power
            
            if vote_data.get("vote", False):
                yes_votes += power
            else:
                no_votes += power
        
        return {
            "yes": yes_votes,
            "no": no_votes,
            "total_power": total_power
        }


class GameSyncProtocol(BaseProtocol):
    """Protocol for game state synchronization"""
    
    def __init__(self):
        super().__init__("/op/game/1.0.0")
        self.game_states: Dict[str, Dict[str, Any]] = {}
        self.move_callbacks: Dict[str, Callable] = {}
    
    def register_move_callback(self, game_id: str, callback: Callable):
        """Register callback for moves in specific game"""
        self.move_callbacks[game_id] = callback
    
    async def broadcast_move(
        self,
        stream,
        game_id: str,
        move_data: Dict[str, Any],
        sequence_number: int,
        sender_id: str,
        state_hash: str = ""
    ):
        """Broadcast a game move to peers"""
        move_message = {
            "msg_type": "game_move",
            "game_id": game_id,
            "sender_id": sender_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": move_data,
            "move_data": move_data,
            "sequence_number": sequence_number,
            "state_hash": state_hash
        }
        
        await self.send_message(stream, move_message)
        logger.info(f"Broadcast move for game {game_id}, sequence {sequence_number}")
    
    async def handle_move_message(self, message_dict: Dict[str, Any], stream):
        """Handle incoming game move message"""
        game_id = message_dict.get("game_id")
        sequence_number = message_dict.get("sequence_number")
        
        # Update game state
        if game_id not in self.game_states:
            self.game_states[game_id] = {"moves": [], "latest_sequence": -1}
        
        # Check if this is the next expected move
        expected_sequence = self.game_states[game_id]["latest_sequence"] + 1
        if sequence_number == expected_sequence:
            self.game_states[game_id]["moves"].append(message_dict)
            self.game_states[game_id]["latest_sequence"] = sequence_number
            
            # Call registered callback
            callback = self.move_callbacks.get(game_id)
            if callback:
                await callback(message_dict, stream)
                
            logger.info(f"Applied move for game {game_id}, sequence {sequence_number}")
        else:
            logger.warning(f"Out of order move for game {game_id}: expected {expected_sequence}, got {sequence_number}")
    
    def get_game_state(self, game_id: str) -> Optional[Dict[str, Any]]:
        """Get current game state"""
        return self.game_states.get(game_id)


class GossipProtocol(BaseProtocol):
    """General purpose gossip protocol for broadcasting messages"""
    
    def __init__(self):
        super().__init__("/op/gossip/1.0.0")
        self.seen_messages: set = set()
        self.gossip_callbacks: Dict[str, Callable] = {}
    
    def register_gossip_callback(self, topic: str, callback: Callable):
        """Register callback for specific gossip topics"""
        self.gossip_callbacks[topic] = callback
    
    async def gossip_message(
        self,
        stream,
        topic: str,
        data: Dict[str, Any],
        sender_id: str
    ):
        """Gossip a message to peers"""
        message_id = f"{sender_id}_{topic}_{hash(str(data))}"
        
        if message_id in self.seen_messages:
            return  # Already seen this message
        
        self.seen_messages.add(message_id)
        
        gossip_message = {
            "msg_type": "gossip",
            "topic": topic,
            "sender_id": sender_id,
            "timestamp": int(asyncio.get_event_loop().time()),
            "data": data,
            "message_id": message_id
        }
        
        await self.send_message(stream, gossip_message)
        logger.info(f"Gossiped message on topic {topic}")
    
    async def handle_gossip_message(self, message_dict: Dict[str, Any], stream):
        """Handle incoming gossip message"""
        message_id = message_dict.get("message_id")
        topic = message_dict.get("topic")
        
        if message_id in self.seen_messages:
            return  # Already processed
        
        self.seen_messages.add(message_id)
        
        # Call registered callback
        callback = self.gossip_callbacks.get(topic)
        if callback:
            await callback(message_dict, stream)
        
        logger.info(f"Received gossip message on topic {topic}")
        
        # Re-gossip to other peers (flood routing)
        # Note: In a real implementation, you'd want more sophisticated routing
