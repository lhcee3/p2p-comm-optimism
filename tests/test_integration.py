"""
Test suite for py-libp2p + Optimism integration
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.libp2p_node import LibP2PNode
from src.optimism_client import OptimismClient
from src.dapp_logic import NFTMintCoordinator, DAOVotingCoordinator
from src.message_encoding import MessageEncoder, MessageValidator, MessageFactory
from config.optimism_config import OptimismConfig, P2PConfig


class TestMessageEncoding:
    """Test message encoding and validation"""
    
    def test_json_encoding(self):
        """Test JSON message encoding/decoding"""
        message = MessageFactory.create_intent_message(
            sender_id="test_peer",
            intent_id="intent_123",
            target_contract="0x123",
            function_call="mint(1)",
            gas_estimate=21000,
            timestamp=int(time.time())
        )
        
        # Encode and decode
        encoded = MessageEncoder.encode_json(message)
        decoded = MessageEncoder.decode_json(encoded)
        
        assert decoded["msg_type"] == "intent"
        assert decoded["intent_id"] == "intent_123"
        assert decoded["sender_id"] == "test_peer"
    
    def test_message_validation(self):
        """Test message validation"""
        valid_message = {
            "msg_type": "intent",
            "sender_id": "peer_123",
            "timestamp": int(time.time()),
            "data": {"test": "data"},
            "intent_id": "intent_123",
            "target_contract": "0x123",
            "function_call": "mint(1)",
            "gas_estimate": 21000
        }
        
        # Valid message should pass
        assert MessageValidator.validate_message(valid_message)
        assert MessageValidator.validate_intent_message(valid_message)
        
        # Invalid message should fail
        invalid_message = {"msg_type": "intent"}
        assert not MessageValidator.validate_message(invalid_message)
        assert not MessageValidator.validate_intent_message(invalid_message)


class TestLibP2PNode:
    """Test LibP2P node functionality"""
    
    @pytest.mark.asyncio
    async def test_node_startup(self):
        """Test node startup and shutdown"""
        config = P2PConfig()
        node = LibP2PNode(config)
        
        # Start node
        peer_id = await node.start(4001)
        assert peer_id is not None
        assert node.running
        assert node.peer_id == peer_id
        
        # Stop node
        await node.stop()
        assert not node.running
    
    @pytest.mark.asyncio
    async def test_peer_connection_simulation(self):
        """Test simulated peer connections"""
        node = LibP2PNode()
        await node.start(4001)
        
        # Simulate peer connection
        peer_address = "/ip4/127.0.0.1/tcp/4002/p2p/test_peer_123"
        success = await node.connect_to_peer(peer_address)
        
        assert success
        assert "test_peer_123" in node.connected_peers
        
        # Test disconnection
        await node.disconnect_peer("test_peer_123")
        assert "test_peer_123" not in node.connected_peers
        
        await node.stop()
    
    @pytest.mark.asyncio
    async def test_message_broadcasting(self):
        """Test message broadcasting"""
        node = LibP2PNode()
        await node.start(4001)
        
        # Connect to mock peers
        await node.connect_to_peer("/ip4/127.0.0.1/tcp/4002/p2p/peer1")
        await node.connect_to_peer("/ip4/127.0.0.1/tcp/4003/p2p/peer2")
        
        # Broadcast intent
        sent_count = await node.share_intent(
            intent_id="test_intent",
            contract_address="0x123",
            function_call="mint(1)",
            gas_estimate=21000
        )
        
        assert sent_count == 2  # Should send to both peers
        
        await node.stop()


class TestOptimismClient:
    """Test Optimism client functionality"""
    
    def test_client_initialization(self):
        """Test client initialization"""
        config = OptimismConfig.for_testnet()
        client = OptimismClient(config)
        
        assert client.config.chain_id == 420  # Optimism Goerli
        assert client.w3 is not None
    
    @pytest.mark.asyncio
    async def test_mock_connection(self):
        """Test mock connection (since we don't have real RPC)"""
        config = OptimismConfig.for_testnet()
        client = OptimismClient(config)
        
        # Mock the web3 connection
        client.w3.eth.block_number = 12345
        
        # This would normally test real connection
        # For demo purposes, we'll just verify the client exists
        assert client.config.rpc_url == "https://goerli.optimism.io"


class TestNFTMintCoordinator:
    """Test NFT mint coordination logic"""
    
    @pytest.mark.asyncio
    async def test_intent_creation(self):
        """Test intent creation and sharing"""
        # Mock dependencies
        p2p_node = Mock(spec=LibP2PNode)
        p2p_node.peer_id = "test_peer"
        p2p_node.share_intent = AsyncMock(return_value=2)
        
        optimism_client = Mock(spec=OptimismClient)
        optimism_client.estimate_gas = AsyncMock(return_value=21000)
        
        coordinator = NFTMintCoordinator(p2p_node, optimism_client)
        
        # Create intent
        intent_id = await coordinator.create_mint_intent(
            nft_contract="0x123",
            token_id=1,
            priority=5
        )
        
        # Verify intent was created
        assert intent_id in coordinator.intents
        intent = coordinator.intents[intent_id]
        assert intent.contract_address == "0x123"
        assert intent.function_call == "mint(1)"
        assert intent.priority == 5
        
        # Verify sharing was called
        p2p_node.share_intent.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_intent_coordination(self):
        """Test intent coordination logic"""
        p2p_node = Mock(spec=LibP2PNode)
        p2p_node.peer_id = "test_peer"
        p2p_node.get_connected_peers.return_value = ["peer1", "peer2"]
        p2p_node.broadcast_message = AsyncMock()
        
        optimism_client = Mock(spec=OptimismClient)
        
        coordinator = NFTMintCoordinator(p2p_node, optimism_client)
        
        # Simulate receiving an intent message
        intent_message = {
            "msg_type": "intent",
            "intent_id": "intent_123",
            "sender_id": "peer1", 
            "timestamp": int(time.time()),
            "target_contract": "0x123",
            "function_call": "mint(1)",
            "gas_estimate": 21000,
            "priority": 5
        }
        
        await coordinator._handle_intent_message(intent_message, None)
        
        # Verify intent was stored
        assert "intent_123" in coordinator.intents


class TestDAOVotingCoordinator:
    """Test DAO voting coordination logic"""
    
    @pytest.mark.asyncio
    async def test_proposal_creation(self):
        """Test proposal creation and broadcasting"""
        p2p_node = Mock(spec=LibP2PNode)
        p2p_node.peer_id = "test_peer"
        p2p_node.broadcast_message = AsyncMock()
        
        optimism_client = Mock(spec=OptimismClient)
        
        coordinator = DAOVotingCoordinator(p2p_node, optimism_client)
        
        # Create proposal
        proposal_data = {
            "title": "Test Proposal",
            "description": "A test proposal",
            "action": "transfer"
        }
        
        proposal_id = await coordinator.create_proposal(proposal_data, 60)
        
        # Verify proposal was created
        assert proposal_id in coordinator.proposals
        proposal = coordinator.proposals[proposal_id]
        assert proposal["data"]["title"] == "Test Proposal"
        assert proposal["status"] == "active"
        
        # Verify broadcast was called
        p2p_node.broadcast_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_voting_process(self):
        """Test voting process"""
        p2p_node = Mock(spec=LibP2PNode)
        p2p_node.peer_id = "test_peer"
        p2p_node.submit_vote = AsyncMock()
        
        optimism_client = Mock(spec=OptimismClient)
        
        coordinator = DAOVotingCoordinator(p2p_node, optimism_client)
        
        # Create proposal
        proposal_id = await coordinator.create_proposal({"title": "Test"}, 60)
        
        # Submit vote
        success = await coordinator.submit_vote(proposal_id, True, 10)
        
        assert success
        
        # Verify vote was recorded
        proposal = coordinator.proposals[proposal_id]
        assert "test_peer" in proposal["votes"]
        assert proposal["votes"]["test_peer"]["vote"] is True
        assert proposal["votes"]["test_peer"]["power"] == 10


class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """Test a complete workflow simulation"""
        # Create two nodes
        node1 = LibP2PNode()
        node2 = LibP2PNode()
        
        await node1.start(4001)
        await node2.start(4002)
        
        # Connect nodes
        peer1_addr = f"/ip4/127.0.0.1/tcp/4001/p2p/{node1.peer_id}"
        await node2.connect_to_peer(peer1_addr)
        
        # Create coordinators
        config = OptimismConfig.for_testnet()
        client1 = OptimismClient(config)
        client2 = OptimismClient(config)
        
        coord1 = NFTMintCoordinator(node1, client1)
        coord2 = NFTMintCoordinator(node2, client2)
        
        # Simulate intent sharing
        await node1.share_intent(
            intent_id="test_intent",
            contract_address="0x123",
            function_call="mint(1)", 
            gas_estimate=21000
        )
        
        # Simulate message receipt
        await node2.simulate_message_received(
            node1.peer_id,
            "/op/intent/1.0.0",
            {
                "msg_type": "intent",
                "intent_id": "test_intent",
                "sender_id": node1.peer_id,
                "timestamp": int(time.time()),
                "data": {"contract": "0x123", "function": "mint(1)", "gas": 21000},
                "target_contract": "0x123",
                "function_call": "mint(1)",
                "gas_estimate": 21000
            }
        )
        
        # Verify intent was received
        assert "test_intent" in coord2.intents
        
        # Cleanup
        await node1.stop()
        await node2.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
