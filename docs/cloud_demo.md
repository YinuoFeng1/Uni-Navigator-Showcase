# Free cloud demonstration

This deployment lives on `codex/cloud-demo`. The two historical showcase commits
on `main` and the original private research repository are unchanged.

## Data and runtime

- One Docker web service serves an exported Next.js frontend and FastAPI.
- The original ChatOrchestrator, OpenAI generation/embedding and Chroma are used.
- Only official policy passages and their existing embeddings are bundled.
  Startup/build does not make embedding API calls. Original PDFs are not uploaded;
  citations open the official UQ source URLs.
- No participant data, research DB, API keys or evaluation results are packaged.
- Demo questions/activity use an isolated temporary SQLite database, not formal
  participant records. The page discloses OpenAI processing and temporary storage.
- All admin, export, session management, API documentation and design-lab routes
  are inaccessible. This is an API allowlist, not only hidden navigation.

## Render settings

- Source: public `YinuoFeng1/Uni-Navigator-Showcase`, branch `codex/cloud-demo`.
- Runtime: Docker; Dockerfile: `deploy/cloud/Dockerfile`; build context: repository root.
- Instance: **Free**. Health check: `/healthz`.
- Secret environment variable: `OPENAI_API_KEY`. Never commit this value.
- `APP_REVISION`: deployed Git commit SHA.
- Use a dedicated OpenAI project/key where possible, with usage monitoring.

Free hosting is not free OpenAI usage. The API allows only one answer at a time,
at least 10 seconds between accepted chat requests, and defaults to 30 attempts
per process lifetime (`CLOUD_DEMO_CHAT_LIMIT`, 1-100). Failed attempts also count.
Other API posts are limited to 120/minute globally; JSON bodies are capped at
16 KB. These shared limits can be exhausted by visitors. They are not a monthly
spending guarantee: restarts reset the process counters. Stop the service or
revoke its API key to stop API spending.

Render Free sleeps after 15 idle minutes, can take about a minute to wake, and
does not provide persistent disks. Runtime demo logs can disappear. The bundled
policy index survives because it is in the image. Do not collect study data here.
No paid resources or automatic paid upgrades are required. Check Render usage
limits and payment settings before publishing.

## Updating the index

Run `scripts/export_demo_index.py --source <original-Chroma-directory> --output
deploy/cloud/policy_index.json.gz` with a Python environment containing Chroma.
The exporter reads a temporary snapshot, selects official active records and
allowlists public metadata. It never modifies the original index or research DB.
Review this generated bundle before publishing changes to it.

## Verification

Run the backend tests and frontend test/lint/typecheck/build checks. Build the
cloud frontend with `NEXT_PUBLIC_CLOUD_DEMO=true NEXT_PUBLIC_API_BASE_URL=`.
Check `/healthz` reports Chroma, no fallback, and the expected official counts.
Verify `/admin`, `/api/admin/logs`, `/docs` and session activation return 404.
Finally submit a synthetic policy question, inspect citation navigation and the
official source link. This last check uses the OpenAI API and incurs usage.

Reference: https://render.com/docs/free
