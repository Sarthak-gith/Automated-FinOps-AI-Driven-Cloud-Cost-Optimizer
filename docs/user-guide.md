# User guide

## Start the application

Use the Windows setup steps in the repository [README](../README.md). Start Uvicorn
from the repository root with `--app-dir backend`, then start Vite from `frontend`.
The first backend start creates the local SQLite database and deterministic demo
data automatically.

## Sign in and roles

The default users are listed in the README. An administrator can change the
automation policy, approve or reject action requests, execute approved simulated
actions, and regenerate the simulator. An analyst can generate forecasts and
recommendations, append latest telemetry, and request approvals. A viewer can
inspect pages and export reports.

An analyst should request a recommendation's action; a different administrator
must approve it. The administrator then executes it from the Approval Queue. An
idle-stop action changes the simulated resource to stopped. A right-size action
changes the simulated size and type labels. Neither operation calls a cloud API.

## Dashboard and resources

The Overview shows estimated monthly run cost, active simulated resources, recent
average CPU, a sample utilization trend, and cost by category. The Resources page
lists the simulated inventory and charts historical CPU and memory for a selected
resource. Resource detail includes region, category, size, status, and integer-cent
estimated costs.

## Forecasts

Choose **Generate forecasts** to process the current inventory. Resources need at
least 48 valid hourly observations. Results include timestamps, predicted CPU,
uncertainty bounds, and the model name. Recent results are cached for six hours;
an authorized caller can force a refresh through the API. The endpoint can be
called per resource for fast iteration:

```text
POST /api/forecasts/generate?resource_id=sim-general-001&horizon_hours=24&force=true
```

The API labels each result `insufficient_data`, `available`, or `failed`. The
dashboard displays the model used. Prophet is attempted first; ARIMA is an explicit
fallback when Prophet cannot run.

## Recommendations and approvals

Select **Analyze resources** to inspect the latest seven days of simulated CPU
observations. Idle candidates use mean CPU below 8% and maximum CPU below 15%.
Right-sizing candidates use mean CPU below 30% and 95th percentile below 55%.
Storage and network resources are not covered by these compute rules. Each result
explains its observed sample and estimated savings assumptions.

To simulate a change:

1. An analyst selects **Request approval** for a pending recommendation.
2. An administrator reviews and approves or rejects it.
3. An administrator executes the approved action.
4. The resource status or size changes only in the local database; the audit page
   records the request, decision, and execution.

The automation policy's pause switch blocks new requests and execution. The API
also checks the allowed-action list and per-action savings limit.

## Simulator and reports

The protected seed endpoint is idempotent. Latest-metric collection adds a sample
for the current hour and will not duplicate that resource-hour. Simulator
regeneration replaces the simulated inventory, metrics, forecasts, recommendations,
and actions but keeps users, policy, and audit entries. Use it when you want a clean
demo dataset without deleting local authentication history.

The Reports page downloads a server-generated CSV containing resource costs and
recommendation estimates. The CSV and report summary label their values as
simulated or estimated.

## Troubleshooting

- **Port already in use:** close the other local server or change Uvicorn's port and
  `CORS_ORIGINS`/Vite API URL accordingly.
- **Login does not accept an overridden password:** demo password environment
  variables apply only when the users are first created. Existing users persist in
  SQLite; the regeneration endpoint deliberately preserves them.
- **Prophet model fails:** if ARIMA is available, the API returns the explicit
  `ARIMA fallback` model label. If both fail, inspect the forecast result's message.
- **No cloud data appears:** this project intentionally has no cloud connector. All
  displayed records come from the local simulator.
- **Reset a damaged local demo database:** stop the backend and remove
  `backend/data/finops.db`, then start it again. This resets local users, policy,
  resources, and audit history; the database file is ignored by Git.
