# Desktop conversion assessment

## Existing application

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, and Recharts in `frontend/`.
- **Backend:** FastAPI with SQLAlchemy, Alembic, JWT sessions, HTTP-only cookies, and role based authorization in `backend/`.
- **Database:** PostgreSQL is the supported application database. The local Docker Compose setup runs PostgreSQL; the backend can also connect to a hosted PostgreSQL service. Business data and authentication remain behind the API.
- **API and authentication:** REST endpoints under `/api`; `/health` is available for startup checks. Access JWTs are kept in renderer memory and refresh/session cookies are HTTP-only. No browser local storage is used for access tokens.
- **Configuration and integrations:** Backend settings come from environment variables and the repository `.env`; optional LLM provider credentials are backend only. The frontend currently uses relative API URLs and Vite proxies to port 8000.
- **Files and printing:** CSV sales import/export, receipt and supplier-document upload (including images/PDF/Excel), CSV export, and receipt printing use browser `File`, `Blob`, download, and print APIs.
- **Routing and state:** Hash-based client routing; a checkout cart uses `sessionStorage`.
- **Background and realtime:** No WebSocket use or separate worker service was found. Model training is an API-triggered backend operation.
- **Build/deployment:** Frontend Vite build; backend Docker image; root Docker Compose includes PostgreSQL, API, and Nginx. There is no existing desktop build.

## Desktop changes needed

The renderer can remain the existing React application. Electron needs a secure main/preload boundary, a loopback-only backend process with an ephemeral port and health check, desktop first-run database configuration, and packaging of the Python backend. Because the app has no synchronization layer, offline operation is not supported; PostgreSQL connectivity is required. For installed desktop use, the database connection is entered locally and protected with the operating system credential store when available. The packaged backend continues to own database access and all secrets.

The app's upload, download, and print workflows already use standard browser APIs supported by Electron Chromium, so they remain intact. Generated demand model artifacts need a persistent app-data path instead of the temporary PyInstaller extraction directory. External navigation must be handed to the system browser. Native menus, lifecycle handling, logs, and update checks belong in the Electron main process.

## Architecture decision

Use Electron with the existing renderer and a packaged FastAPI service bound only to `127.0.0.1`. Keep PostgreSQL behind that service (hosted PostgreSQL is suitable; local PostgreSQL is also supported). Electron stores the connection configuration under the OS application-data directory using `safeStorage`; it passes the decrypted settings only to the backend process environment at launch. Do not place credentials in renderer bundles. Build the backend separately on each target OS before creating that OS's installer.

## Workflow checklist

- [x] React routes, forms, dashboards, and charts retained
- [x] Login, logout, JWT session, and role permissions remain API-backed
- [x] CRUD, search, filtering, forecasts, inventory, sales, reorders, purchase orders, analytics, and chatbot remain API-backed
- [x] CSV/receipt/document upload and CSV/invoice export remain available
- [x] Receipt printing remains available
- [x] Local API process lifecycle and health check integrated
- [x] Packaged PostgreSQL URL normalized to psycopg 3, matching the bundled driver
- [x] Native file and app menus, external-link handling, and local logs integrated
- [x] Windows x64 NSIS installer builds on Windows (`release/Stockwise AI-1.0.0-win-x64.exe`)
- [ ] macOS and Linux installer builds run on their respective build hosts
- [ ] Packaged Windows API health check completes (sandbox blocks loopback HTTP probes; bundled API imports and starts its argument parser successfully)
- [ ] Live database and signed-update credentials/configuration supplied by the deployment owner
- [ ] End-to-end workflows verified against a configured PostgreSQL database

The remaining items require macOS/Linux build hosts, a loopback-enabled Windows runtime check, deployment credentials, or an initialized application database. The first Windows backend failure was traced to SQLAlchemy selecting psycopg2 for a standard `postgresql://` URL even though only psycopg 3 was bundled; URL normalization now selects psycopg 3. The replacement Windows installer was rebuilt, but a live local API health check could not be run in this sandbox.
