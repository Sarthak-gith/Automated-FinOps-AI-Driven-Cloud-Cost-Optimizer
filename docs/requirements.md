# Requirements

## Required behavior

1. Collect and display locally simulated cloud-resource telemetry.
2. Generate forecasts from persisted historical metrics with Prophet when the
   model dependency and data permit; report insufficient data or model errors
   accurately.
3. Identify idle and over-provisioned simulated resources.
4. Explain savings estimates, assumptions, and risk for recommendations.
5. Require authorization and approval before simulated optimization actions.
6. Provide an interactive dashboard for costs, utilization, and forecasts.
7. Persist role-aware decisions, configuration, and audit history in SQLite.
8. Include automated tests and Windows setup documentation.

## Constraints

- Python 3.11+, FastAPI, Pydantic, SQLAlchemy, and SQLite for the backend.
- React, Vite, TypeScript, Tailwind CSS, Chart.js, React Router, and Lucide React
  for the frontend.
- NumPy and Pandas for deterministic metric simulation; Prophet for time-series
  forecasting. A documented statsmodels ARIMA fallback is permitted only when
  Prophet cannot install or run.
- No cloud account, cloud credentials, paid services, or live cloud API calls.
- Simulated resources, telemetry, forecasts, savings, and actions must be labeled
  as simulated or estimated. No unverified accuracy claims.
- Seed operations must be repeatable and must not create duplicate records.
- Persisted monetary values must use fixed precision or integer minor units.

## Out of scope for this version

Live AWS/provider integrations, billing data ingestion, paid hosted services, and
automatic changes to real infrastructure. These may be future enhancements behind
the provider abstraction, but are not part of the required local demonstration.
