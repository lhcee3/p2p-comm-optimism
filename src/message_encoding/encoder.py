"""
Message encoding utilities for py-libp2p + Optimism integration
"""
import json
import rlp
from typing import Any, Dict, List, Union
from dataclasses import dataclass, asdict
from eth_utils import to_bytes, to_hex
import msgpack


@dataclass
class P2PMessage:
    """Base message structure for P2P communication"""
    msg_type: str
    sender_id: str
    timestamp: int
    data: Dict[str, Any]
    signature: str = ""


@dataclass
class IntentMessage:
    """Message for sharing transaction intents"""
    msg_type: str
    sender_id: str
    timestamp: int
    data: Dict[str, Any]
    intent_id: str
    target_contract: str
    function_call: str
    gas_estimate: int
    signature: str = ""
    priority: int = 0


@dataclass
class VoteMessage:
    """Message for DAO voting coordination"""
    msg_type: str
    sender_id: str
    timestamp: int
    data: Dict[str, Any]
    proposal_id: str
    vote: bool  # True for yes, False for no
    voting_power: int
    signature: str = ""
    proof: str = ""


@dataclass
class GameMoveMessage:
    """Message for game state coordination"""
    msg_type: str
    sender_id: str
    timestamp: int
    data: Dict[str, Any]
    game_id: str
    move_data: Dict[str, Any]
    sequence_number: int
    signature: str = ""
    state_hash: str = ""


class MessageEncoder:
    """Handles encoding/decoding of messages for P2P transmission"""
    
    @staticmethod
    def encode_json(message: P2PMessage) -> bytes:
        """Encode message as JSON bytes"""
        return json.dumps(asdict(message)).encode('utf-8')
    
    @staticmethod
    def decode_json(data: bytes) -> Dict[str, Any]:
        """Decode JSON bytes to dictionary"""
        return json.loads(data.decode('utf-8'))
    
    @staticmethod
    def encode_msgpack(message: P2PMessage) -> bytes:
        """Encode message using MessagePack (more efficient)"""
        return msgpack.packb(asdict(message))
    
    @staticmethod
    def decode_msgpack(data: bytes) -> Dict[str, Any]:
        """Decode MessagePack bytes to dictionary"""
        return msgpack.unpackb(data, raw=False)
    
    @staticmethod
    def encode_rlp(data: List[Union[str, int, bytes]]) -> bytes:
        """Encode data using RLP (Ethereum's encoding)"""
        # Convert strings to bytes for RLP
        rlp_data = []
        for item in data:
            if isinstance(item, str):
                rlp_data.append(item.encode('utf-8'))
            elif isinstance(item, int):
                rlp_data.append(item.to_bytes((item.bit_length() + 7) // 8, 'big'))
            else:
                rlp_data.append(item)
        return rlp.encode(rlp_data)
    
    @staticmethod
    def decode_rlp(data: bytes) -> List[bytes]:
        """Decode RLP bytes to list"""
        return rlp.decode(data)


class MessageFactory:
    """Factory for creating typed messages"""
    
    @staticmethod
    def create_intent_message(
        sender_id: str,
        intent_id: str,
        target_contract: str,
        function_call: str,
        gas_estimate: int,
        timestamp: int,
        priority: int = 0
    ) -> IntentMessage:
        """Create an intent sharing message"""
        return IntentMessage(
            msg_type="intent",
            sender_id=sender_id,
            timestamp=timestamp,
            data={
                "contract": target_contract,
                "function": function_call,
                "gas": gas_estimate
            },
            intent_id=intent_id,
            target_contract=target_contract,
            function_call=function_call,
            gas_estimate=gas_estimate,
            priority=priority
        )
    
    @staticmethod
    def create_vote_message(
        sender_id: str,
        proposal_id: str,
        vote: bool,
        voting_power: int,
        timestamp: int,
        proof: str = ""
    ) -> VoteMessage:
        """Create a voting message"""
        return VoteMessage(
            msg_type="vote",
            sender_id=sender_id,
            timestamp=timestamp,
            data={
                "proposal": proposal_id,
                "decision": vote,
                "power": voting_power
            },
            proposal_id=proposal_id,
            vote=vote,
            voting_power=voting_power,
            proof=proof
        )
    
    @staticmethod
    def create_game_move_message(
        sender_id: str,
        game_id: str,
        move_data: Dict[str, Any],
        sequence_number: int,
        timestamp: int,
        state_hash: str = ""
    ) -> GameMoveMessage:
        """Create a game move message"""
        return GameMoveMessage(
            msg_type="game_move",
            sender_id=sender_id,
            timestamp=timestamp,
            data=move_data,
            game_id=game_id,
            move_data=move_data,
            sequence_number=sequence_number,
            state_hash=state_hash
        )


class MessageValidator:
    """Validates message integrity and format"""
    
    @staticmethod
    def validate_message(message_dict: Dict[str, Any]) -> bool:
        """Validate basic message structure"""
        required_fields = ["msg_type", "sender_id", "timestamp", "data"]
        return all(field in message_dict for field in required_fields)
    
    @staticmethod
    def validate_intent_message(message_dict: Dict[str, Any]) -> bool:
        """Validate intent message specific fields"""
        if not MessageValidator.validate_message(message_dict):
            return False
        
        required_intent_fields = ["intent_id", "target_contract", "function_call", "gas_estimate"]
        return all(field in message_dict for field in required_intent_fields)
    
    @staticmethod
    def validate_vote_message(message_dict: Dict[str, Any]) -> bool:
        """Validate vote message specific fields"""
        if not MessageValidator.validate_message(message_dict):
            return False
        
        required_vote_fields = ["proposal_id", "vote", "voting_power"]
        return all(field in message_dict for field in required_vote_fields)
