"""
verify_provenance.py
Nexus Learning Labs — Maya-Morphe Series
ORCID: 0000-0002-3315-7907
MayaNexusVS2026NLL_Bengaluru_Narasimha

Wired into every run script. Refuses to execute if IP signatures are missing.
"""
import os
import sys
import socket
import datetime

CANARY = "MayaNexusVS2026NLL_Bengaluru_Narasimha"
ORCID = "0000-0002-3315-7907"
MAGIC = "0.002315"
LOG_FILE = ".maya_provenance.log"

def stamp():
    _check_license()
    _check_constants()
    _write_log()
    print(f"[provenance] {CANARY} | ORCID: {ORCID} | {datetime.datetime.now().isoformat()}")

def _check_license():
    lic_path = os.path.join(os.path.dirname(__file__), "LICENSE")
    if not os.path.exists(lic_path):
        print("[provenance] FAIL — LICENSE file missing.")
        sys.exit(1)
    with open(lic_path, "r") as f:
        content = f.read()
    if ORCID not in content:
        print(f"[provenance] FAIL — ORCID {ORCID} not found in LICENSE.")
        sys.exit(1)

def _check_constants():
    constants_path = os.path.join(os.path.dirname(__file__), "src", "morphe", "constants.py")
    if not os.path.exists(constants_path):
        print("[provenance] FAIL — constants.py missing.")
        sys.exit(1)
    with open(constants_path, "r") as f:
        content = f.read()
    if MAGIC not in content:
        print(f"[provenance] FAIL — ORCID magic number {MAGIC} not found in constants.py.")
        sys.exit(1)

def _write_log():
    with open(LOG_FILE, "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {socket.gethostname()} | {os.getcwd()} | {CANARY}\n")
