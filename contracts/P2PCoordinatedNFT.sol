// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title P2PCoordinatedNFT
 * @dev NFT contract that supports P2P coordinated minting to reduce gas wars
 */
contract P2PCoordinatedNFT {
    uint256 private _tokenIdCounter;
    mapping(uint256 => address) private _owners;
    mapping(address => uint256) private _balances;
    mapping(uint256 => address) private _tokenApprovals;
    mapping(address => mapping(address => bool)) private _operatorApprovals;
    
    // P2P coordination events
    event MintIntentRegistered(address indexed user, uint256 tokenId, bytes32 intentHash);
    event CoordinatedMint(address indexed to, uint256 tokenId, bytes32 batchHash);
    
    // Intent coordination
    struct MintIntent {
        address user;
        uint256 tokenId;
        uint256 timestamp;
        bytes32 p2pHash; // Hash of P2P coordination data
    }
    
    mapping(bytes32 => MintIntent) public mintIntents;
    mapping(uint256 => bytes32) public tokenIntents;
    
    function registerMintIntent(
        uint256 tokenId, 
        bytes32 p2pHash
    ) external {
        require(_owners[tokenId] == address(0), "Token already minted");
        
        bytes32 intentHash = keccak256(abi.encodePacked(
            msg.sender,
            tokenId,
            block.timestamp,
            p2pHash
        ));
        
        mintIntents[intentHash] = MintIntent({
            user: msg.sender,
            tokenId: tokenId,
            timestamp: block.timestamp,
            p2pHash: p2pHash
        });
        
        tokenIntents[tokenId] = intentHash;
        
        emit MintIntentRegistered(msg.sender, tokenId, intentHash);
    }
    
    function coordinatedMint(
        address to,
        uint256 tokenId,
        bytes32 batchHash,
        bytes32 intentHash
    ) external {
        require(_owners[tokenId] == address(0), "Token already minted");
        
        MintIntent memory intent = mintIntents[intentHash];
        require(intent.user == to, "Intent user mismatch");
        require(intent.tokenId == tokenId, "Intent token mismatch");
        
        // Mint the token
        _owners[tokenId] = to;
        _balances[to] += 1;
        
        emit CoordinatedMint(to, tokenId, batchHash);
    }
    
    function mint(address to, uint256 tokenId) external {
        require(_owners[tokenId] == address(0), "Token already minted");
        
        _owners[tokenId] = to;
        _balances[to] += 1;
    }
    
    // Standard ERC721 functions (simplified)
    function ownerOf(uint256 tokenId) external view returns (address) {
        return _owners[tokenId];
    }
    
    function balanceOf(address owner) external view returns (uint256) {
        return _balances[owner];
    }
}
