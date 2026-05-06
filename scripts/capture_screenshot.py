"""Generate a static UI mockup PNG for docs/screenshots/ui-demo.png.

Uses only stdlib (struct + zlib) — no Pillow required.
Run: uv run python scripts/capture_screenshot.py
"""

import struct
import zlib
from pathlib import Path

WIDTH = 1200
HEIGHT = 800

# Colour palette (r, g, b)
BG = (10, 10, 15)
HEADER_BG = (15, 15, 30)
CARD_BG = (20, 20, 35)
ACCENT = (99, 102, 241)   # indigo #6366f1
SUCCESS = (16, 185, 129)  # green #10b981
WARNING = (245, 158, 11)  # amber
TEXT = (226, 232, 240)    # slate-200
MUTED = (100, 116, 139)   # slate-500
WHITE = (255, 255, 255)


def _rgb(r: int, g: int, b: int) -> bytes:
    return bytes([r, g, b])


def make_canvas() -> list[list[bytes]]:
    """Return HEIGHT rows of WIDTH RGB pixels."""
    return [[_rgb(*BG)] * WIDTH for _ in range(HEIGHT)]


def fill_rect(
    canvas: list[list[bytes]],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    colour: tuple[int, int, int],
) -> None:
    px = _rgb(*colour)
    for y in range(max(0, y0), min(HEIGHT, y1)):
        for x in range(max(0, x0), min(WIDTH, x1)):
            canvas[y][x] = px


def draw_text_block(
    canvas: list[list[bytes]],
    x: int,
    y: int,
    char_w: int,
    char_h: int,
    text: str,
    colour: tuple[int, int, int],
) -> None:
    """Draw text as coloured pixel blocks (bitmap font simulation)."""
    col = x
    for ch in text:
        if ch == " ":
            col += char_w + 2
            continue
        fill_rect(canvas, col, y, col + char_w, y + char_h, colour)
        col += char_w + 2
        if col > WIDTH - char_w:
            break


def encode_png(canvas: list[list[bytes]]) -> bytes:
    """Encode pixel canvas as a valid PNG bytestring."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    raw_rows = b""
    for row in canvas:
        raw_rows += b"\x00" + b"".join(row)

    idat = chunk(b"IDAT", zlib.compress(raw_rows, 6))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def render() -> None:
    canvas = make_canvas()

    # ── Header bar
    fill_rect(canvas, 0, 0, WIDTH, 56, HEADER_BG)
    fill_rect(canvas, 0, 56, WIDTH, 58, ACCENT)

    # Title text simulation (thick blocks)
    draw_text_block(canvas, 24, 16, 10, 24, "XRPFiVerifiableCopilot", WHITE)

    # Ticker strip (right side)
    fill_rect(canvas, 850, 14, 1160, 42, (18, 18, 40))
    draw_text_block(canvas, 860, 20, 6, 16, "FLR/USD0.0076", SUCCESS)
    draw_text_block(canvas, 1010, 20, 6, 16, "XRP/USD1.41", SUCCESS)

    # ── Hero section
    fill_rect(canvas, 0, 58, WIDTH, 160, BG)
    # "Run Judge Demo" button
    fill_rect(canvas, 450, 80, 750, 132, ACCENT)
    draw_text_block(canvas, 490, 95, 9, 22, "RunJudgeDemo", WHITE)

    # ── Steps panel
    step_labels = [
        ("[1] FTSO prices", SUCCESS),
        ("[2] ENS mint-helper.eth", SUCCESS),
        ("[3] ENS yield-router.eth", SUCCESS),
        ("[4] FDC attestation", SUCCESS),
        ("[5] FXRP minted", SUCCESS),
        ("[6] Yield routed", SUCCESS),
        ("[7] Uniswap quote", WARNING),
        ("[8] Gensyn AXL", SUCCESS),
        ("[9] 0G storage", WARNING),
        ("[10] iNFT minted", SUCCESS),
    ]

    panel_x, panel_y = 40, 170
    fill_rect(canvas, panel_x, panel_y, panel_x + 540, panel_y + 570, CARD_BG)

    for i, (label, colour) in enumerate(step_labels):
        row_y = panel_y + 16 + i * 52
        fill_rect(canvas, panel_x + 12, row_y, panel_x + 528, row_y + 40, HEADER_BG)
        # Status dot
        fill_rect(canvas, panel_x + 20, row_y + 10, panel_x + 34, row_y + 30, colour)
        draw_text_block(canvas, panel_x + 44, row_y + 12, 5, 16, label, TEXT)

    # ── Decision cards panel
    card_x, card_y = 620, 170
    fill_rect(canvas, card_x, card_y, card_x + 540, card_y + 570, CARD_BG)
    draw_text_block(canvas, card_x + 16, card_y + 16, 7, 18, "DecisionRecords", TEXT)

    for i in range(4):
        cy = card_y + 52 + i * 124
        fill_rect(canvas, card_x + 12, cy, card_x + 528, cy + 112, HEADER_BG)
        fill_rect(canvas, card_x + 12, cy, card_x + 528, cy + 28, (25, 25, 50))
        label = f"mint-helper.eth Decision{i + 1}"
        draw_text_block(canvas, card_x + 20, cy + 6, 5, 16, label, ACCENT)
        draw_text_block(canvas, card_x + 20, cy + 38, 4, 12, "FLR/USD0.0076XRP/USD1.41", MUTED)
        draw_text_block(canvas, card_x + 20, cy + 60, 4, 12, "action:InitiateFXRPMint100XRP", TEXT)
        fill_rect(canvas, card_x + 20, cy + 84, card_x + 120, cy + 104, (20, 60, 40))
        draw_text_block(canvas, card_x + 24, cy + 88, 4, 12, "0Gstored", SUCCESS)

    # ── Footer
    fill_rect(canvas, 0, HEIGHT - 40, WIDTH, HEIGHT, HEADER_BG)
    draw_text_block(canvas, 24, HEIGHT - 28, 4, 14, "0GAPACHackathon2026|FlareForward", MUTED)
    footer_link = "github.com/FlareForward/xrpfi-verif-copilot"
    draw_text_block(canvas, 900, HEIGHT - 28, 4, 14, footer_link, MUTED)

    out = Path(__file__).parent.parent / "docs" / "screenshots" / "ui-demo.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(encode_png(canvas))
    size_kb = out.stat().st_size // 1024
    print(f"Screenshot saved to {out}  ({size_kb} KB)")


if __name__ == "__main__":
    render()
