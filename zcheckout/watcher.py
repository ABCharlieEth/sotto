"""Syncs each merchant's view-only wallet and matches received outputs to open invoices.
Match order: the invoice's own memo ("zc:<id>"), then the invoice's own diversified address."""
import json, threading, time, traceback, urllib.request
from . import config, db, devtool

def _webhook(m, inv):
    if not m["webhook"]: return True
    body = json.dumps({"event": "invoice.paid", "invoice": inv["id"], "order_ref": inv["order_ref"],
                       "amount_zat": inv["amount_zat"], "received_zat": inv["received_zat"], "txid": inv["txid"],
                       "confirmations": inv["confirmations"], "network": config.NETWORK}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(m["webhook"], data=body, headers={"content-type": "application/json"}), timeout=10)
        return True
    except Exception:
        return False

def scan_merchant(m):
    devtool.sync(m["id"])
    tip = devtool.tip(m["id"])
    outs = devtool.received(m["id"])
    open_inv = {r["id"]: r for r in db.q("SELECT * FROM invoices WHERE merchant_id=? AND status IN ('open','seen','underpaid')", (m["id"],))}
    by_addr = {r["address"]: r for r in open_inv.values()}
    for o in outs:
        if db.q("SELECT 1 FROM seen_outputs WHERE txid=? AND pool=? AND idx=?", (o["txid"], o["pool"], o["index"]), one=True):
            continue
        inv = None
        if o["memo"].startswith("zc:"):
            inv = open_inv.get(o["memo"][3:].strip())
        if inv is None and o["address"]:
            inv = by_addr.get(o["address"])
        if inv is None: continue
        db.x("INSERT OR IGNORE INTO seen_outputs VALUES (?,?,?,?)", (o["txid"], o["pool"], o["index"], inv["id"]))
        db.x("UPDATE invoices SET received_zat = received_zat + ?, txid = ?, mined_height = ? WHERE id = ?",
             (o["value"], o["txid"], o["height"], inv["id"]))
    now = int(time.time())
    for inv in db.q("SELECT * FROM invoices WHERE merchant_id=? AND status IN ('open','seen','underpaid')", (m["id"],)):
        conf = (tip - inv["mined_height"] + 1) if inv["mined_height"] else 0
        if inv["received_zat"] >= inv["amount_zat"]:
            status = "paid" if conf >= config.CONFIRMATIONS else "seen"
        elif inv["received_zat"] > 0:
            status = "underpaid"
        elif now > inv["expires"]:
            status = "expired"
        else:
            status = "open"
        db.x("UPDATE invoices SET status=?, confirmations=?, paid_at=CASE WHEN ?='paid' THEN ? ELSE paid_at END WHERE id=?",
             (status, conf, status, now, inv["id"]))
    for inv in db.q("SELECT * FROM invoices WHERE merchant_id=? AND status='paid' AND webhook_sent=0", (m["id"],)):
        if _webhook(m, inv): db.x("UPDATE invoices SET webhook_sent=1 WHERE id=?", (inv["id"],))
    return tip

STATE = {"tip": None, "last": None, "error": None}

def loop():
    while True:
        try:
            for m in db.q("SELECT * FROM merchants"):
                # only merchants with something to watch, to keep the light-wallet server load small
                if db.q("SELECT 1 FROM invoices WHERE merchant_id=? AND status IN ('open','seen','underpaid')", (m["id"],), one=True):
                    STATE["tip"] = scan_merchant(m)
            STATE["last"] = int(time.time()); STATE["error"] = None
        except Exception as e:
            STATE["error"] = str(e)[:300]; traceback.print_exc()
        time.sleep(config.POLL)

def start():
    threading.Thread(target=loop, daemon=True, name="watcher").start()
