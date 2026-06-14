"""ERC-8004 agent identity registration.

Registers the agent's dedicated wallet as an on-chain agent identity. Required for the BNB
Track 1 submission (BSC registry verified: 0x8004a169fb4a3325136eb29fa0ceb6d2e539a432).
Optional for Mantle (Mantle submission proof can be a real swap tx instead).

NOTE: the wallet registered here BECOMES the agent's trading wallet. Use a dedicated, freshly
generated wallet funded with only the test capital + gas. Never a personal wallet.

This is a skeleton: the exact registry ABI/method must be confirmed from the deployed
Identity Registry contract before running. Fill REGISTER_ABI once confirmed on a BSC explorer.
"""
from __future__ import annotations

import os

from web3 import Web3

REGISTRY_BSC = os.environ.get("ERC8004_REGISTRY_BSC", "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432")

# TODO confirm the real registry ABI (method name + args) from the verified contract on bscscan.
# Common ERC-8004 shape is a register/newAgent call returning a token id. Placeholder below.
REGISTER_ABI = [
    {
        "name": "register",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [{"name": "agentDomain", "type": "string"}, {"name": "agentAddress", "type": "address"}],
        "outputs": [{"name": "agentId", "type": "uint256"}],
    }
]


def register(rpc_url: str, registry_addr: str, private_key: str, agent_domain: str) -> dict:
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    acct = w3.eth.account.from_key(private_key)
    registry = w3.eth.contract(address=Web3.to_checksum_address(registry_addr), abi=REGISTER_ABI)

    tx = registry.functions.register(agent_domain, acct.address).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 300_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return {"tx_hash": tx_hash.hex(), "agent_address": acct.address, "status": receipt.status}


if __name__ == "__main__":
    # Dedicated wallet only. Confirm ABI before running for real.
    out = register(
        rpc_url=os.environ["BSC_RPC"],
        registry_addr=REGISTRY_BSC,
        private_key=os.environ["AGENT_WALLET_PRIVATE_KEY"],
        agent_domain=os.environ.get("AGENT_DOMAIN", "sumplus.xyz"),
    )
    print(out)
