"""ZIP 321 payment request URIs: zcash:<address>?amount=<ZEC>&memo=<base64url>&message=<text>."""
import base64, urllib.parse

def zat_to_zec(z):
    s = f"{z // 100_000_000}.{z % 100_000_000:08d}".rstrip("0").rstrip(".")
    return s or "0"

def uri(address, amount_zat, memo=None, message=None):
    q = [("amount", zat_to_zec(amount_zat))]
    if memo: q.append(("memo", base64.urlsafe_b64encode(memo.encode()).decode().rstrip("=")))
    if message: q.append(("message", message))
    return f"zcash:{address}?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
