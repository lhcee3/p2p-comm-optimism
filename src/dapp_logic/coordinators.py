"""
dApp logic implementations for various use cases
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
import json
import hashlib
import time

from src.libp2p_node import LibP2PNode
from src.optimism_client import OptimismClient
from config.optimism_config import OptimismConfig


logger = logging.getLogger(__name__)


@dataclass
class IntentData:
    """Data structure for transaction intents"""
    intent_id: str
    sender_id: str
    contract_address: str
    function_call: str
    gas_estimate: int
    priority: int
    timestamp: float
    status: str = "pending"  # pending, coordinating, submitted, confirmed


class NFTMintCoordinator:
    """Coordinates NFT minting intents across peers to avoid gas wars"""
    
    def __init__(self, p2p_node: LibP2PNode, optimism_client: OptimismClient):
        self.p2p_node = p2p_node
        self.optimism_client = optimism_client
        self.intents: Dict[str, IntentData] = {}
        self.coordination_rounds: Dict[str, Dict] = {}
        
        # Register protocol handlers
        intent_protocol = self.p2p_node.get_protocol("/op/intent/1.0.0")
        if intent_protocol:
            intent_protocol.register_handler("intent", self._handle_intent_message)
            intent_protocol.register_handler("coordination", self._handle_coordination_message)
    
    async def create_mint_intent(
        self, 
        nft_contract: str, 
        token_id: int, 
        priority: int = 5
    ) -> str:
        """Create and share an NFT mint intent"""
        intent_id = f"mint_{self.p2p_node.peer_id}_{int(time.time())}"
        function_call = f"mint({token_id})"
        
        # Estimate gas for the mint
        gas_estimate = await self.optimism_client.estimate_gas(
            nft_contract,
            b'',  # In real implementation, encode the mint function call
            0
        )
        
        intent = IntentData(
            intent_id=intent_id,
            sender_id=self.p2p_node.peer_id,
            contract_address=nft_contract,
            function_call=function_call,
            gas_estimate=gas_estimate,
            priority=priority,
            timestamp=time.time()
        )
        
        self.intents[intent_id] = intent
        
        # Share intent with peers
        await self.p2p_node.share_intent(
            intent_id=intent_id,
            contract_address=nft_contract,
            function_call=function_call,
            gas_estimate=gas_estimate
        )
        
        logger.info(f"Created mint intent {intent_id} for token {token_id}")
        return intent_id
    
    async def _handle_intent_message(self, message: Dict[str, Any], stream):
        """Handle incoming intent message"""
        intent_id = message.get("intent_id")
        sender_id = message.get("sender_id")
        
        # Create intent data from message
        intent = IntentData(
            intent_id=intent_id,
            sender_id=sender_id,
            contract_address=message.get("target_contract"),
            function_call=message.get("function_call"),
            gas_estimate=message.get("gas_estimate"),
            priority=message.get("priority", 5),
            timestamp=message.get("timestamp")
        )
        
        self.intents[intent_id] = intent
        
        # Start coordination if this is a conflicting intent
        await self._coordinate_intents(intent.contract_address)
        
        logger.info(f"Received intent {intent_id} from {sender_id}")
    
    async def _coordinate_intents(self, contract_address: str):
        """Coordinate conflicting intents for the same contract"""
        # Find all pending intents for this contract
        contract_intents = [
            intent for intent in self.intents.values()
            if intent.contract_address == contract_address and intent.status == "pending"
        ]
        
        if len(contract_intents) <= 1:
            return  # No coordination needed
        
        # Sort by priority and timestamp
        sorted_intents = sorted(
            contract_intents,
            key=lambda x: (x.priority, x.timestamp),
            reverse=True
        )
        
        # Create coordination round
        round_id = f"coord_{contract_address}_{int(time.time())}"
        self.coordination_rounds[round_id] = {
            "contract": contract_address,
            "intents": [intent.intent_id for intent in sorted_intents],
            "votes": {},
            "status": "voting"
        }
        
        # Propose the highest priority intent
        winner_intent = sorted_intents[0]
        coordination_message = {
            "msg_type": "coordination",
            "round_id": round_id,
            "proposed_intent": winner_intent.intent_id,
            "contract": contract_address,
            "sender_id": self.p2p_node.peer_id,
            "timestamp": int(time.time())
        }
        
        await self.p2p_node.broadcast_message(
            "/op/intent/1.0.0",
            coordination_message
        )
        
        logger.info(f"Started coordination round {round_id} for contract {contract_address}")
    
    async def _handle_coordination_message(self, message: Dict[str, Any], stream):
        """Handle coordination round message"""
        round_id = message.get("round_id")
        proposed_intent = message.get("proposed_intent")
        sender_id = message.get("sender_id")
        
        if round_id not in self.coordination_rounds:
            # New coordination round
            self.coordination_rounds[round_id] = {
                "contract": message.get("contract"),
                "proposed_intent": proposed_intent,
                "votes": {},
                "status": "voting"
            }
        
        # Vote on the proposal (simple majority)
        my_vote = True  # For now, always vote yes
        self.coordination_rounds[round_id]["votes"][self.p2p_node.peer_id] = my_vote
        
        # Check if we have enough votes to decide
        total_peers = len(self.p2p_node.get_connected_peers()) + 1  # +1 for self
        votes = self.coordination_rounds[round_id]["votes"]
        
        if len(votes) >= (total_peers // 2 + 1):
            # We have majority, proceed with execution
            yes_votes = sum(1 for vote in votes.values() if vote)
            
            if yes_votes > len(votes) // 2:
                # Execute the winning intent
                await self._execute_intent(proposed_intent)
                self.coordination_rounds[round_id]["status"] = "executed"
            else:
                self.coordination_rounds[round_id]["status"] = "rejected"
        
        logger.info(f"Processed coordination vote for round {round_id}")
    
    async def _execute_intent(self, intent_id: str):
        """Execute a coordinated intent on Optimism"""
        if intent_id not in self.intents:
            logger.warning(f"Intent {intent_id} not found")
            return
        
        intent = self.intents[intent_id]
        
        # Only execute our own intents
        if intent.sender_id != self.p2p_node.peer_id:
            intent.status = "executed_by_peer"
            return
        
        try:
            # Submit transaction to Optimism
            # In real implementation, properly encode the function call
            tx_hash = await self.optimism_client.send_transaction(
                intent.contract_address,
                0,  # value
                b'',  # encoded function call
                intent.gas_estimate
            )
            
            intent.status = "submitted"
            logger.info(f"Submitted intent {intent_id} to Optimism: {tx_hash}")
            
            # Wait for confirmation
            receipt = await self.optimism_client.wait_for_transaction_receipt(tx_hash)
            
            if receipt.get("status") == 1:
                intent.status = "confirmed"
                logger.info(f"Intent {intent_id} confirmed on Optimism")
            else:
                intent.status = "failed"
                logger.error(f"Intent {intent_id} failed on Optimism")
                
        except Exception as e:
            intent.status = "failed"
            logger.error(f"Failed to execute intent {intent_id}: {e}")


class DAOVotingCoordinator:
    """Coordinates DAO voting across peers before onchain finalization"""
    
    def __init__(self, p2p_node: LibP2PNode, optimism_client: OptimismClient):
        self.p2p_node = p2p_node
        self.optimism_client = optimism_client
        self.proposals: Dict[str, Dict[str, Any]] = {}
        
        # Register protocol handlers
        voting_protocol = self.p2p_node.get_protocol("/op/vote/1.0.0")
        if voting_protocol:
            voting_protocol.register_handler("vote", self._handle_vote_message)
            voting_protocol.register_handler("proposal", self._handle_proposal_message)
    
    async def create_proposal(
        self, 
        proposal_data: Dict[str, Any],
        voting_duration: int = 300  # 5 minutes
    ) -> str:
        """Create a new proposal for voting"""
        proposal_id = f"prop_{self.p2p_node.peer_id}_{int(time.time())}"
        
        proposal = {
            "proposal_id": proposal_id,
            "creator": self.p2p_node.peer_id,
            "data": proposal_data,
            "created_at": time.time(),
            "voting_ends": time.time() + voting_duration,
            "votes": {},
            "status": "active"
        }
        
        self.proposals[proposal_id] = proposal
        
        # Broadcast proposal to peers
        proposal_message = {
            "msg_type": "proposal",
            "proposal_id": proposal_id,
            "creator": self.p2p_node.peer_id,
            "data": proposal_data,
            "voting_duration": voting_duration,
            "timestamp": int(time.time())
        }
        
        await self.p2p_node.broadcast_message("/op/vote/1.0.0", proposal_message)
        
        logger.info(f"Created proposal {proposal_id}")
        return proposal_id
    
    async def submit_vote(
        self, 
        proposal_id: str, 
        vote: bool, 
        voting_power: int = 1
    ) -> bool:
        """Submit a vote for a proposal"""
        if proposal_id not in self.proposals:
            logger.warning(f"Proposal {proposal_id} not found")
            return False
        
        proposal = self.proposals[proposal_id]
        
        if time.time() > proposal["voting_ends"]:
            logger.warning(f"Voting period ended for proposal {proposal_id}")
            return False
        
        # Record vote locally
        proposal["votes"][self.p2p_node.peer_id] = {
            "vote": vote,
            "power": voting_power,
            "timestamp": time.time()
        }
        
        # Broadcast vote to peers
        await self.p2p_node.submit_vote(proposal_id, vote, voting_power)
        
        logger.info(f"Submitted vote for proposal {proposal_id}: {vote}")
        return True
    
    async def _handle_proposal_message(self, message: Dict[str, Any], stream):
        """Handle new proposal message"""
        proposal_id = message.get("proposal_id")
        creator = message.get("creator")
        data = message.get("data")
        voting_duration = message.get("voting_duration", 300)
        timestamp = message.get("timestamp")
        
        proposal = {
            "proposal_id": proposal_id,
            "creator": creator,
            "data": data,
            "created_at": timestamp,
            "voting_ends": timestamp + voting_duration,
            "votes": {},
            "status": "active"
        }
        
        self.proposals[proposal_id] = proposal
        logger.info(f"Received proposal {proposal_id} from {creator}")
    
    async def _handle_vote_message(self, message: Dict[str, Any], stream):
        """Handle vote message"""
        proposal_id = message.get("proposal_id")
        sender_id = message.get("sender_id")
        vote = message.get("vote")
        voting_power = message.get("voting_power", 1)
        
        if proposal_id not in self.proposals:
            logger.warning(f"Received vote for unknown proposal {proposal_id}")
            return
        
        proposal = self.proposals[proposal_id]
        
        # Record the vote
        proposal["votes"][sender_id] = {
            "vote": vote,
            "power": voting_power,
            "timestamp": time.time()
        }
        
        logger.info(f"Received vote from {sender_id} for proposal {proposal_id}: {vote}")
        
        # Check if voting should be finalized
        await self._check_finalization(proposal_id)
    
    async def _check_finalization(self, proposal_id: str):
        """Check if proposal should be finalized"""
        proposal = self.proposals[proposal_id]
        
        if proposal["status"] != "active":
            return
        
        # Check if voting period ended or we have enough votes
        now = time.time()
        total_peers = len(self.p2p_node.get_connected_peers()) + 1
        vote_count = len(proposal["votes"])
        
        should_finalize = (
            now > proposal["voting_ends"] or 
            vote_count >= total_peers
        )
        
        if should_finalize:
            await self._finalize_proposal(proposal_id)
    
    async def _finalize_proposal(self, proposal_id: str):
        """Finalize proposal and submit to Optimism if needed"""
        proposal = self.proposals[proposal_id]
        proposal["status"] = "finalizing"
        
        # Tally votes
        yes_votes = 0
        no_votes = 0
        total_power = 0
        
        for vote_data in proposal["votes"].values():
            power = vote_data["power"]
            total_power += power
            
            if vote_data["vote"]:
                yes_votes += power
            else:
                no_votes += power
        
        # Determine outcome
        passed = yes_votes > no_votes
        proposal["result"] = {
            "passed": passed,
            "yes_votes": yes_votes,
            "no_votes": no_votes,
            "total_power": total_power,
            "finalized_at": time.time()
        }
        
        proposal["status"] = "passed" if passed else "rejected"
        
        # If passed and we're the creator, submit to Optimism
        if passed and proposal["creator"] == self.p2p_node.peer_id:
            await self._submit_to_optimism(proposal_id)
        
        logger.info(f"Finalized proposal {proposal_id}: {'PASSED' if passed else 'REJECTED'}")
    
    async def _submit_to_optimism(self, proposal_id: str):
        """Submit finalized proposal to Optimism"""
        proposal = self.proposals[proposal_id]
        
        try:
            # In real implementation, encode the proposal execution
            # For now, just log the action
            logger.info(f"Submitting proposal {proposal_id} to Optimism L2")
            
            # Example: could call a DAO contract to execute the proposal
            # tx_hash = await self.optimism_client.call_contract_function(
            #     dao_contract_address,
            #     "executeProposal",
            #     [proposal_id, proposal["data"]],
            #     dao_contract_abi
            # )
            
            proposal["onchain_status"] = "submitted"
            # proposal["tx_hash"] = tx_hash
            
        except Exception as e:
            proposal["onchain_status"] = "failed"
            logger.error(f"Failed to submit proposal {proposal_id} to Optimism: {e}")


class GameStateCoordinator:
    """Coordinates game state across peers with periodic onchain checkpointing"""
    
    def __init__(self, p2p_node: LibP2PNode, optimism_client: OptimismClient):
        self.p2p_node = p2p_node
        self.optimism_client = optimism_client
        self.games: Dict[str, Dict[str, Any]] = {}
        
        # Register protocol handlers
        game_protocol = self.p2p_node.get_protocol("/op/game/1.0.0")
        if game_protocol:
            game_protocol.register_handler("game_move", self._handle_move_message)
            game_protocol.register_handler("checkpoint", self._handle_checkpoint_message)
    
    async def create_game(self, game_type: str, initial_state: Dict[str, Any]) -> str:
        """Create a new game session"""
        game_id = f"game_{self.p2p_node.peer_id}_{int(time.time())}"
        
        game = {
            "game_id": game_id,
            "creator": self.p2p_node.peer_id,
            "game_type": game_type,
            "state": initial_state,
            "moves": [],
            "sequence": 0,
            "players": [self.p2p_node.peer_id],
            "status": "active",
            "last_checkpoint": time.time()
        }
        
        self.games[game_id] = game
        logger.info(f"Created game {game_id} of type {game_type}")
        return game_id
    
    async def make_move(
        self, 
        game_id: str, 
        move_data: Dict[str, Any]
    ) -> bool:
        """Make a move in a game"""
        if game_id not in self.games:
            logger.warning(f"Game {game_id} not found")
            return False
        
        game = self.games[game_id]
        
        if game["status"] != "active":
            logger.warning(f"Game {game_id} is not active")
            return False
        
        # Create move
        move = {
            "player": self.p2p_node.peer_id,
            "data": move_data,
            "sequence": game["sequence"],
            "timestamp": time.time()
        }
        
        # Apply move locally
        game["moves"].append(move)
        game["sequence"] += 1
        
        # Update game state (game-specific logic would go here)
        self._update_game_state(game_id, move)
        
        # Broadcast move to peers
        await self.p2p_node.broadcast_game_move(
            game_id=game_id,
            move_data=move_data,
            sequence_number=move["sequence"]
        )
        
        # Check if checkpoint is needed
        await self._check_checkpoint(game_id)
        
        logger.info(f"Made move in game {game_id}, sequence {move['sequence']}")
        return True
    
    async def _handle_move_message(self, message: Dict[str, Any], stream):
        """Handle incoming game move"""
        game_id = message.get("game_id")
        sender_id = message.get("sender_id")
        move_data = message.get("move_data")
        sequence = message.get("sequence_number")
        
        if game_id not in self.games:
            logger.warning(f"Received move for unknown game {game_id}")
            return
        
        game = self.games[game_id]
        
        # Validate sequence number
        if sequence != game["sequence"]:
            logger.warning(f"Out of order move for game {game_id}: expected {game['sequence']}, got {sequence}")
            return
        
        # Apply move
        move = {
            "player": sender_id,
            "data": move_data,
            "sequence": sequence,
            "timestamp": time.time()
        }
        
        game["moves"].append(move)
        game["sequence"] += 1
        
        # Update game state
        self._update_game_state(game_id, move)
        
        logger.info(f"Applied move from {sender_id} in game {game_id}, sequence {sequence}")
    
    def _update_game_state(self, game_id: str, move: Dict[str, Any]):
        """Update game state based on move (game-specific logic)"""
        game = self.games[game_id]
        
        # Example: simple turn-based game state update
        if game["game_type"] == "turn_based":
            game["state"]["last_player"] = move["player"]
            game["state"]["turn_count"] = game["state"].get("turn_count", 0) + 1
    
    async def _check_checkpoint(self, game_id: str):
        """Check if game needs checkpointing to Optimism"""
        game = self.games[game_id]
        
        # Checkpoint every 10 moves or 5 minutes
        moves_since_checkpoint = len(game["moves"])
        time_since_checkpoint = time.time() - game["last_checkpoint"]
        
        should_checkpoint = (
            moves_since_checkpoint >= 10 or
            time_since_checkpoint >= 300
        )
        
        if should_checkpoint:
            await self._create_checkpoint(game_id)
    
    async def _create_checkpoint(self, game_id: str):
        """Create onchain checkpoint of game state"""
        game = self.games[game_id]
        
        try:
            # Create state hash
            state_data = json.dumps(game["state"], sort_keys=True)
            state_hash = hashlib.sha256(state_data.encode()).hexdigest()
            
            checkpoint = {
                "game_id": game_id,
                "sequence": game["sequence"],
                "state_hash": state_hash,
                "timestamp": int(time.time()),
                "move_count": len(game["moves"])
            }
            
            # In real implementation, submit to Optimism
            logger.info(f"Creating checkpoint for game {game_id} at sequence {game['sequence']}")
            
            # Example contract call:
            # tx_hash = await self.optimism_client.call_contract_function(
            #     game_contract_address,
            #     "createCheckpoint",
            #     [game_id, game["sequence"], state_hash],
            #     game_contract_abi
            # )
            
            game["last_checkpoint"] = time.time()
            game["checkpoints"] = game.get("checkpoints", [])
            game["checkpoints"].append(checkpoint)
            
        except Exception as e:
            logger.error(f"Failed to create checkpoint for game {game_id}: {e}")
    
    async def _handle_checkpoint_message(self, message: Dict[str, Any], stream):
        """Handle checkpoint coordination message"""
        # Implementation for coordinating checkpoints across peers
        pass
