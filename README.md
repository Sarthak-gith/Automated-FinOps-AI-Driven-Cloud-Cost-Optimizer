# Automated FinOps: AI-Driven Cloud Cost Optimizer

A local academic software engineering project for cost monitoring and optimization.
The application runs on a Windows 11 development machine and uses a deterministic
simulator, SQLite, FastAPI, and a React dashboard. It does not connect to AWS or
any live cloud account.

**Every resource, metric, forecast, cost, saving, and action shown here is simulated
or estimated.** No result represents a measured cloud bill or verified saving.

## Features

- 20 reproducible simulated resources and 30 days of hourly CPU, memory, storage,
  and network telemetry on first run.
- SQLite persistence across restarts and an append-only latest-metric operation.
- Dashboard, resource history, cost summaries, forecast charts, and CSV reports.
- Prophet forecasting with a named statsmodels ARIMA fallback if Prophet cannot run;
  forecasts are cached and persisted.
- Idle and right-sizing recommendations that show their thresholds and savings
  assumptions.
- Role-aware sign-in, admin approval, simulated execution, pause controls, and audit
  history.
- A provider protocol with a local simulator adapter. No live provider is included.

## Requirements

- Windows 11, Python 3.11, and Node.js 20 LTS or newer with npm.
- No cloud account, credentials, paid API, or external service account.

## Windows setup

Open PowerShell in the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -r backend\requirements.txt
```

Start the backend in that window:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
```

In a second PowerShell window, from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. The backend API is at <http://127.0.0.1:8000> and
interactive API documentation is at <http://127.0.0.1:8000/docs>.

The first backend startup creates the SQLite schema, demo users, default policy,
simulated inventory, and historical metrics. The default database is
`backend/data/finops.db` and is excluded from Git.

## Demo sign-in

| Role | Email | Default password |
|---|---|---|
| Administrator | `admin@finops.local` | `Admin123!` |
| Analyst | `analyst@finops.local` | `Analyst123!` |
| Viewer | `viewer@finops.local` | `Viewer123!` |

Set `DEMO_ADMIN_PASSWORD`, `DEMO_ANALYST_PASSWORD`, or `DEMO_VIEWER_PASSWORD` in
`.env` before first startup to choose local passwords. These variables only apply
when the database creates the demo users. Existing accounts persist their password.

## Working with the simulator

- `POST /api/simulation/seed` (administrator) performs an idempotent seed.
- `POST /api/simulation/latest` (administrator or analyst) appends one current
  hourly sample per resource without replacing history.
- `POST /api/simulation/regenerate` (administrator) replaces simulated resources,
  metrics, forecasts, recommendations, and actions. It preserves users, settings,
  policy, and the audit log, and writes a regeneration event.
- Resource count and historical days can be configured with `SIM_RESOURCE_COUNT`
  (1 to 30) and `SIM_HISTORY_DAYS` (1 to 90) before first seed.

## Forecasting note

The forecast endpoint uses Prophet first and labels results with the model actually
used. On the Windows validation environment for this project, Prophet 1.1.7 installed
but could not load its bundled CmdStan because its directory lacked a required
makefile. In that case, statsmodels ARIMA successfully generated the forecast and
the UI identifies it as **ARIMA fallback**. If both models fail, the endpoint
reports a failure instead of inventing a prediction. MAE and RMSE are only returned
when a holdout period is available.

The lockfile pins patched React Router 7, Vite 6, Vitest 5, and Tailwind CSS 4
releases. The final `npm audit` reported no known vulnerabilities in the locked
frontend dependency tree.

## Tests and checks

Backend:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests -q
```

Frontend, from the repository root:

```powershell
Set-Location frontend
npm ci
npm test
npm run lint
npm run build
```

## Documentation

- [Architecture](docs/architecture.md)
- [Requirements and scope](docs/requirements.md)
- [User guide and workflows](docs/user-guide.md)

## Limitations and future work

The simulator is the only provider. Cost rates and savings percentages are
demonstration assumptions, not provider pricing or verified savings. The project
does not provide production identity management, cloud-account integrations,
automated migrations, or infrastructure changes. A future provider would need to
be implemented behind the provider protocol and separately reviewed; live AWS
integration is not part of this project.
