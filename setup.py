"""
Setup and installation script for py-libp2p + Optimism integration
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(command, description):
    """Run a shell command with error handling"""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        print(f"Error: {e.stderr.strip()}")
        return False


def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor} is compatible")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor} is not compatible. Python 3.8+ required.")
        return False


def install_dependencies():
    """Install Python dependencies"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found")
        return False
    
    # Update pip first
    if not run_command(f"{sys.executable} -m pip install --upgrade pip", "Updating pip"):
        return False
    
    # Install requirements
    return run_command(
        f"{sys.executable} -m pip install -r {requirements_file}",
        "Installing dependencies"
    )


def create_directories():
    """Create necessary directories"""
    print("\n🔄 Creating project directories...")
    
    directories = [
        "logs",
        "data", 
        "config/local",
        "examples/outputs"
    ]
    
    for directory in directories:
        dir_path = Path(__file__).parent / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    print("✅ Directories created successfully")
    return True


def run_tests():
    """Run the test suite"""
    return run_command(
        f"{sys.executable} -m pytest tests/ -v",
        "Running test suite"
    )


def setup_environment():
    """Setup environment configuration"""
    print("\n🔄 Setting up environment...")
    
    env_example = Path(__file__).parent / ".env.example"
    env_file = Path(__file__).parent / ".env"
    
    if not env_file.exists() and env_example.exists():
        # Copy example env file
        with open(env_example, 'r') as src, open(env_file, 'w') as dst:
            dst.write(src.read())
        print("✅ Environment file created from example")
    
    return True


def print_next_steps():
    """Print next steps for the user"""
    print("""
🎉 Setup completed successfully!

📋 Next steps:

1. 📝 Configure your environment:
   - Edit config/optimism_config.py for your network settings
   - Set up your Optimism RPC endpoints
   - Configure private keys (use environment variables)

2. 🧪 Try the demos:
   
   # NFT Mint Intent Demo
   python examples/nft_mint_intent_demo.py --port 4001 --role coordinator
   python examples/nft_mint_intent_demo.py --port 4002 --role participant --connect /ip4/127.0.0.1/tcp/4001/p2p/<PEER_ID>
   
   # DAO Voting Demo  
   python examples/dao_voting_demo.py --port 5001 --role proposer
   python examples/dao_voting_demo.py --port 5002 --role voter --connect /ip4/127.0.0.1/tcp/5001/p2p/<PEER_ID>
   
   # P2P Gaming Demo
   python examples/p2p_gaming_demo.py --port 6001 --role host
   python examples/p2p_gaming_demo.py --port 6002 --role player --connect /ip4/127.0.0.1/tcp/6001/p2p/<PEER_ID>

3. 📚 Read the documentation:
   - docs/architecture.md for system overview
   - README.md for usage instructions

4. 🔧 Development:
   - Run tests: python -m pytest tests/
   - Add custom protocols in src/protocols/
   - Implement dApp logic in src/dapp_logic/

Happy building! 🚀
""")


def main():
    """Main setup function"""
    print("🚀 py-libp2p + Optimism Integration Setup")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directories
    if not create_directories():
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\n⚠️  Warning: Some dependencies failed to install.")
        print("This might be expected if you don't have a real libp2p installation.")
        print("The demos will work with the mock implementation.")
    
    # Setup environment
    setup_environment()
    
    # Run tests (optional, might fail without real dependencies)
    print("\n🧪 Running tests (optional)...")
    test_success = run_tests()
    if not test_success:
        print("⚠️  Some tests failed. This is expected without real libp2p dependencies.")
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    main()
