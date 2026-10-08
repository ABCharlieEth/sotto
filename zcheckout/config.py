import os

NETWORK = os.environ.get("ZC_NETWORK", "test")            # "test" or "main"
LWD_SERVER = os.environ.get("ZC_LWD", "zecrocks")          # light-wallet server operator known to zcash-devtool
DEVTOOL = os.environ.get("ZC_DEVTOOL", "zcash-devtool")
DATA = os.environ.get("ZC_DATA", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
PORT = int(os.environ.get("ZC_PORT", "8920"))
CONFIRMATIONS = int(os.environ.get("ZC_CONFIRMATIONS", "2"))   # blocks before an invoice counts as paid
INVOICE_TTL = int(os.environ.get("ZC_INVOICE_TTL", str(60 * 60)))   # seconds an invoice stays open
LATE_WINDOW = int(os.environ.get("ZC_LATE_WINDOW", str(7 * 24 * 3600)))   # seconds an expired invoice still catches a late payment
POLL = int(os.environ.get("ZC_POLL", "15"))                 # seconds between wallet syncs
PUBLIC_URL = os.environ.get("ZC_PUBLIC_URL", "")           # used in links handed to merchants
TICKER = "TAZ" if NETWORK == "test" else "ZEC"
UFVK_PREFIX = "uviewtest1" if NETWORK == "test" else "uview1"
MAX_MERCHANTS = int(os.environ.get("ZC_MAX_MERCHANTS", "30"))   # sign-up cap for a public demo
SIGNUPS_PER_IP_HOUR = int(os.environ.get("ZC_SIGNUPS_PER_IP_HOUR", "3"))
