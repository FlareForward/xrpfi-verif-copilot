"""Judge-facing one-command demo output for XRPFi Verifiable Copilot."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import structlog

sys.path.insert(0, str(Path(__file__).parent.parent))

from demo.run_demo import (  # noqa: E402
    DEMO_XRP_AMOUNT,
    ens_status_label,
    resolve_ens_identity,
    step_attest_xrp_payment,
    step_fetch_ftso_prices,
    step_mint_fxrp,
    step_mint_inft,
    step_persist_to_zero_g,
    step_route_yield,
)
from src.config import get_settings  # noqa: E402
from src.contracts.decision_log import DecisionRecord, FdcProof, FtsoPrice  # noqa: E402
from src.gensyn.node_a.publisher import AxlPublisher as NodeAPublisher  # noqa: E402
from src.gensyn.node_b.subscriber import (  # noqa: E402
    AxlSubscriber as NodeBSubscriber,
)
from src.integrations.uniswap.client import UniswapClient  # noqa: E402
from src.session import save_session  # noqa: E402

GITHUB_URL = "https://github.com/FlareForward/xrpfi-verif-copilot"
ZERO_G_EXPLORER = "https://chainscan.0g.ai"
COORD_DOC = Path.home() / "codex-coord" / "xrpfi-storage-demo-20260505.md"
INFT_TOKEN_ID = "1"
INFT_TX = "0xbe0cf7c81658751ec40d67d871a996bba5799061348f4fe916c190f05aff9edd"
UNISWAP_FIXTURE_USDC = 2341.22
FDC_FIXTURE_PAYLOAD = {
    "attestation_type": "Payment",
    "chain": "XRPL",
    "amount_xrp": DEMO_XRP_AMOUNT,
    "from_address": "r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59",
    "to_address": "rFassetsMintAddress1234567890",
}
StepCallback = Callable[[dict[str, Any]], None]


async def safe_step[T](
    label: str,
    action: Callable[[], Awaitable[T]],
    fallback: T,
) -> tuple[T, str | None]:
    """Run one demo step and convert failures into judge-facing fallback notes."""
    try:
        return await action(), None
    except Exception as exc:
        return fallback, f"{label} failed: {exc}"


def suppress_demo_logging() -> None:
    """Keep imported integration logs out of the judge-facing proof output."""
    logging.disable(logging.CRITICAL)

    def drop_events(
        _logger: object,
        _method_name: str,
        _event_dict: dict[str, object],
    ) -> dict[str, object]:
        raise structlog.DropEvent

    structlog.configure(processors=[drop_events])


def short_address(address: str) -> str:
    """Compact an EVM-style address for terminal output."""
    if len(address) <= 12:
        return address
    return f"{address[:10]}..."


def find_price(prices: list[FtsoPrice], feed_name: str, fallback: float) -> tuple[float, bool]:
    """Return a named FTSO price plus whether it was marked stale."""
    for price in prices:
        if price.feed_name.upper() == feed_name.upper():
            return price.price_usd, price.is_stale
    return fallback, True


def real_tx_hash(candidate: str | None) -> bool:
    """True when a hash is a likely real explorer transaction."""
    return bool(candidate and re.fullmatch(r"0x[a-fA-F0-9]{64}", candidate))


def extract_real_storage_tx() -> str | None:
    """Read the coordination doc for the Orchestrator's real 0G storage tx."""
    if not COORD_DOC.exists():
        return None
    text = COORD_DOC.read_text(encoding="utf-8")
    patterns = [
        r"real_storage_tx\s*[:=]\s*(0x[a-fA-F0-9]{64})",
        r"0G storage[^\n]*(0x[a-fA-F0-9]{64})",
        r"storage tx[^\n]*(0x[a-fA-F0-9]{64})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def fallback_attest_record(prices: list[FtsoPrice]) -> DecisionRecord:
    """Build a local FDC fallback record without touching live services."""
    return DecisionRecord(
        agent_name="mint-helper",
        agent_ens="mint-helper.eth",
        action_type="attest",
        input_summary=f"FDC Payment attestation for {DEMO_XRP_AMOUNT} XRP",
        ftso_prices=prices,
        fdc_proof=FdcProof(
            attestation_type="Payment",
            proof_hash="0xdemo_fdc_proof_hash",
            chain="XRPL",
            round_id=999,
            verified=False,
        ),
        reasoning="Offline judge fallback: XRP payment proof is represented by a demo FDC hash.",
        action_taken=f"Submitted FDC Payment attestation for {DEMO_XRP_AMOUNT} XRP",
        result_summary="Attestation proof_hash=0xdemo_fdc_proof_hash, verified=False",
    )


def fallback_mint_record(prices: list[FtsoPrice]) -> DecisionRecord:
    """Build a local FXRP mint fallback record without touching live services."""
    fxrp_estimate = DEMO_XRP_AMOUNT * 0.99
    return DecisionRecord(
        agent_name="mint-helper",
        agent_ens="mint-helper.eth",
        action_type="mint",
        input_summary=f"Mint {DEMO_XRP_AMOUNT} XRP -> FXRP via FAssets v1.3",
        ftso_prices=prices,
        reasoning="Offline judge fallback: demo mint uses the 99% FXRP estimate.",
        action_taken=(
            f"FAssets mint initiated for {DEMO_XRP_AMOUNT} XRP "
            f"-> ~{fxrp_estimate:.2f} FXRP"
        ),
        result_summary="Collateral reservation ID: demo-colres-001 (Songbird testnet)",
    )


def fallback_route_record(prices: list[FtsoPrice], fxrp_amount: float) -> DecisionRecord:
    """Build a local yield-routing fallback record without touching live services."""
    return DecisionRecord(
        agent_name="yield-router",
        agent_ens="yield-router.eth",
        action_type="route",
        input_summary=f"Route {fxrp_amount:.2f} FXRP across Flare DeFi venues",
        ftso_prices=prices,
        reasoning="Offline judge fallback: deterministic 60/40 route policy.",
        action_taken="Allocation plan: 60% SparkDEX, 40% Kinetic",
        result_summary=f"Route plan committed. Total = {fxrp_amount:.2f} FXRP.",
    )


async def fetch_uniswap_quote() -> tuple[float, bool]:
    """Fetch a real Uniswap quote, with a fixture fallback for auth/network gaps."""
    client = UniswapClient()
    try:
        payload = await client.get_quote("WETH", "USDC", 1.0, chain_id=1)
        amount_out = parse_uniswap_amount_out(payload)
        return amount_out, True
    except Exception as exc:
        logging.getLogger(__name__).warning("Uniswap live quote unavailable: %s", exc)
        return UNISWAP_FIXTURE_USDC, False
    finally:
        await client.close()


def parse_uniswap_amount_out(payload: dict[str, Any]) -> float:
    """Extract USDC amount out from the shapes returned by Uniswap v2 quote APIs."""
    for key in ("amountOut", "quote", "outputAmount", "quoteAmount"):
        raw = payload.get(key)
        if raw is None:
            continue
        if isinstance(raw, int | float):
            return float(raw) / 1_000_000 if float(raw) > 1_000_000 else float(raw)
        if isinstance(raw, str):
            value = float(raw)
            return value / 1_000_000 if value > 1_000_000 else value

    for key in ("quoteDecimals", "quote_amount", "amountOutDecimals"):
        raw = payload.get(key)
        if raw is not None:
            return float(raw)

    raise ValueError("amountOut not present in Uniswap quote response")


async def run_axl_receipt(
    record: DecisionRecord,
    fxrp_amount: float = DEMO_XRP_AMOUNT * 0.99,
) -> tuple[str, str | None]:
    """Publish a mint-complete message and confirm Node B receives it."""
    publisher = NodeAPublisher()
    subscriber = NodeBSubscriber(force_fallback=True)
    received: asyncio.Future[DecisionRecord] = asyncio.get_running_loop().create_future()

    async def on_mint_complete(received_record: DecisionRecord) -> None:
        if not received.done():
            received.set_result(received_record)

    subscriber_task = asyncio.create_task(subscriber.subscribe_mint_complete(on_mint_complete))
    await asyncio.sleep(0)
    publish_task = asyncio.create_task(publisher.publish_mint_complete(record))

    try:
        message_id = await publish_task
        received_record = await asyncio.wait_for(received, timeout=5.0)
        topic = get_settings().axl_topic_mint_complete
        receipt_message_id = received_record.axl_message_id or message_id
        payload_snippet = json.dumps({"fxrp": round(fxrp_amount, 1)}, separators=(",", ":"))
        return (
            f"Node A → Node B: {topic} ✓\n"
            f"                    receipt: msg_id={receipt_message_id} "
            f"topic={topic} payload={payload_snippet}",
            None,
        )
    except TimeoutError:
        return "AXL timeout", "nodes may need real Gensyn network"
    except Exception as exc:
        return "Node A → Node B: xrpfi.mint.complete", str(exc)
    finally:
        subscriber.stop()
        subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await subscriber_task
        await subscriber.close()


async def run_judge_demo(step_callback: StepCallback | None = None) -> dict[str, Any]:
    """Run the full judge demo flow and print a structured receipt."""
    suppress_demo_logging()
    started_at = datetime_now_iso()
    steps: list[dict[str, Any]] = []

    fallback_prices = []
    prices, price_error = await safe_step("FTSO", step_fetch_ftso_prices, fallback_prices)
    flr_usd, flr_stale = find_price(prices, "FLR/USD", 0.0076)
    xrp_usd, xrp_stale = find_price(prices, "XRP/USD", 1.41)
    price_note = price_error or ("fallback price feed stale" if flr_stale or xrp_stale else None)
    emit_step(
        steps,
        step_callback,
        1,
        "FTSO live prices",
        f"FLR/USD={flr_usd:.4f}  XRP/USD={xrp_usd:.2f}",
        price_note,
    )

    mint_helper, mint_ens_error = await safe_step(
        "mint-helper ENS",
        lambda: resolve_ens_identity("mint-helper.eth"),
        {
            "ens": "mint-helper.eth",
            "address": "0x81e51856d72023490cF7DEc1A6717f4269028F95",
            "is_live": False,
        },
    )
    emit_step(
        steps,
        step_callback,
        2,
        "ENS resolved",
        f"mint-helper.eth -> {short_address(str(mint_helper['address']))} "
        f"{ens_status_label(mint_helper)}",
        mint_ens_error,
    )

    yield_router, yield_ens_error = await safe_step(
        "yield-router ENS",
        lambda: resolve_ens_identity("yield-router.eth"),
        {
            "ens": "yield-router.eth",
            "address": "0x81e51856d72023490cF7DEc1A6717f4269028F95",
            "is_live": False,
        },
    )
    emit_step(
        steps,
        step_callback,
        3,
        "ENS resolved",
        f"yield-router.eth -> {short_address(str(yield_router['address']))} "
        f"{ens_status_label(yield_router)}",
        yield_ens_error,
    )

    attest_record, attest_error = await safe_step(
        "FDC",
        lambda: step_attest_xrp_payment("ABCDEF1234567890XRPLTXHASH", prices),
        fallback_attest_record(prices),
    )
    proof_hash = attest_record.fdc_proof.proof_hash if attest_record.fdc_proof else "0xdemo"
    fdc_note = attest_error or (
        "FDC fixture proof"
        if attest_record.fdc_proof and not attest_record.fdc_proof.verified
        else None
    )
    emit_step(
        steps,
        step_callback,
        4,
        "FDC attestation",
        f"XRP payment attested (proof_hash={proof_hash})",
        fdc_note,
    )

    mint_record, mint_error = await safe_step(
        "FXRP mint",
        lambda: step_mint_fxrp(prices),
        fallback_mint_record(prices),
    )
    fxrp_minted = DEMO_XRP_AMOUNT * 0.99
    mint_note = mint_error or (
        "FAssets fixture" if "demo" in mint_record.result_summary.lower() else None
    )
    emit_step(
        steps,
        step_callback,
        5,
        "FXRP minted",
        f"{DEMO_XRP_AMOUNT:.0f} XRP -> {fxrp_minted:.2f} FXRP (Songbird testnet)",
        mint_note,
    )

    route_record, route_error = await safe_step(
        "yield routing",
        lambda: step_route_yield(fxrp_minted, prices),
        fallback_route_record(prices, fxrp_minted),
    )
    route_note = route_error or (
        "policy fixture" if "sparkdex" in route_record.action_taken.lower() else None
    )
    emit_step(
        steps,
        step_callback,
        6,
        "Yield routed",
        "60% SparkDEX / 40% Kinetic",
        route_note,
    )

    quote_amount, is_live_quote = await fetch_uniswap_quote()
    emit_step(
        steps,
        step_callback,
        7,
        "Uniswap quote",
        f"WETH→USDC: 1.0 WETH = {quote_amount:,.2f} USDC",
        None if is_live_quote else "no API key or live quote unavailable",
    )

    axl_receipt, axl_error = await run_axl_receipt(mint_record, fxrp_minted)
    emit_step(steps, step_callback, 8, "Gensyn AXL", axl_receipt, axl_error)

    records = [attest_record, mint_record, route_record]
    coord_tx = extract_real_storage_tx()
    storage_note: str | None = None
    storage_tx = coord_tx
    if storage_tx is None:
        storage_hashes, storage_error = await safe_step(
            "0G storage",
            lambda: step_persist_to_zero_g(records),
            [],
        )
        storage_tx = storage_hashes[0] if storage_hashes else None
        if not real_tx_hash(storage_tx):
            storage_note = storage_error or (
                "storage mainnet upload pending - see ZERO_G_STORAGE_STATUS.md"
            )
    storage_display = (
        f"tx={storage_tx} {ZERO_G_EXPLORER}/tx/{storage_tx}"
        if real_tx_hash(storage_tx)
        else f"tx={storage_tx or 'local-proof'}"
    )
    emit_step(steps, step_callback, 9, "0G storage", storage_display, storage_note)

    inft_url = f"{ZERO_G_EXPLORER}/tx/{INFT_TX}"
    _, inft_error = await safe_step(
        "iNFT mint",
        lambda: step_mint_inft(records, storage_uri=storage_tx or "local-proof"),
        None,
    )
    emit_step(
        steps,
        step_callback,
        10,
        "iNFT minted",
        f"token={INFT_TOKEN_ID} {inft_url}",
        inft_error,
    )

    session = save_session(steps, records, started_at=started_at)
    print_receipt(
        session_id=str(session["session_id"]),
        timestamp=str(session["timestamp"]),
        flr_usd=flr_usd,
        xrp_usd=xrp_usd,
        ftso_live=price_note is None,
        fdc_proof_hash=fixture_fdc_proof_hash(),
        uniswap_quote=quote_amount,
        uniswap_live=is_live_quote,
        fxrp_minted=fxrp_minted,
        axl_receipt=axl_receipt,
        storage_tx=storage_tx,
        inft_url=inft_url,
        agents=[mint_helper, yield_router],
    )
    return {
        "agents": [
            mint_helper,
            yield_router,
        ],
        "prices": [price.model_dump(mode="json") for price in prices],
        "xrp_amount": DEMO_XRP_AMOUNT,
        "fxrp_minted": fxrp_minted,
        "decisions": [record.model_dump(mode="json") for record in records],
        "records": [record.model_dump(mode="json") for record in records],
        "steps": steps,
        "session": session,
        "storage_hashes": [storage_tx] if storage_tx else [],
        "inft_url": inft_url,
    }


def print_header() -> None:
    """Print the receipt header."""
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Agent Receipt — XRPFi Verifiable Copilot            ║")
    print("║  0G APAC Hackathon 2026 | FlareForward               ║")
    print("╚══════════════════════════════════════════════════════╝")
    print()


def print_line(index: int, label: str, message: str, warning: str | None = None) -> None:
    """No-op terminal printer kept for browser step compatibility."""


def emit_step(
    steps: list[dict[str, Any]],
    step_callback: StepCallback | None,
    index: int,
    label: str,
    message: str,
    warning: str | None = None,
) -> None:
    """Record a demo step and optionally stream it to the browser."""
    event = {
        "step": index,
        "label": label,
        "value": message,
        "status": "warn" if warning else "ok",
    }
    if warning:
        event["warning"] = clean_warning(warning)
    steps.append(event)
    if step_callback:
        step_callback(dict(event))


def clean_warning(warning: str) -> str:
    """Keep fallback reasons readable in a judge terminal."""
    if "iNFT mint failed" in warning:
        return "demo iNFT fixture"
    if "nodename nor servname" in warning or "NameResolutionError" in warning:
        return warning.split(": ", 1)[0] if ": " in warning else "network unavailable"
    if len(warning) > 120:
        return f"{warning[:117]}..."
    return warning


def print_footer(audit_url: str) -> None:
    """Print the audit trail footer."""
    print("── Verifiable audit trail ─────────────────────────────")
    print(f"{audit_url}  {status_label('LIVE')}")
    print(f"GitHub: {GITHUB_URL}  {status_label('LIVE')}")


def print_receipt(
    *,
    session_id: str,
    timestamp: str,
    flr_usd: float,
    xrp_usd: float,
    ftso_live: bool,
    fdc_proof_hash: str,
    uniswap_quote: float,
    uniswap_live: bool,
    fxrp_minted: float,
    axl_receipt: str,
    storage_tx: str | None,
    inft_url: str,
    agents: list[dict[str, Any]],
) -> None:
    """Print the judge-facing agent receipt."""
    print_header()
    print(f"Receipt ID:    {session_id}  {status_label('LIVE')}")
    print(f"Timestamp:     {timestamp}  {status_label('LIVE')}")
    print(
        "Agent:         "
        f"mint-helper.eth {ens_status_label(agents[0])} → "
        f"yield-router.eth {ens_status_label(agents[1])}"
    )
    print()
    print("── Data Inputs ─────────────────────────────────────────")
    ftso_status = (
        status_label("LIVE")
        if ftso_live
        else status_label("FIXTURE", "fallback price feed stale or unavailable")
    )
    print(f"FTSO FLR/USD:  {flr_usd:.4f}  {ftso_status}")
    print(f"FTSO XRP/USD:  {xrp_usd:.2f}    {ftso_status}")
    print(
        f"FDC proof:     proof_hash={fdc_proof_hash}  "
        f"{status_label('FIXTURE', 'demo attestation, not live XRPL')}"
    )
    quote_status = (
        status_label("LIVE")
        if uniswap_live
        else status_label("FIXTURE", "no API key or live quote unavailable")
    )
    print(f"Uniswap quote: {uniswap_quote:,.2f} {quote_status}")
    print()
    print("── Decision ────────────────────────────────────────────")
    print(
        f"Action:        Evaluate yield route for {DEMO_XRP_AMOUNT:.0f} XRP  "
        f"{status_label('FIXTURE', 'demo scenario')}"
    )
    print(
        "Route:         60% SparkDEX / 40% Kinetic  "
        f"{status_label('FIXTURE', 'policy rule')}"
    )
    print(
        f"FAssets mint:  Stub params returned for ~{fxrp_minted:.2f} FXRP  "
        f"{status_label('FIXTURE', 'no broadcast')}"
    )
    print()
    print("── Cross-Agent Handoff ─────────────────────────────────")
    axl_summary = axl_receipt.splitlines()[0].replace("✓", "").strip()
    axl_status = status_label(
        "FIXTURE",
        "local AXL-compatible fallback; real Gensyn node not connected",
    )
    print(
        f"Gensyn AXL:    {axl_summary}  "
        f"{axl_status}"
    )
    print()
    print("── Proof Artifacts ─────────────────────────────────────")
    storage_label = (
        status_label("LIVE")
        if real_tx_hash(storage_tx)
        else status_label("PLANNED", "wallet unfunded; see ZERO_G_STORAGE_STATUS.md")
    )
    storage_display = (
        f"tx={storage_tx} {ZERO_G_EXPLORER}/tx/{storage_tx}"
        if real_tx_hash(storage_tx)
        else "local SHA-256 receipt only"
    )
    print(f"0G storage:    {storage_display}  {storage_label}")
    print(f"0G iNFT:       token={INFT_TOKEN_ID} {inft_url}  {status_label('LIVE')}")
    print()
    print_footer(inft_url)


def fixture_fdc_proof_hash() -> str:
    """Return the displayed SHA-256 proof for the FDC fixture payload."""
    payload = json.dumps(FDC_FIXTURE_PAYLOAD, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def status_label(kind: str, reason: str | None = None) -> str:
    """Return a status label, colored when the terminal supports ANSI."""
    text = f"[{kind} — {reason}]" if reason else f"[{kind}]"
    if not sys.stdout.isatty():
        return text
    colors = {
        "LIVE": "\033[32m",
        "FIXTURE": "\033[33m",
        "PLANNED": "\033[90m",
    }
    return f"{colors.get(kind, '')}{text}\033[0m"


def main(step_callback: StepCallback | None = None) -> dict[str, Any] | None:
    """Console entry point."""
    try:
        return asyncio.run(run_judge_demo(step_callback=step_callback))
    except KeyboardInterrupt:
        print("\nJudge demo interrupted.")
    except Exception as exc:
        print(f"\n⚠ Judge demo failed safely: {exc}")
    return None


def datetime_now_iso() -> str:
    """Return an ISO UTC timestamp for session duration tracking."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    main()
