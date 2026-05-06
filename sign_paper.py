"""
sign_paper.py
=============
LSB Steganographic Signature for Maya-Morphe Paper 1 Figures
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

Embeds a tamper-evident signature into the least significant bits of
every matplotlib figure PNG. The signature encodes:
  - ORCID: 0000-0002-3315-7907
  - DOI: 10.5281/zenodo.XXXXXXX (update after Zenodo upload)
  - Institution: Nexus Learning Labs Bengaluru
  - Canary: MayaNexusVS2026NLL_Bengaluru_Narasimha
  - Timestamp: ISO 8601

Usage:
  # Sign a single figure
  python sign_paper.py figures/fig1_frr_curve.png

  # Sign all figures in the figures/ directory
  python sign_paper.py --all

  # Verify a signed figure
  python sign_paper.py --verify figures/fig1_frr_curve_signed.png

Output: figures/[name]_signed.png

The signature is invisible to the human eye. It survives JPEG
compression at quality >= 95. It does NOT survive heavy JPEG
compression, cropping, or resampling — which is intentional,
as those operations indicate deliberate manipulation.

IP Protection Layer 6 — mandatory before Zenodo.
"""

import sys
import os
import struct
import datetime
import argparse
import numpy as np

# ── SIGNATURE PAYLOAD ─────────────────────────────────────────────

ORCID       = "0000-0002-3315-7907"
DOI         = "10.5281/zenodo.XXXXXXX"   # UPDATE after Zenodo upload
INSTITUTION = "Nexus Learning Labs Bengaluru"
CANARY      = "MayaNexusVS2026NLL_Bengaluru_Narasimha"
SERIES      = "Maya-Morphe Series 3 Paper 1"

def build_signature() -> str:
    """Build the full signature string to embed."""
    ts = datetime.datetime.utcnow().isoformat()
    return (
        f"ORCID:{ORCID}|"
        f"DOI:{DOI}|"
        f"INST:{INSTITUTION}|"
        f"SERIES:{SERIES}|"
        f"CANARY:{CANARY}|"
        f"TS:{ts}"
    )

# ── LSB ENCODING / DECODING ───────────────────────────────────────

MAGIC = b"NLLSIG1"   # 7-byte magic header to identify signed images

def _str_to_bits(s: str) -> list:
    """Convert string to list of bits."""
    bits = []
    for byte in s.encode("utf-8"):
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def _bits_to_str(bits: list) -> str:
    """Convert list of bits back to string."""
    chars = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        if byte == 0:
            break
        chars.append(chr(byte))
    return "".join(chars)

def _bytes_to_bits(b: bytes) -> list:
    """Convert bytes to list of bits (8 bits per byte)."""
    bits = []
    for byte in b:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits

def embed_signature(img_array: np.ndarray, signature: str) -> np.ndarray:
    """
    Embed signature into LSB of the blue channel.
    Format: MAGIC (7 bytes) + length (4 bytes, big-endian) + payload bits
    """
    arr = img_array.copy()
    flat = arr[:, :, 2].flatten().astype(np.int32)

    # Build full payload as raw bytes
    sig_bytes  = signature.encode("utf-8")
    length     = len(sig_bytes)
    header     = MAGIC + struct.pack(">I", length)
    all_bits   = _bytes_to_bits(header) + _bytes_to_bits(sig_bytes)

    if len(all_bits) > len(flat):
        raise ValueError(
            f"Signature too long ({len(all_bits)} bits) for image "
            f"({len(flat)} pixels). Use a larger figure."
        )

    # Embed bits into LSB
    for i, bit in enumerate(all_bits):
        flat[i] = (int(flat[i]) & 0xFE) | bit

    arr[:, :, 2] = flat.reshape(arr[:, :, 2].shape).astype(np.uint8)
    return arr

def extract_signature(img_array: np.ndarray) -> str | None:
    """
    Extract LSB signature from blue channel.
    Returns None if no valid signature found.
    """
    flat = img_array[:, :, 2].flatten()

    # Read magic (7 bytes = 56 bits) + length (4 bytes = 32 bits) = 88 bits total
    header_bits = [(int(flat[i]) & 1) for i in range(88)]

    # Reconstruct header bytes directly from bits
    header_bytes = bytearray()
    for i in range(0, 88, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | header_bits[i + j]
        header_bytes.append(byte)

    if bytes(header_bytes[:7]) != MAGIC:
        return None

    length = struct.unpack(">I", bytes(header_bytes[7:11]))[0]
    if length > 10000 or length == 0:
        return None

    # Read payload bits
    total_bits = 88 + length * 8
    if total_bits > len(flat):
        return None

    payload_bytes = bytearray()
    for i in range(88, total_bits, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | (int(flat[i + j]) & 1)
        payload_bytes.append(byte)

    try:
        return payload_bytes.decode("utf-8")
    except Exception:
        return None

# ── FILE OPERATIONS ───────────────────────────────────────────────

def sign_file(input_path: str, output_path: str | None = None) -> str:
    """Sign a PNG figure and save the signed version."""
    try:
        from PIL import Image
    except ImportError:
        print("[ERROR] Pillow not installed. Run: pip install pillow")
        sys.exit(1)

    if not os.path.exists(input_path):
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)

    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)

    if arr.shape[2] < 3:
        print(f"[ERROR] Image must have at least 3 channels: {input_path}")
        sys.exit(1)

    sig = build_signature()
    print(f"[sign] Embedding signature ({len(sig)} chars) into {input_path}")
    print(f"[sign] ORCID:  {ORCID}")
    print(f"[sign] DOI:    {DOI}")
    print(f"[sign] Canary: {CANARY}")

    signed_arr = embed_signature(arr, sig)
    signed_img = Image.fromarray(signed_arr)

    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = base + "_signed.png"

    signed_img.save(output_path, format="PNG")
    print(f"[sign] Saved: {output_path}")
    return output_path

def verify_file(path: str) -> bool:
    """Verify LSB signature in a signed figure."""
    try:
        from PIL import Image
    except ImportError:
        print("[ERROR] Pillow not installed.")
        return False

    img = Image.open(path).convert("RGBA")
    arr = np.array(img)
    sig = extract_signature(arr)

    if sig is None:
        print(f"[FAIL] No valid signature found in: {path}")
        return False

    print(f"[OK]   Signature verified in: {path}")
    parts = dict(p.split(":", 1) for p in sig.split("|") if ":" in p)
    for k, v in parts.items():
        print(f"       {k:8s} = {v}")
    return True

def sign_all_figures(figures_dir: str = "figures") -> int:
    """Sign all PNG files in the figures directory."""
    if not os.path.exists(figures_dir):
        print(f"[WARN] figures/ directory not found — creating it")
        os.makedirs(figures_dir)
        print(f"[INFO] Place your matplotlib figures in {figures_dir}/ and run again")
        return 0

    pngs = [f for f in os.listdir(figures_dir)
            if f.endswith(".png") and "_signed" not in f]

    if not pngs:
        print(f"[INFO] No unsigned PNGs found in {figures_dir}/")
        return 0

    count = 0
    for fname in pngs:
        inp = os.path.join(figures_dir, fname)
        try:
            sign_file(inp)
            count += 1
        except Exception as e:
            print(f"[ERROR] Failed to sign {fname}: {e}")

    print(f"\n[done] Signed {count}/{len(pngs)} figures")
    return count

# ── MAIN ─────────────────────────────────────────────────────────

def main():
    import verify_provenance
    verify_provenance.stamp()

    parser = argparse.ArgumentParser(
        description="LSB steganographic signature for Maya-Morphe figures"
    )
    parser.add_argument("input", nargs="?", help="Input PNG file to sign")
    parser.add_argument("--all", action="store_true",
                        help="Sign all PNGs in figures/ directory")
    parser.add_argument("--verify", metavar="FILE",
                        help="Verify signature in a signed PNG")
    parser.add_argument("--output", "-o", metavar="FILE",
                        help="Output path for signed file")
    args = parser.parse_args()

    if args.verify:
        ok = verify_file(args.verify)
        sys.exit(0 if ok else 1)
    elif args.all:
        sign_all_figures()
    elif args.input:
        sign_file(args.input, args.output)
    else:
        parser.print_help()
        print("\n[INFO] Usage examples:")
        print("  python sign_paper.py figures/fig1_frr.png")
        print("  python sign_paper.py --all")
        print("  python sign_paper.py --verify figures/fig1_frr_signed.png")

if __name__ == "__main__":
    main()
