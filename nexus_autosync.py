"""
nexus_autosync.py
=================
Maya-Morphe P1 — Auto Commit + Push to GitHub
Nexus Learning Labs | ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

Runs at the start of every session and before every push.
Stages all changes, commits with a timestamped message,
and pushes to origin.

Usage:
  python nexus_autosync.py              — commit + push all changes
  python nexus_autosync.py --check      — check git status only
  python nexus_autosync.py --msg "..."  — custom commit message

Standards:
  - Always runs verify_provenance first
  - Checks LICENSE, CITATION.cff, verify_provenance.py exist
  - Checks ORCID magic number in constants.py
  - Never pushes if IP checks fail
  - Uses semicolons not && (PowerShell standard)
"""

import sys
import os
import subprocess
import datetime
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verify_provenance
verify_provenance.stamp()

from src.morphe.constants import CANARY, VAIRAGYA_DECAY_RATE

# ── CONFIG ────────────────────────────────────────────────────────

REQUIRED_FILES = [
    "LICENSE",
    "CITATION.cff",
    "verify_provenance.py",
    "sign_paper.py",
    "README.md",
    "dashboard.html",
    "docs/faq.html",
    "src/morphe/constants.py",
    "experiments/run_lizard_v5.py",
    "experiments/run_ablation.py",
]

ORCID_MAGIC = "0.002315"

# ── IP CHECKS ─────────────────────────────────────────────────────

def check_ip_stack() -> bool:
    """Verify all IP protection layers before pushing."""
    ok = True
    print("\n[IP CHECK] Verifying IP protection stack...")

    # Check required files exist
    for f in REQUIRED_FILES:
        if os.path.exists(f):
            print(f"  [OK] {f}")
        else:
            print(f"  [MISS] {f} — REQUIRED")
            ok = False

    # Check LICENSE contains ORCID
    try:
        with open("LICENSE", encoding="utf-8") as f:
            lic = f.read()
        if "0000-0002-3315-7907" in lic:
            print(f"  [OK] LICENSE contains ORCID")
        else:
            print(f"  [FAIL] LICENSE missing ORCID")
            ok = False
    except Exception as e:
        print(f"  [FAIL] LICENSE read error: {e}")
        ok = False

    # Check ORCID magic in constants
    try:
        with open("src/morphe/constants.py", encoding="utf-8") as f:
            consts = f.read()
        if ORCID_MAGIC in consts:
            print(f"  [OK] ORCID magic {ORCID_MAGIC} in constants.py")
        else:
            print(f"  [FAIL] ORCID magic {ORCID_MAGIC} missing from constants.py")
            ok = False
    except Exception as e:
        print(f"  [FAIL] constants.py read error: {e}")
        ok = False

    # Check canary in run scripts
    for script in ["experiments/run_lizard_v5.py", "experiments/run_ablation.py"]:
        try:
            with open(script, encoding="utf-8") as f:
                content = f.read()
            if CANARY in content or "Narasimha" in content:
                print(f"  [OK] Canary in {script}")
            else:
                print(f"  [WARN] Canary missing from {script}")
        except Exception:
            print(f"  [WARN] Could not read {script}")

    return ok

# ── GIT OPERATIONS ────────────────────────────────────────────────

def run_git(args: list, capture: bool = False) -> tuple[int, str]:
    """Run a git command and return (returncode, output)."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, encoding="utf-8"
    )
    if capture:
        return result.returncode, (result.stdout + result.stderr).strip()
    return result.returncode, ""

def check_status() -> bool:
    """Print git status and return True if there are changes."""
    code, out = run_git(["status", "--short"], capture=True)
    if out.strip():
        print(f"\n[GIT STATUS]\n{out}")
        return True
    else:
        print("\n[GIT] Working tree clean — nothing to commit")
        return False

def sync(message: str | None = None) -> bool:
    """Stage, commit, and push all changes."""
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = message or f"sync: Maya-Morphe P1 autosync {ts} | {CANARY}"

    print(f"\n[SYNC] Staging all changes...")
    code, _ = run_git(["add", "-A"])
    if code != 0:
        print("[ERROR] git add failed")
        return False

    # Check if there's anything to commit
    code, status = run_git(["status", "--short"], capture=True)
    if not status.strip():
        print("[SYNC] Nothing to commit — already up to date")
        # Still push in case remote is behind
    else:
        print(f"[SYNC] Committing: {msg}")
        code, out = run_git(["commit", "-m", msg], capture=True)
        if code != 0:
            print(f"[ERROR] git commit failed:\n{out}")
            return False
        print(f"[OK]   Committed")

    # Check current branch
    code, branch = run_git(["branch", "--show-current"], capture=True)
    branch = branch.strip() or "master"
    print(f"[SYNC] Pushing to origin/{branch}...")

    code, out = run_git(["push", "origin", branch], capture=True)
    if code != 0:
        # Try fetch first
        print("[SYNC] Push failed — trying fetch first...")
        run_git(["fetch", "origin"])
        code, out = run_git(["push", "origin", branch], capture=True)
        if code != 0:
            print(f"[ERROR] Push failed:\n{out}")
            return False

    print(f"[OK]   Pushed to origin/{branch}")
    return True

# ── MAIN ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Maya-Morphe P1 — Auto commit + push to GitHub"
    )
    parser.add_argument("--check", action="store_true",
                        help="Check git status only — do not commit or push")
    parser.add_argument("--msg", type=str, default=None,
                        help="Custom commit message")
    parser.add_argument("--skip-ip", action="store_true",
                        help="Skip IP checks (not recommended)")
    args = parser.parse_args()

    print("=" * 60)
    print("NEXUS AUTOSYNC — Maya-Morphe P1")
    print(f"ORCID: 0000-0002-3315-7907 | UDYAM-KR-02-0122422")
    print(f"Canary: {CANARY}")
    print("=" * 60)

    # IP check
    if not args.skip_ip:
        ip_ok = check_ip_stack()
        if not ip_ok:
            print("\n[ABORT] IP checks failed. Fix issues before pushing.")
            print("[HINT]  Run with --skip-ip to bypass (not recommended)")
            sys.exit(1)
        print("\n[IP CHECK] All layers verified ✓")

    # Status only
    if args.check:
        check_status()
        sys.exit(0)

    # Sync
    has_changes = check_status()
    ok = sync(args.msg)

    if ok:
        print("\n[DONE] Sync complete")
        print(f"[DONE] Repo: https://github.com/venky2099/Maya-Morphe-P1")
        print(f"[DONE] {CANARY}")
    else:
        print("\n[FAIL] Sync failed — check errors above")
        sys.exit(1)

if __name__ == "__main__":
    main()
