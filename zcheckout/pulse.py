"""Pulse: Sotto's live view of the Zcash network (always mainnet data, whatever network the checkout runs on).

Refreshes the public sources in the background and serves one JSON document at /api/pulse. Blockchair's free tier
allows ~1440 requests a day, so only ONE Sotto instance should refresh; others point ZC_PULSE_UPSTREAM at it."""
import json, os, sqlite3, threading, time, traceback, urllib.request
from . import config, pulse_sources as sources

NU7_TARGET = os.environ.get("ZC_NU7_TARGET", "2026-11-05T00:00:00Z")   # announced target; height decided 2026-10-20
UPSTREAM = os.environ.get("ZC_PULSE_UPSTREAM", "")                    # another Sotto that refreshes, e.g. http://127.0.0.1:8921
SHIELDED = ("ironwood", "orchard", "sapling", "sprout")
STATE = {"chain": None, "stats": None, "miners": None, "t": {}, "up": (0, None)}
lock = threading.Lock()
H = None

def _db():
    os.makedirs(config.DATA, exist_ok=True)
    c = sqlite3.connect(os.path.join(config.DATA, "pulse-history.sqlite"), check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS snap (t INTEGER PRIMARY KEY, height INTEGER, supply REAL, pools TEXT, price REAL)")
    return c

def _refresher(name, fn, every):
    def run():
        while True:
            try:
                v = fn()
                with lock: STATE[name] = v; STATE["t"][name] = int(time.time())
                if name == "chain":
                    with lock:
                        H.execute("INSERT OR REPLACE INTO snap VALUES (?,?,?,?,?)", (int(time.time()) // 1800 * 1800, v["height"], v["supply"],
                                  json.dumps(v["pools"]), (STATE["stats"] or {}).get("price"))); H.commit()
            except Exception:
                traceback.print_exc()
            time.sleep(every)
    threading.Thread(target=run, daemon=True, name="pulse-" + name).start()

def miner_summary(blocks):
    if not blocks: return None
    n = len(blocks); counts = {}
    for b in blocks: counts[b["m"]] = counts.get(b["m"], 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    known = [(m, c) for m, c in ranked if m not in ("Untagged", "Mined-by user tags", "Unknown")]
    # pools needed to pass half of all blocks (unknown blocks count against nobody)
    acc = k = 0
    for m, c in known:
        acc += c; k += 1
        if acc * 2 > n: break
    else:
        k = None
    return {"blocks": n, "nakamoto": k, "unknown": counts.get("Untagged", 0) + counts.get("Mined-by user tags", 0),
            "top": [{"name": m, "blocks": c, "share": c / n} for m, c in ranked[:8]],
            "first_height": blocks[-1]["h"], "last_height": blocks[0]["h"]}

def pulse():
    if UPSTREAM:
        with lock: t, v = STATE["up"]
        if v is None or time.time() - t > 30:
            try:
                with urllib.request.urlopen(UPSTREAM.rstrip("/") + "/api/pulse", timeout=10) as r: v = json.loads(r.read())
                with lock: STATE["up"] = (time.time(), v)
            except Exception:
                if v is None: return {"ready": False}
        return v
    with lock:
        ch, st, mi, t = STATE["chain"], STATE["stats"], STATE["miners"], dict(STATE["t"])
        hist = H.execute("SELECT t, pools, supply FROM snap ORDER BY t DESC LIMIT 336").fetchall() if H else []
    if not ch: return {"ready": False}
    pools, total = ch["pools"], ch["supply"]
    shielded = sum(pools.get(p, 0) for p in SHIELDED)
    price = (st or {}).get("price")
    return {"ready": True, "height": ch["height"], "supply": total, "price": price,
            "price_change_24h": (st or {}).get("price_change_24h"), "market_cap": (st or {}).get("market_cap"),
            "pools": pools, "shielded": shielded, "shielded_share": shielded / total if total else None,
            "sprout": {"zec": pools.get("sprout", 0), "usd": pools.get("sprout", 0) * price if price else None, "nu7_target": NU7_TARGET},
            "network": st, "mining": miner_summary(mi), "upgrades": ch["upgrades"][-5:],
            "history": [{"t": r[0], "shielded_share": sum(json.loads(r[1]).get(p, 0) for p in SHIELDED) / r[2]} for r in reversed(hist)],
            "updated": t}

def start():
    global H
    if UPSTREAM: return
    H = _db()
    _refresher("stats", sources.stats, 300)
    _refresher("chain", sources.chain, 120)
    _refresher("miners", sources.miners, 1800)
