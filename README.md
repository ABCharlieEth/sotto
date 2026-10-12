# Sotto

Private Zcash payments for real shops, and a live view of the network they run on.

Sotto has two parts in one app: **Pay**, a shielded checkout, and **Pulse**, a live dashboard of the Zcash network.

## Pay

Accept private Zcash payments with a link.

A merchant shares a **unified full viewing key** (it can see incoming payments, never spend them). Each invoice gets
its own diversified shielded address and a memo, encoded as a [ZIP 321](https://zips.z.cash/zip-0321) payment URI and
QR code. The customer pays from any Zcash wallet; the server syncs the merchant's view-only wallet, matches the payment
to the invoice, tracks confirmations and calls the merchant's webhook.

- **Non-custodial**: funds go straight to the merchant's wallet. The server never holds a spending key.

**Proven on mainnet.** On 12 October 2026 a real invoice (0.001 ZEC) was paid from a phone wallet to a running
Sotto instance: scanned from the invoice QR, sent shielded, detected within one block and marked paid at two
confirmations. The transaction is
[`a0d1b29acb1888f5d3fa95ef1f73929ed6310eb8cc8241904a033dfcd3a90230`](https://mainnet.zcashexplorer.app/transactions/a0d1b29acb1888f5d3fa95ef1f73929ed6310eb8cc8241904a033dfcd3a90230)
on chain, it reveals nothing about the amount, the payer or the merchant, and that is the point.
- **Private**: shielded (Orchard/Sapling) payments; one address per invoice, so payments are matched even if a wallet
  drops the memo.
- **No dependencies**: Python 3 standard library. Wallet scanning uses
  [zcash-devtool](https://github.com/zcash/zcash-devtool) against a public light-wallet server.

## Pulse

`/pulse` shows the health of Zcash mainnet: how much ZEC is shielded, the value of every pool (Orchard, Sapling, Sprout,
lockbox, transparent) and its history, the ZEC still in Sprout ahead of NU7, which pools mined the last day of blocks,
and the network's pace.

- Data: [zcashexplorer.app](https://mainnet.zcashexplorer.app) (`getblockchaininfo`: value pools, upgrades) and
  [Blockchair](https://blockchair.com/zcash) (price, 24 h activity, per-block coinbase tags), fetched server-side and
  cached; a half-hourly snapshot builds the shielded-share history.
- Mining pools are read from the tag each pool writes into the coinbase; untagged blocks are shown as untagged, never
  guessed.
- Pulse always shows mainnet, whatever network the checkout runs on. Blockchair's free tier allows ~1440 requests a
  day, so run the refresher in one instance only and point others at it with `ZC_PULSE_UPSTREAM`.

## Run

```sh
# 1. build zcash-devtool (Rust)
git clone https://github.com/zcash/zcash-devtool && cd zcash-devtool && cargo build --release
# Sotto asks it for shielded-only invoice addresses (a --shielded-only flag on wallet generate-address):
#   git am ../patches/zcash-devtool-shielded-only.patch   # the one small patch, carried in this repo
# On an unpatched build Sotto still runs, but every invoice reuses the merchant's first address and
# payments are matched by memo and amount alone.
# 2. run the checkout
ZC_NETWORK=test ZC_DEVTOOL=/path/to/zcash-devtool/target/release/zcash-devtool python3 -m zcheckout.server
# open http://127.0.0.1:8920
```

Settings (environment): `ZC_NETWORK` (`test`|`main`), `ZC_LWD` (light-wallet operator, default `zecrocks`),
`ZC_PORT`, `ZC_DATA`, `ZC_CONFIRMATIONS` (default 2), `ZC_INVOICE_TTL` (seconds, default 3600), `ZC_POLL`,
`ZC_PUBLIC_URL`, `ZC_PULSE_UPSTREAM` (another Sotto that refreshes Pulse), `ZC_NU7_TARGET`.

## API

| Method | Path | Auth | |
|---|---|---|---|
| POST | `/api/merchants` | none | `{name, ufvk, webhook?}` returns `{merchant_id, api_key, address}` (key shown once) |
| POST | `/api/invoices` | `Bearer <api_key>` | `{amount, label?, order_ref?}` returns the invoice with `uri` and `pay_url` |
| GET | `/api/invoices` | `Bearer <api_key>` | the merchant's invoices |
| GET | `/api/invoices/<id>` | none | public invoice status (for the payment page) |
| GET | `/api/health` | none | network, chain tip, last scan |
| GET | `/api/pulse` | none | the Pulse dashboard data (mainnet) |

Invoice status: `open` -> `seen` (in a block) -> `paid` (confirmed), or `underpaid` / `expired`.
Webhook (on `paid`): `POST {event: "invoice.paid", invoice, order_ref, amount_zat, received_zat, txid, confirmations, network}`.

## License

MIT. Bundles [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) (MIT).
