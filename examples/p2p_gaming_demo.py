"""
P2P Gaming Demo - Collaborative game state with onchain checkpointing

This demo shows how peers can synchronize game state offchain with
periodic checkpoints to Optimism L2 for dispute resolution.

Usage:
    # Terminal 1 (Game Host)
    python examples/p2p_gaming_demo.py --port 6001 --role host
    
    # Terminal 2 (Player 1)
    python examples/p2p_gaming_demo.py --port 6002 --role player --connect /ip4/127.0.0.1/tcp/6001/p2p/<PEER_ID>
    
    # Terminal 3 (Player 2)
    python examples/p2p_gaming_demo.py --port 6003 --role player --connect /ip4/127.0.0.1/tcp/6001/p2p/<PEER_ID>
"""
import asyncio
import argparse
import logging
import os
import sys
import random
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.libp2p_node import LibP2PNode
from src.optimism_client import OptimismClient
from src.dapp_logic import GameStateCoordinator
from config.optimism_config import OptimismConfig, P2PConfig


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class P2PGamingDemo:
    """Demo application for P2P gaming with onchain checkpointing"""
    
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
        self.coordinator = GameStateCoordinator(self.p2p_node, self.optimism_client)
        
        # Demo state
        self.running = False
        self.game_id = None
        self.player_score = 0
    
    async def start(self):
        """Start the demo"""
        logger.info(f"Starting P2P Gaming Demo as {self.role} on port {self.port}")
        
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
        if self.role == "host":
            await self._run_host()
        else:
            await self._run_player()
    
    async def connect_to_peer(self, peer_address: str):
        """Connect to another peer"""
        success = await self.p2p_node.connect_to_peer(peer_address)
        if success:
            logger.info(f"Connected to peer: {peer_address}")
        else:
            logger.error(f"Failed to connect to peer: {peer_address}")
        return success
    
    async def _run_host(self):
        """Run as game host"""
        logger.info("Running as game host - will create and manage game")
        
        # Wait for players to connect
        await asyncio.sleep(5)
        
        # Create a simple turn-based game
        initial_state = {
            "game_type": "simple_scoring",
            "players": {},
            "current_turn": 0,
            "max_turns": 20,
            "leaderboard": {}
        }
        
        self.game_id = await self.coordinator.create_game(
            game_type="turn_based",
            initial_state=initial_state
        )
        
        logger.info(f"Created game {self.game_id}")
        
        # Start game loop
        await self._game_loop()
    
    async def _run_player(self):
        """Run as game player"""
        logger.info("Running as game player - will join and play")
        
        # Wait for game to be created
        await asyncio.sleep(10)
        
        # Start making moves
        await self._player_loop()
    
    async def _game_loop(self):
        """Main game loop for host"""
        turn_count = 0
        max_turns = 20
        
        while self.running and turn_count < max_turns:
            # Make host move
            await self._make_random_move()
            
            # Wait for other players
            await asyncio.sleep(3)
            
            turn_count += 1
            logger.info(f"Turn {turn_count}/{max_turns} completed")
            
            # Show current game state
            if self.game_id and self.game_id in self.coordinator.games:
                game = self.coordinator.games[self.game_id]
                logger.info(f"Game state: {game['state']}")
        
        logger.info("Game completed!")
        await self._show_final_results()
    
    async def _player_loop(self):
        """Game loop for players"""
        move_count = 0
        
        while self.running and move_count < 15:
            await asyncio.sleep(random.uniform(2, 6))  # Random delay
            await self._make_random_move()
            move_count += 1
    
    async def _make_random_move(self):
        """Make a random game move"""
        if not self.game_id:
            # Try to find an existing game
            if self.coordinator.games:
                self.game_id = list(self.coordinator.games.keys())[0]
            else:
                return
        
        # Generate random move
        move_types = ["attack", "defend", "collect", "special"]
        move_type = random.choice(move_types)
        points = random.randint(1, 10)
        
        move_data = {
            "type": move_type,
            "points": points,
            "player": self.p2p_node.peer_id,
            "random_factor": random.random()
        }
        
        # Update local score
        self.player_score += points
        
        success = await self.coordinator.make_move(self.game_id, move_data)
        
        if success:
            logger.info(f"Made {move_type} move for {points} points (total: {self.player_score})")
        else:
            logger.warning("Failed to make move")
    
    async def _show_final_results(self):
        """Show final game results"""
        if not self.game_id or self.game_id not in self.coordinator.games:
            return
        
        game = self.coordinator.games[self.game_id]
        
        # Calculate final scores
        player_scores = {}
        for move in game["moves"]:
            player = move["player"]
            points = move["data"].get("points", 0)
            player_scores[player] = player_scores.get(player, 0) + points
        
        # Show leaderboard
        logger.info("=== FINAL RESULTS ===")
        sorted_scores = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
        
        for i, (player, score) in enumerate(sorted_scores, 1):
            logger.info(f"{i}. {player}: {score} points")
        
        logger.info(f"Total moves: {len(game['moves'])}")
        logger.info(f"Checkpoints created: {len(game.get('checkpoints', []))}")
    
    async def stop(self):
        """Stop the demo"""
        logger.info("Stopping P2P Gaming Demo")
        self.running = False
        await self.p2p_node.stop()


async def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="P2P Gaming Demo")
    parser.add_argument("--port", type=int, default=6001, help="P2P listen port")
    parser.add_argument("--role", choices=["host", "player"], default="host", help="Node role")
    parser.add_argument("--connect", type=str, help="Peer address to connect to")
    
    args = parser.parse_args()
    
    # Create and start demo
    demo = P2PGamingDemo(args.port, args.role)
    
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
