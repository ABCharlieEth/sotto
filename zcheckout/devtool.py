"""A thin wrapper around zcash-devtool: view-only wallets, sync, and reading received outputs from the wallet DB."""
import json, os, re, sqlite3, subprocess
from . import config

def wallet_dir(merchant_id):
    return os.path.join(config.DATA, "wallets", merchant_id)

def run(*args, timeout=300):
    p = subprocess.run([config.DEVTOOL, *args], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else f"devtool exit {p.returncode}")
    return p.stdout

def tip(merchant_id):
    out = run("wallet", "-w", wallet_dir(merchant_id), "get-info", "-s", config.LWD_SERVER, timeout=60)
    d = json.loads(out[out.index("{"):])
    return int(d.get("chain_tip_height") or d.get("chainTipHeight"))

def init_view_only(merchant_id, name, ufvk, birthday=None):
    args = ["wallet", "-w", wallet_dir(merchant_id), "init-fvk", "--name", name, "--fvk", ufvk, "-s", config.LWD_SERVER]
    if birthday: args += ["--birthday", str(birthday)]
    run(*args, timeout=180)

def new_address(merchant_id):
    """A fresh diversified Unified Address for the merchant's account: one per invoice, so a payment is matched
    by the address it arrived at even when the payer's wallet drops the memo."""
    # shielded receivers only: a transparent component would put every invoice address under the transparent
    # gap limit, which blocks once a few invoices expire unpaid (found on mainnet, 2026-10-12). Shielded
    # diversified addresses have no such limit, and a payment-only address has no business being transparent
    out = run("wallet", "-w", wallet_dir(merchant_id), "generate-address", "--shielded-only", timeout=60)
    m = re.findall(r"\b(u(?:test)?1[0-9a-z]{100,})\b", out)
    if m: return m[-1]
    return first_address(merchant_id)

def first_address(merchant_id):
    out = run("wallet", "-w", wallet_dir(merchant_id), "list-addresses", timeout=60)
    m = re.findall(r"\b(u(?:test)?1[0-9a-z]{100,})\b", out)
    if not m: raise RuntimeError("no address")
    return m[0]

def sync(merchant_id):
    run("wallet", "-w", wallet_dir(merchant_id), "sync", "-s", config.LWD_SERVER, timeout=600)
    try: run("wallet", "-w", wallet_dir(merchant_id), "enhance", "-s", config.LWD_SERVER, timeout=300)   # full txs, for memos
    except Exception: pass

def memo_text(b):
    """ZIP 302: a text memo starts with a byte <= 0xF4 and is zero-padded UTF-8."""
    if not b or b[0] > 0xF4: return ""
    return bytes(b).rstrip(b"\x00").decode("utf-8", "replace")

def received(merchant_id):
    """Every non-change output received by the merchant's account: txid, pool, index, value, memo, address, height."""
    path = os.path.join(wallet_dir(merchant_id), "data.sqlite")
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(v_tx_outputs)")}
        addr = "to_address" if "to_address" in cols else "NULL"
        rows = c.execute(f"""SELECT o.txid, o.output_pool, o.output_index, o.value, o.memo, {addr}, t.mined_height
                              FROM v_tx_outputs o JOIN v_transactions t ON t.txid = o.txid
                             WHERE o.to_account_uuid IS NOT NULL AND o.is_change = 0""").fetchall()
    finally:
        c.close()
    out = []
    for txid, pool, idx, value, memo, to_addr, h in rows:
        out.append({"txid": bytes(txid)[::-1].hex() if isinstance(txid, (bytes, bytearray)) else str(txid),
                    "pool": pool, "index": idx, "value": int(value), "memo": memo_text(memo or b""),
                    "address": to_addr, "height": h})
    return out
