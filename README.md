# py-libp2p + Optimism Integration

A Python-based integration prototype that combines py-libp2p peer-to-peer networking with Optimism L2 for decentralized applications.

## Features

- **P2P Messaging**: Uses py-libp2p for decentralized peer discovery and communication
- **Optimism Integration**: Connects to Optimism L2 for onchain state management
- **Hybrid Architecture**: Supports both offchain coordination and onchain finalization
- **Modular Design**: Pluggable dApp logic for various use cases

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   py-libp2p     │    │   Application   │    │   Optimism L2   │
│     Node        │◄──►│     Logic       │◄──►│   (via RPC)     │
│                 │    │                 │    │                 │
│ • Peer Discovery│    │ • Message       │    │ • State Updates │
│ • PubSub        │    │   Handling      │    │ • Transactions  │
│ • Stream Proto  │    │ • Intent Sync   │    │ • Smart Contract│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Quick Start

### Prerequisites

```bash
# Install Python 3.8+
pip install -r requirements.txt
```

### Running the Demo

**🎮 Easy Mode (No API Keys Required)**

The project works perfectly in mock mode for learning and testing:

1. **Start Node 1** (in terminal 1):
```bash
python examples/nft_mint_intent_demo.py --port 4001 --role coordinator
```

2. **Start Node 2** (in terminal 2):
```bash
python examples/nft_mint_intent_demo.py --port 4002 --role participant --connect /ip4/127.0.0.1/tcp/4001/p2p/<NODE1_PEER_ID>
```

3. **Watch the P2P coordination and L2 interactions**

**⚙️ Configuration Modes**

- **Mock Mode** (default): No API keys, full simulation
- **Testnet Mode**: Connect to Optimism Goerli (requires test ETH)
- **Production Mode**: Real mainnet integration (requires API keys)

See [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for detailed mode configuration.

### Configuration

Edit `config/optimism_config.py` to set:
- Optimism RPC endpoint
- Contract addresses
- Network parameters

Copy `.env.example` to `.env` and configure for your desired mode.

## Use Cases

### 1. P2P NFT Mint Intent Sharing
- Peers share mint intentions offchain
- Coordinate to avoid gas wars
- Batch submit to Optimism L2

### 2. Collaborative Gaming
- P2P game state synchronization
- Offchain move validation
- Periodic onchain checkpointing

### 3. DAO Voting Coordination
- Offchain vote collection
- Consensus building via gossip
- Batch finalization onchain

## Project Structure

```
pi2o/
├── src/
│   ├── libp2p_node/          # py-libp2p integration
│   ├── optimism_client/      # L2 interaction layer
│   ├── protocols/            # Custom libp2p protocols
│   ├── message_encoding/     # RLP/JSON encoding
│   └── dapp_logic/          # Application-specific logic
├── examples/                 # Demo applications
├── tests/                   # Test suite
├── config/                  # Configuration files
└── docs/                    # Documentation
```

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Adding New Protocols
1. Create protocol in `src/protocols/`
2. Register in `src/libp2p_node/node.py`
3. Add dApp logic in `src/dapp_logic/`

### Custom dApp Integration
```python
from src.libp2p_node import LibP2PNode
from src.optimism_client import OptimismClient

# Create your custom dApp
class MyDApp:
    def __init__(self):
        self.p2p_node = LibP2PNode()
        self.optimism_client = OptimismClient()
    
    async def handle_message(self, message):
        # Process P2P message
        # Optionally interact with L2
        pass
```

## 📚 Documentation

- **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** - Complete project structure and development modes
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute to the project
- **[docs/architecture.md](docs/architecture.md)** - Detailed system architecture
- **[examples/](examples/)** - Working demo applications

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines  
- How to add new features
- Testing procedures
- Community guidelines

## License

MIT License - see [LICENSE](LICENSE) file for details.
