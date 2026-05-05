"""Shared configuration for all agents and integrations."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration — populated from environment variables."""

    # Flare network
    flare_rpc_url: str = Field(
        default="https://coston2-api.flare.network/ext/C/rpc",
        description="Flare EVM RPC endpoint (Coston2 testnet default)",
    )
    songbird_rpc_url: str = Field(
        default="https://songbird-api.flare.network/ext/C/rpc",
        description="Songbird RPC for FAssets v1.3 testing",
    )

    # Google AI (ADK + Gemini)
    google_api_key: str = Field(default="", description="Google AI Studio API key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Default Gemini model")

    # ENS
    eth_rpc_url: str = Field(
        default="https://mainnet.infura.io/v3/",
        description="Ethereum mainnet RPC for ENS resolution",
    )
    eth_sepolia_rpc_url: str = Field(
        default="https://sepolia.infura.io/v3/",
        description="Ethereum Sepolia for ENS testnet registration",
    )

    # 0G storage
    zero_g_storage_url: str = Field(
        default="https://indexer-storage-turbo.0g.ai",
        description="0G storage node endpoint",
    )
    zero_g_rpc_url: str = Field(
        default="https://0g-rpc.publicnode.com",
        description="0G EVM RPC endpoint (mainnet default)",
    )
    zero_g_chain_id: int = Field(default=16661, description="0G chain ID (16661 = mainnet)")
    zero_g_flow_contract: str = Field(
        default="0x62D4144dB0F0a6fBBaeb6296c785C71B3D57C526",
        description="0G mainnet Flow contract for storage uploads",
    )
    zero_g_explorer: str = Field(
        default="https://chainscan.0g.ai",
        description="0G block explorer base URL",
    )
    zero_g_private_key: str | None = Field(default=None, description="0G deployer key")
    zero_g_inft_contract: str | None = Field(
        default=None, description="Deployed XRPFiINFT contract address on 0G"
    )

    # Uniswap
    uniswap_api_url: str = Field(
        default="https://api.uniswap.org/v2",
        description="Uniswap Trading API base URL",
    )
    uniswap_api_key: str | None = Field(default=None, description="Uniswap API key if required")

    # Gensyn AXL
    axl_node_a_endpoint: str = Field(
        default="http://localhost:8765",
        description="Gensyn AXL node A endpoint",
    )
    axl_node_b_endpoint: str = Field(
        default="http://localhost:8766",
        description="Gensyn AXL node B endpoint",
    )
    axl_topic_mint_complete: str = Field(
        default="xrpfi.mint.complete",
        description="AXL topic: Agent A publishes after FXRP mint",
    )
    axl_topic_route_plan: str = Field(
        default="xrpfi.route.plan",
        description="AXL topic: Agent B publishes yield route plan",
    )

    # Agent signing key (testnet only — never mainnet)
    agent_private_key: str | None = Field(default=None, description="Testnet-only signing key")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
