"""HTTP API and static files. Run: python3 -m zcheckout.server"""
import hashlib, json, os, secrets, time, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from . import config, db, devtool, watcher, zip321

PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}
ID = re.compile(r"^[A-Za-z0-9]{6,32}$")
SIGNUPS = {}

def new_id(n=10):
    a = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(a) for _ in range(n))

def hkey(k): return hashlib.sha256(k.encode()).hexdigest()

def invoice_view(r):
    memo = r["memo"]
    return {"id": r["id"], "label": r["label"], "order_ref": r["order_ref"], "status": r["status"],
            "amount": zip321.zat_to_zec(r["amount_zat"]), "amount_zat": r["amount_zat"], "ticker": config.TICKER,
            "received": zip321.zat_to_zec(r["received_zat"]), "address": r["address"], "memo": memo,
            "uri": zip321.uri(r["address"], r["amount_zat"], memo, r["label"] or None),
            "txid": r["txid"], "confirmations": r["confirmations"], "needed": config.CONFIRMATIONS,
            "created": r["created"], "expires": r["expires"], "paid_at": r["paid_at"], "network": config.NETWORK}

class H(BaseHTTPRequestHandler):
    server_version = "zcheckout"
    def log_message(self, *a): pass
    def send(self, code, obj=None, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", ctype); self.send_header("cache-control", "no-store")
        self.send_header("x-content-type-options", "nosniff"); self.send_header("referrer-policy", "no-referrer")
        self.end_headers(); self.wfile.write(body)
    def body(self):
        n = int(self.headers.get("content-length") or 0)
        if n > 20000: raise ValueError("too large")
        return json.loads(self.rfile.read(n) or b"{}")
    def merchant(self):
        k = (self.headers.get("authorization") or "").removeprefix("Bearer ").strip()
        return db.q("SELECT * FROM merchants WHERE key_hash=?", (hkey(k),), one=True) if k else None

    def do_GET(self):
        u = urlparse(self.path); p = u.path
        if p == "/api/health":
            return self.send(200, {"network": config.NETWORK, "ticker": config.TICKER, "tip": watcher.STATE["tip"],
                                   "last_scan": watcher.STATE["last"], "error": watcher.STATE["error"]})
        if p.startswith("/api/invoices/"):
            i = p.rsplit("/", 1)[-1]
            r = db.q("SELECT * FROM invoices WHERE id=?", (i,), one=True) if ID.match(i) else None
            return self.send(200, invoice_view(r)) if r else self.send(404, {"error": "not found"})
        if p == "/api/invoices":
            m = self.merchant()
            if not m: return self.send(401, {"error": "api key"})
            rows = db.q("SELECT * FROM invoices WHERE merchant_id=? ORDER BY created DESC LIMIT 200", (m["id"],))
            return self.send(200, {"merchant": {"id": m["id"], "name": m["name"], "webhook": m["webhook"]},
                                   "invoices": [invoice_view(r) for r in rows]})
        # static: /pay/<id> and /merchant are single pages
        if p.startswith("/pay/"): p = "/pay.html"
        if p == "/merchant": p = "/merchant.html"
        if p == "/": p = "/index.html"
        f = os.path.normpath(os.path.join(PUBLIC, p.lstrip("/")))
        if not f.startswith(PUBLIC) or not os.path.isfile(f): return self.send(404, {"error": "not found"})
        with open(f, "rb") as fh: return self.send(200, raw=fh.read(), ctype=TYPES.get(os.path.splitext(f)[1], "application/octet-stream"))

    def do_POST(self):
        p = urlparse(self.path).path
        try: b = self.body()
        except Exception: return self.send(400, {"error": "bad json"})
        if p == "/api/merchants":
            # every merchant is a wallet this server syncs: a public demo caps the total and the rate per visitor
            ip = self.headers.get("cf-connecting-ip") or self.client_address[0]
            now = time.time(); SIGNUPS[ip] = [t for t in SIGNUPS.get(ip, []) if now - t < 3600]
            if len(SIGNUPS[ip]) >= config.SIGNUPS_PER_IP_HOUR: return self.send(429, {"error": "too many sign-ups, try again later"})
            if (db.q("SELECT COUNT(*) AS n FROM merchants", one=True)["n"]) >= config.MAX_MERCHANTS:
                return self.send(503, {"error": "the demo is full"})
            SIGNUPS[ip].append(now)
            name = str(b.get("name") or "").strip()[:60]; ufvk = str(b.get("ufvk") or "").strip()
            hook = str(b.get("webhook") or "").strip()[:300] or None
            if not name or not re.fullmatch(re.escape(config.UFVK_PREFIX) + r"[0-9a-z]{100,2000}", ufvk):
                return self.send(400, {"error": f"name and a {config.UFVK_PREFIX}... unified full viewing key are required"})
            if hook and not hook.startswith("https://"): return self.send(400, {"error": "webhook must be https"})
            mid = new_id(12); key = "zck_" + secrets.token_urlsafe(24)
            try:
                devtool.init_view_only(mid, name, ufvk)
                addr = devtool.first_address(mid)
            except Exception as e:
                return self.send(400, {"error": "viewing key rejected: " + str(e)[:200]})
            db.x("INSERT INTO merchants VALUES (?,?,?,?,?,?)", (mid, name, hkey(key), addr, hook, int(time.time())))
            return self.send(201, {"merchant_id": mid, "api_key": key, "address": addr,
                                   "note": "Keep the api_key: it is shown once. The viewing key can see incoming payments but cannot spend."})
        if p == "/api/invoices":
            m = self.merchant()
            if not m: return self.send(401, {"error": "api key"})
            try:
                zec = str(b.get("amount")).strip()
                if not re.fullmatch(r"\d{1,6}(\.\d{1,8})?", zec): raise ValueError
                whole, _, frac = zec.partition("."); zat = int(whole) * 100_000_000 + int((frac + "00000000")[:8])
                if zat <= 0: raise ValueError
            except Exception:
                return self.send(400, {"error": "amount in ZEC, up to 8 decimals"})
            iid = new_id(10); now = int(time.time())
            try: addr = devtool.new_address(m["id"])
            except Exception: addr = m["address"]
            db.x("INSERT INTO invoices (id, merchant_id, label, order_ref, amount_zat, address, memo, created, expires) VALUES (?,?,?,?,?,?,?,?,?)",
                 (iid, m["id"], str(b.get("label") or "")[:80] or None, str(b.get("order_ref") or "")[:80] or None,
                  zat, addr, "zc:" + iid, now, now + config.INVOICE_TTL))
            r = db.q("SELECT * FROM invoices WHERE id=?", (iid,), one=True)
            v = invoice_view(r); v["pay_url"] = (config.PUBLIC_URL.rstrip("/") + "/pay/" + iid) if config.PUBLIC_URL else "/pay/" + iid
            return self.send(201, v)
        return self.send(404, {"error": "not found"})

def main():
    db.db(); watcher.start()
    s = ThreadingHTTPServer(("127.0.0.1", config.PORT), H)
    print(f"zcheckout on 127.0.0.1:{config.PORT} ({config.NETWORK})", flush=True)
    s.serve_forever()

if __name__ == "__main__":
    main()
