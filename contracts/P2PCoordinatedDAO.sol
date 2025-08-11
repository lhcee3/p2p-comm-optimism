// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title P2PCoordinatedDAO
 * @dev DAO contract that supports P2P vote coordination before onchain finalization
 */
contract P2PCoordinatedDAO {
    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        bytes executionData;
        uint256 startTime;
        uint256 endTime;
        uint256 yesVotes;
        uint256 noVotes;
        bool executed;
        bytes32 p2pVoteHash; // Hash of P2P coordination data
    }
    
    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;
    mapping(address => uint256) public votingPower;
    
    uint256 public proposalCount;
    uint256 public constant VOTING_DURATION = 7 days;
    uint256 public constant MIN_VOTING_POWER = 1000;
    
    event ProposalCreated(uint256 indexed proposalId, address indexed proposer, string title);
    event P2PVotesSubmitted(uint256 indexed proposalId, bytes32 voteHash, uint256 yesVotes, uint256 noVotes);
    event ProposalExecuted(uint256 indexed proposalId);
    
    function createProposal(
        string memory title,
        string memory description,
        bytes memory executionData
    ) external returns (uint256) {
        require(votingPower[msg.sender] >= MIN_VOTING_POWER, "Insufficient voting power");
        
        uint256 proposalId = proposalCount++;
        
        proposals[proposalId] = Proposal({
            id: proposalId,
            proposer: msg.sender,
            title: title,
            description: description,
            executionData: executionData,
            startTime: block.timestamp,
            endTime: block.timestamp + VOTING_DURATION,
            yesVotes: 0,
            noVotes: 0,
            executed: false,
            p2pVoteHash: bytes32(0)
        });
        
        emit ProposalCreated(proposalId, msg.sender, title);
        return proposalId;
    }
    
    function submitP2PVotes(
        uint256 proposalId,
        bytes32 voteHash,
        uint256 yesVotes,
        uint256 noVotes,
        bytes calldata coordinationProof
    ) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id == proposalId, "Proposal does not exist");
        require(block.timestamp <= proposal.endTime, "Voting period ended");
        require(proposal.p2pVoteHash == bytes32(0), "P2P votes already submitted");
        
        // In a real implementation, verify the coordination proof
        // This could involve checking signatures from multiple peers
        require(coordinationProof.length > 0, "Invalid coordination proof");
        
        proposal.yesVotes = yesVotes;
        proposal.noVotes = noVotes;
        proposal.p2pVoteHash = voteHash;
        
        emit P2PVotesSubmitted(proposalId, voteHash, yesVotes, noVotes);
    }
    
    function executeProposal(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id == proposalId, "Proposal does not exist");
        require(block.timestamp > proposal.endTime, "Voting period not ended");
        require(!proposal.executed, "Proposal already executed");
        require(proposal.yesVotes > proposal.noVotes, "Proposal did not pass");
        
        proposal.executed = true;
        
        // Execute the proposal (simplified)
        if (proposal.executionData.length > 0) {
            (bool success,) = address(this).call(proposal.executionData);
            require(success, "Proposal execution failed");
        }
        
        emit ProposalExecuted(proposalId);
    }
    
    function setVotingPower(address user, uint256 power) external {
        // In a real implementation, this would have proper access controls
        votingPower[user] = power;
    }
    
    function getProposal(uint256 proposalId) external view returns (Proposal memory) {
        return proposals[proposalId];
    }
}
