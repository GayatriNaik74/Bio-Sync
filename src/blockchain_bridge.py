"""
BioSync Phase 3 — Blockchain Bridge
Connects Python trust engine to the BioSyncAuth smart contract.
Usage: python src/blockchain_bridge.py  (runs a demo test)
"""

import os
import json
import datetime
from web3 import Web3

# ── Configuration ──────────────────────────────────
# !! REPLACE with your contract address from truffle migrate !!
CONTRACT_ADDRESS =  "0x66664c46251507DB7a6d5fdff443D739689d5104"

GANACHE_URL  = "http://127.0.0.1:7545"
ABI_PATH     = "blockchain/build/contracts/BioSyncAuth.json"

# ── Connect to Ganache ──────────────────────────────
def connect():
    w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
    if not w3.is_connected():
        raise ConnectionError(
            "Cannot connect to Ganache. Is it running?"
        )
    print(f"  ✓ Connected to Ganache")
    print(f"  Block number : {w3.eth.block_number}")
    print(f"  Accounts     : {len(w3.eth.accounts)}")
    return w3

# ── Load contract ABI ───────────────────────────────
def load_contract(w3):
    if not os.path.exists(ABI_PATH):
        raise FileNotFoundError(
            f"ABI not found at {ABI_PATH}. Run truffle compile first."
        )
    with open(ABI_PATH) as f:
        artifact = json.load(f)

    abi      = artifact['abi']
    checksum = Web3.to_checksum_address(CONTRACT_ADDRESS)
    contract = w3.eth.contract(address=checksum, abi=abi)
    print(f"  ✓ Contract loaded at {CONTRACT_ADDRESS[:10]}...")
    return contract

# ── Log a security event to blockchain ──────────────
def log_event(w3, contract, session_id: str,
              event_type: str, trust_score: int,
              risk_level: str) -> str:
    """
    Writes a security event to the blockchain.
    event_type: 'ANOMALY', 'LOCK', or 'RESTORE'
    Returns: transaction hash
    """
    account = w3.eth.accounts[0]   # use first Ganache account

    tx_hash = contract.functions.logEvent(
        session_id,
        event_type,
        int(trust_score),
        risk_level
    ).transact({'from': account})

    # Wait for transaction to be mined
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    tx_str  = tx_hash.hex()

    print(f"  ✓ Event logged on blockchain")
    print(f"    Type    : {event_type}")
    print(f"    Score   : {trust_score}")
    print(f"    Risk    : {risk_level}")
    print(f"    Tx Hash : {tx_str[:20]}...")
    print(f"    Gas used: {receipt['gasUsed']}")
    return tx_str

# ── Check if a session is locked ────────────────────
def is_session_locked(contract, session_id: str) -> bool:
    return contract.functions.isLocked(session_id).call()

# ── Get total events logged ──────────────────────────
def get_event_count(contract) -> int:
    return contract.functions.getEventCount().call()

# ── BioSync integration: called by trust engine ──────
def handle_trust_score(session_id: str, trust_score: float,
                        risk_level: str) -> dict:
    """
    Main function called by trust_engine.py whenever score updates.
    Logs to blockchain only for MEDIUM/HIGH risk events.
    Returns: dict with tx_hash and action taken
    """
    result = {'logged': False, 'tx_hash': None, 'action': 'none'}

    if risk_level == 'LOW':
        return result   # don't log normal operation

    try:
        w3       = connect()
        contract = load_contract(w3)

        event_type = 'LOCK' if risk_level == 'HIGH' else 'ANOMALY'
        tx_hash    = log_event(w3, contract, session_id,
                               event_type, int(trust_score), risk_level)
        result = {'logged': True, 'tx_hash': tx_hash,
                  'action': event_type}
    except Exception as e:
        print(f"  ⚠ Blockchain log failed: {e}")
        print(f"  (Is Ganache running?)")

    return result

# ── Demo test ────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 50)
    print("  BioSync — Blockchain Bridge Test")
    print("═" * 50)

    w3       = connect()
    contract = load_contract(w3)

    session  = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Test 1: Log an anomaly event
    print(f"\n  Test 1 — Log ANOMALY event")
    log_event(w3, contract, session, "ANOMALY", 62, "MEDIUM")

    # Test 2: Log a lock event
    print(f"\n  Test 2 — Log LOCK event")
    log_event(w3, contract, session, "LOCK", 38, "HIGH")

    # Test 3: Check if session is locked
    locked = is_session_locked(contract, session)
    print(f"\n  Session locked: {locked}")

    # Test 4: Total events on chain
    count = get_event_count(contract)
    print(f"  Total events on blockchain: {count}")

    print("\n  ✓ Check Ganache UI — you should see 2 transactions!")