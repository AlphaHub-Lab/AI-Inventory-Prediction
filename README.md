# Stockwise AI — Inventory Demand Forecasting & Waste Reduction

Stockwise AI is a connected React and FastAPI application for inventory operations. It combines live stock and sales data, explainable demand forecasts, expiry and waste prediction, approval-gated reordering, purchase orders, supplier tracking, and a grounded conversational decision assistant.

## Architecture

```text
React + TypeScript dashboard
        │ JWT / RBAC API
        ▼
FastAPI ── SQLAlchemy ── PostgreSQL (Docker)
   ├── forecasting and chronological model evaluation
   ├── expiry, waste, what-if and reorder engines
   └── chatbot intent router ── live data tools + RAG knowledge chunks
```

The desktop app reuses this renderer and API. Electron starts the FastAPI service on an ephemeral loopback-only port; PostgreSQL remains behind the API. The database is configured on first launch and stored encrypted in the OS credential store.

Quantitative chatbot answers are produced by live database tools. Policy/help answers retrieve a chunk from the seeded knowledge base and return its source metadata. The optional `LLM_API_KEY`/`LLM_MODEL` configuration is reserved for a provider adapter; no secret reaches the browser.

## Database ERD

- `users` hold one of three roles (`admin`, `business_owner`, `associate`); `user_permissions` stores explicit associate grants and `audit_logs` record sensitive operations.
- `businesses` store one of five types and the corresponding master/local database names. These are routing metadata in this build; tenant records still live in the shared application database.
- `categories` and `suppliers` each have many `products`; a product has batches, inventory transactions, sales, forecasts, waste predictions, expiry alerts, and reorder recommendations.
- Approved recommendations are converted by an authorized business owner into `purchase_orders` and `purchase_order_items`.
- `chatbot_conversations` contain `chatbot_messages`; `knowledge_documents` are chunked into `knowledge_chunks` for retrieval.
- `model_runs` holds model/version, chronological train period, horizon, and MAE/RMSE/MAPE/R².

## Quick start — local development

Prerequisites: Python 3.12+, Node 20+, and Docker Desktop with Docker Compose. PostgreSQL is the only supported database.

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
docker compose up -d --wait db
Set-Location backend
uvicorn app.main:app --reload --port 8000
```

The database starts empty. To load the demo catalog and sample history, run `python -m app.seed` from `backend` after PostgreSQL is ready.

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Open `http://localhost:5173`; API documentation is at `http://localhost:8000/docs`.

Seed accounts:

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@inventory.example.com` | `Admin123!` |
| Business Owner | `manager@inventory.example.com` | `Manager123!` |
| Associate | `staff@inventory.example.com` | `Staff123!` |

There is no public registration route. Administrators provision businesses, owners, and associates. Business owners grant associates their operational permissions.

## Desktop application

The Electron desktop client packages the existing React renderer and a per-platform PyInstaller build of the FastAPI service. It does not create or migrate a production database on the user's machine. Connect it to a provisioned PostgreSQL database with the existing Stockwise schema. The connection URL is encrypted with Electron `safeStorage`; the randomly generated JWT signing key stays in the same encrypted application-data file and is passed only to the local backend process.

Desktop requirements: Python 3.12, Node.js 22.12 or newer, npm, and a reachable PostgreSQL database. To use the local Docker database, first follow Quick start through `docker compose up -d --wait db`, then apply migrations and seed data from the project root:

```powershell
Set-Location backend
alembic upgrade head
python -m app.seed
Set-Location ..
```

Install backend build/runtime dependencies and npm packages:

```powershell
python -m pip install -r requirements-desktop.txt
npm install
npm --prefix frontend install
npm run desktop
```

On first launch, enter the central/admin database PostgreSQL connection URL. Remote connections must include `sslmode=require` or a stronger TLS mode. The API binds only to `127.0.0.1`; Electron chooses an available port, checks `/health` including a database query, and only then loads the renderer. Use **File → Change Database Connection…** to replace the saved URL. Upload, download, export, and print workflows continue to use Chromium's native file and print support. External web links open in the system browser.

Development scripts:

| Command | Purpose |
| --- | --- |
| `npm run web` | Run the existing Vite renderer only |
| `npm run desktop` | Run Vite and the Electron desktop shell; requires backend Python dependencies |
| `npm run build:renderer` | Type-check and build the web renderer |
| `npm run build:backend` | Install desktop Python requirements and bundle the API for the current OS |
| `npm run build` | Build the Windows installer on Windows, macOS artifacts on macOS, or Linux packages on Linux |
| `npm run build:win` | Build the Windows NSIS installer (Windows host) |
| `npm run build:mac` | Build the macOS app, DMG, and update ZIP (macOS host) |
| `npm run build:linux` | Build AppImage and DEB packages (Linux host) |

Desktop artifacts are written to `release/`. PyInstaller and Electron Builder create native binaries, so build the backend and installer on each target operating system. macOS distribution outside local use requires Apple signing/notarization credentials. Windows signing is recommended for public distribution. GitHub release publishing and update checks use the repository configured in `package.json`; publish signed artifacts with `GH_TOKEN` set in the release environment. The app checks for updates only when the user chooses **Help → Check for Updates…** and asks before downloading and restarting.

The desktop client requires a live PostgreSQL connection. It has no offline database or synchronization implementation. Remote database credentials are required at first launch; there are no production credentials in the app bundle. Encrypted connection settings, generated forecasting models, and desktop logs are stored in the OS application-data directory (`connection.enc`, `models/`, and `logs/desktop.log`). Database schema creation and migrations remain an operator/deployment responsibility.

For the conversion assessment and application-specific workflow checklist, see [DESKTOP_ASSESSMENT.md](DESKTOP_ASSESSMENT.md).

The deterministic seed contains 30 products, 8 suppliers, 365 days of sales per product (10,950 rows), expiring inventory, promotions, holidays, forecasts, policies, and operational insights. Re-running seed preserves an existing database rather than overwriting it.

## Docker deployment

```powershell
Copy-Item .env.example .env
docker compose up --build
```

The Compose setup runs PostgreSQL, the FastAPI server, and a production Nginx web bundle. The application connects only to PostgreSQL. Change `SECRET_KEY`, database credentials, and CORS origins in `.env` before production. Apply schema migrations with `cd backend; alembic upgrade head`; the initial migration creates the metadata schema.

## Training, testing, and benchmarking

```powershell
# Import a complete product catalog and dated sales history into the selected business.
python ml\import_supermarket_data.py `
  --sales-csv "C:\path\to\indian_supermarket_sales_history_12_months_synthetic.csv" `
  --catalog-csv "C:\path\to\indian_supermarket_sku_dataset.csv" `
  --database-url sqlite:///backend/indian_supermarket.db

# Train the SKU-aware forecaster and compare it with a seasonal-naive baseline.
python ml\train_forecasts.py --database-url sqlite:///backend/indian_supermarket.db --business-id 1

# Re-copy the supplied chatbot data, if needed
.\scripts\prepare_data.ps1

# Forecast evaluation — chronological 80/20 holdout, never random splitting
python ml\train_forecasts.py

# Backend unit/integration tests (run after seeding)
Set-Location backend
pytest tests -q

# Frontend component test and production build
Set-Location ..\frontend
npm test
npm run build

# Held-out chatbot benchmark (never used as training data)
Set-Location ..\backend
python ..\chatbot\benchmark.py --input ..\data\chatbot_benchmark.csv --output ..\data\benchmark_results.json
```

The demand model uses a chronological 28-day holdout with rolling 7-day and 28-day forecasts; MAPE is calculated on nonzero-sales days and WAPE is also reported because this dataset contains zero-sales days. The selected artifact is used by online forecasts for imported SKUs. Model artifacts and the local supermarket database are generated locally and ignored by Git.

The chatbot benchmark writes intent accuracy, tool success, groundedness/unsupported-claim rate, and response latency to JSON. It uses `data/chatbot_benchmark.csv`; its companion `data/chatbot_training_dataset.txt` remains a development reference for intent/retrieval examples.

## API surface

`/api/auth`, `/api/users`, `/api/categories`, `/api/suppliers`, `/api/products`, `/api/inventory`, `/api/sales` (CSV import/export), `/api/forecasts`, `/api/dashboard`, `/api/analytics`, `/api/waste`, `/api/expiry`, `/api/reorders`, `/api/what-if`, `/api/purchase-orders`, `/api/knowledge`, `/api/models/runs`, and `/api/chat`.

All protected endpoints require a JWT. Write operations are audited; catalog, user, insight refresh, purchase-order status, and recommendation approval endpoints enforce server-side roles. The chat endpoint is rate-limited to 20 requests per minute per client.

## Example chats

- “Which products are likely to expire this week?” → live expiry list and dated items.
- “How much rice should I order next week?” → lead-time forecast, safety stock, current quantity, and explainable recommended order.
- “What will demand for milk be over the next 7 days?” → stored forecast calculation.
- “Explain safety stock.” → retrieved policy text with source citation.
- “What if Basmati Rice demand increases by 20%?” → revised lead-time demand, stockout risk, and recommended order.

## Known limitations and planned enhancements

- Imported supermarket SKUs use the persisted XGBoost forecaster; products without a matching trained SKU profile use the seasonal baseline. The local model artifact is generated by the training command and is intentionally not committed.
- RAG uses lexical chunk ranking locally to avoid a mandatory external service. Its `KnowledgeChunk` boundary is designed to be replaced by pgvector embeddings.
- A provider-specific LLM function-calling adapter is intentionally configuration-driven rather than bundled; tools remain the authority for numbers.
- Product details and management views cover the operational core; bulk batch receiving, richer PO conversion UI, and browser E2E Playwright coverage are logical next iterations.
