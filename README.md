# TechnoPrint CRM

**A CRM/ERP that runs a real print & repair shop in rural Siberia.** It replaced a 2004-era VB6
program, a 1C install used only for invoices, and a pile of spreadsheets. In production since
June 2026 — every cartridge, repair, invoice, debt and salary of the business goes through it.

Not a tutorial project. The constraints came from the shop, not from a course outline: the internet
drops, foreign CDNs are blocked by the ISP, the accountant needs print forms that match Russian
paperwork rules, and the owner needs to know how much cash is in the drawer right now.

🇷🇺 [Русская версия](README.ru.md)

---

## Context

The shop is in Uporovo, a rural district of ~20 000 people in the Tyumen region. It refills printer
cartridges, repairs PCs and office equipment, sells consumables and prints documents. Most of the
revenue comes from public-sector customers — schools, kindergartens, a social services centre,
municipal administrations — who pay by bank transfer against invoices, plus walk-in customers who
pay cash.

Before this system, the same order could exist in three places and agree with none of them.

## What it does

| Section | What it covers |
|---|---|
| **Refills** | Cartridge journal: 4 987 cartridges tracked by barcode, 18 948 refills in history. Per-client cards, price list, Code128 labels. |
| **Repairs** | Repair jobs per client, work types, per-job pricing, billing status. |
| **Goods** | 1 092-item catalogue with search and sale flow. |
| **Documents** | Invoices, acts, waybills, sales receipts — print-exact forms matching Russian accounting practice, generated in the browser. |
| **Clients** | Counterparties with tax/bank details, merge tool, per-client history. |
| **Debts** | Receivables by client with ageing, one-click "paid". |
| **Salary** | Auto-calculated commission from work actually done in the month, payments, month corrections. |
| **Cash** | Cash register balance derived from orders, withdrawals, expenses. |
| **Dashboard** | Daily/monthly/yearly revenue, split by payment type, section breakdown, charts. |
| **Audit log** | Who deleted/finalised/paid what, with amounts. |
| **Telegram bot** | Daily and monthly summaries, debt list, payment notifications. |

## Engineering notes

The parts that were actually interesting to build:

**Offline-first, because the internet really does drop.** The frontend is a PWA with a service
worker and an IndexedDB outbox. Writes made offline are queued, replayed on reconnect, and
reconciled: records created offline get a temporary id that is swapped for the server id once the
queue drains. Every queued write carries an `X-Op-Id` header, and a middleware deduplicates replays
server-side — so a flaky connection can't double-charge a customer.

**No foreign CDNs — at all.** Russian ISPs block `cdn.tailwindcss.com`, `unpkg`, `jsdelivr` and
Google Fonts. A single `<script src="https://cdn…">` means a blank app for the user. Everything is
vendored and served same-origin. This is enforced by convention and verified after deploys with a
headless browser that resolves those hosts to `0.0.0.0`.

**Single-entry money model.** One `orders` table is the single source of truth: a cash sale is a
paid order, an invoice is an unpaid one (a receivable). The dashboard, the debt list and the cash
register are all projections of that table — there is no parallel ledger to reconcile, and no way
for two screens to disagree.

**Work date vs money date.** Salary and section reports attribute work to the month it was *done*;
revenue is attributed to the month it was *billed*. A refill done in June and invoiced in July pays
the technician for June and shows as July revenue — which is what both the technician and the
accountant expect, and what a single date field can't express.

**Additive migrations without Alembic.** On boot, `_ensure_columns()` introspects the live schema
and issues `ALTER TABLE … ADD COLUMN IF NOT EXISTS` for anything the models declare but the database
lacks; `create_all` handles new tables. Additive only — it never drops or rewrites. For a
single-deployment product this replaced a migration tool that nobody was going to maintain.

**Backups with a dead-man switch.** Nightly `pg_dump` on the server, pulled to an off-server machine
twice a day, then pushed to a NAS — three copies. Each step verifies gzip integrity and that the
newest dump is less than 26 hours old, and reports failures to Telegram. The system exists because
the business already lost its data once.

**Print forms.** Invoices, acts, waybills and receipts are rendered client-side into print-exact
HTML, including amounts spelled out in Russian words and bank details laid out the way accountants
expect to receive them.

## Stack

**Backend** — Python 3.12, FastAPI, SQLAlchemy 2 (async), PostgreSQL 16, JWT + bcrypt, WebSockets
for live updates, python-telegram-bot running in-process.
114 endpoints across 18 routers, 32 tables.

**Frontend** — Alpine.js, Tailwind, Chart.js, JsBarcode, service worker, IndexedDB.
No build step: the browser loads the same files that live in the repo.

**Infrastructure** — Docker Compose, nginx, Let's Encrypt, deployed to a small VPS.

~5 900 lines of Python, ~5 500 lines of frontend.

## Running it

```bash
cp .env.example .env                 # POSTGRES_PASSWORD for compose
cp backend/.env.example backend/.env # SECRET_KEY is required: openssl rand -hex 32
docker compose up -d --build
```

The API is then on `127.0.0.1:8003` (`/docs` for the OpenAPI UI, `/health` for a liveness check),
and the frontend is static files to be served by nginx — see `nginx.conf`.

Deployment to a server is `./deploy.sh`, which reads its target from `deploy.env`
(copy `deploy.env.example`). It syncs code, writes environment files, rebuilds containers,
configures nginx and issues the TLS certificate.

## Repository layout

```
backend/app/
  main.py          FastAPI app, idempotency middleware, lifespan
  models.py        SQLAlchemy models — 32 tables
  routers/         18 routers: orders, clients, cartridges, works, goods,
                   documents, debts, salary, expenses, dashboard, audit, …
  telegram_bot.py  bot: summaries, debts, notifications
  database.py      engine, session, additive auto-migration
frontend/
  index.html       the whole UI (Alpine templates)
  app.js           application logic
  offline.js       outbox, sync, idempotency
  sw.js            service worker: shell + API caching strategies
  vendor/          vendored libraries — never a CDN
docker-compose.yml, nginx.conf, deploy.sh, backup_server.sh
```

## Not in this repository

One-off scripts that migrated the historical data out of the legacy VB6 program, 1C and the
spreadsheets are kept private — they contain the customer mapping tables of a real business.
Database dumps, ledgers and any customer data are excluded as well; see `.gitignore`.

## License

MIT — see [LICENSE](LICENSE).
