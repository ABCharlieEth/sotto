# Sotto Pay

Accept private Zcash payments with a link.

A merchant shares a **unified full viewing key** (it can see incoming payments, never spend them). Each invoice gets
its own diversified shielded address and a memo, encoded as a [ZIP 321](https://zips.z.cash/zip-0321) payment URI and
QR code. The customer pays from any Zcash wallet; the server syncs the merchant's view-only wallet, matches the payment
to the invoice, tracks confirmations and calls the merchant's webhook.

- **Non-custodial**: funds go straight to the merchant's wallet. The server never holds a spending key.
- **Private**: shielded (Orchard/Sapling) payments; one address per invoice, so payments are matched even if a wallet
  drops the memo.
- **No dependencies**: Python 3 standard library. Wallet scanning uses
  [zcash-devtool](https://github.com/zcash/zcash-devtool) against a public light-wallet server.

## Run

```sh
# 1. build zcash-devtool (Rust)
git clone https://github.com/zcash/zcash-devtool && cd zcash-devtool && cargo build --release
# 2. run the checkout
ZC_NETWORK=test ZC_DEVTOOL=/path/to/zcash-devtool/target/release/zcash-devtool python3 -m zcheckout.server
# open http://127.0.0.1:8920
```

Settings (environment): `ZC_NETWORK` (`test`|`main`), `ZC_LWD` (light-wallet operator, default `zecrocks`),
`ZC_PORT`, `ZC_DATA`, `ZC_CONFIRMATIONS` (default 2), `ZC_INVOICE_TTL` (seconds, default 3600), `ZC_POLL`,
`ZC_PUBLIC_URL`.

## API

| Method | Path | Auth | |
|---|---|---|---|
| POST | `/api/merchants` | none | `{name, ufvk, webhook?}` returns `{merchant_id, api_key, address}` (key shown once) |
| POST | `/api/invoices` | `Bearer <api_key>` | `{amount, label?, order_ref?}` returns the invoice with `uri` and `pay_url` |
| GET | `/api/invoices` | `Bearer <api_key>` | the merchant's invoices |
| GET | `/api/invoices/<id>` | none | public invoice status (for the payment page) |
| GET | `/api/health` | none | network, chain tip, last scan |

Invoice status: `open` -> `seen` (in a block) -> `paid` (confirmed), or `underpaid` / `expired`.
Webhook (on `paid`): `POST {event: "invoice.paid", invoice, order_ref, amount_zat, received_zat, txid, confirmations, network}`.

## License

MIT. Bundles [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) (MIT).
