# Temporary External Testing Link

> Mac workstation helper, not a turnkey cloud deployment. The public repository
> does not include `.tools/bin/pnpm`, `.tools/bin/caddy` or `.tools/bin/cloudflared`.
> Supply those tools separately before using this helper. Use the root README
> for ordinary local startup. The specific Node path below is historical.

Share the existing Mac application through Cloudflare Quick Tunnel. This is not
cloud hosting: the Mac, network, and sharing processes must remain running. The
URL changes when the tunnel restarts. Cloudflare's HTTPS endpoint carries traffic
to a loopback-only Caddy gateway. The gateway proxies `/api/*` to FastAPI and other
paths to Next.js. No database, policy index, or API key is uploaded for hosting.

## Start, Status, Stop

From the repository root:

```bash
export CODEX_NODE_BIN="/Users/savtr/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
export PATH="$(dirname "$CODEX_NODE_BIN"):$PATH"
backend/.venv/bin/python scripts/public_test.py start
```

This Node path is for the current Mac. On another machine, set it to that machine's
real Node executable. Do not construct it using `$HOME` in this project's VS Code
terminal: workspace settings point `HOME` to the project's `.home` directory.
The launcher validates Node before building and passes the resolved path to its
background services. An invalid explicit path fails rather than using a different
Node executable silently.

The launcher builds `.next-public`, starts its own backend on `127.0.0.1:8001`,
frontend on `127.0.0.1:3100`, and gateway on `127.0.0.1:3101`, then prints the
external `/chat` URL. Ports 3000 and 8000 and the normal `.next` build remain
available for local development. Occupied sharing ports cause an explicit error.
The launcher exits after startup; the managed services continue in the background.

Startup allows up to two minutes for the new domain and external health endpoint
to become reachable before printing the link. `status`
and `start` for an already-running supervisor also check that endpoint rather than
assuming a live process means a usable URL. If the public link is unavailable,
they report an error with `stop` / `start` recovery instructions. This does not
automatically interrupt a test or restart services during a temporary outage.
Quick Tunnel registrations can disappear while the local connector keeps retrying;
`Tunnel not found` in `cloudflared.log` means the old connection must be recreated.

If startup previously failed with a missing `.home/.cache/.../node` path, apply the
exports above and run `start` again. The failed launch cleans up its own services;
it does not delete research data. For an expired external URL, run `stop` followed
by `start` to create a new temporary link.

```bash
backend/.venv/bin/python scripts/public_test.py status
backend/.venv/bin/python scripts/public_test.py stop
```

`stop` stops only services started by this launcher. Research records and local
development servers are not removed. `caffeinate` prevents idle sleep while the
launcher runs; closing the laptop lid or disconnecting the network can still
interrupt the link. Restart after code changes to rebuild the sharing frontend.

## Access

Participants open the `/chat` link directly without an account or password. Chat,
its assets, and its application API requests are public through the gateway.
Session attribution, the separate consent confirmation, save acknowledgements,
and formal-runtime checks are unchanged; removing the login is not removing these
research requirements.

The `researcher` credential unlocks `/admin`, every `/api/admin/*` endpoint,
CSV exports, and backend API documentation. It is generated once in
`.tools/public-test/access.json`, readable only by the current Mac user and excluded
from Git. The current researcher password is preserved. Previously generated
participant credentials are no longer used. Never share the researcher password
with participants. Use a private browser window to check access without cached
researcher credentials.

Unauthenticated Admin/export requests and invalid researcher passwords return
401. The gateway strips credentials before forwarding to application services,
does not write access logs, and sets no-store and noindex headers. Local HTTP
remains bound to loopback; external access is HTTPS. Do not point a tunnel directly
at the unprotected backend or frontend.

Anyone who obtains the link can ask questions, incur OpenAI charges, and submit
application activity. This temporary setup has no abuse rate limit and is not a
production public service. Send the link only to invited testers, keep testing
supervised, and stop sharing after the session. Do not enter personal case data.

The frontend sharing build deliberately sets `NEXT_PUBLIC_API_BASE_URL` to an empty
string so browser requests use the external origin, not the visitor's localhost.
Local builds retain the existing environment/default API URL. No `.env` is changed.

## Research Behaviour and Checks

The launcher uses the existing backend `.env`, OpenAI generation/embeddings,
official corpus, Chroma collection, and existing SQLite database. It refuses to
publish when Chroma is not active or fallback is used. It does not rebuild the
corpus or rewrite a frozen release. Live questions still incur the existing AI
provider charges; the temporary tunnel has no hosting subscription.

Starting the tunnel does **not** make development sessions formal research data.
The configured runtime, frozen release, consent procedure, and readiness checks
remain applicable; see [pilot_runbook.md](pilot_runbook.md). Development sessions
remain labelled as development. Use distinct synthetic verification labels, never
real names, and exclude verification sessions from participant analysis.

Before sharing, verify the public link in a fresh browser: Chat loading without a
password prompt, a synthetic live answer, citation/evidence interactions, session
completion, and researcher-only filtered exports. Check the same database for
backend acknowledgements. Inspect `.tools/public-test/*.log` if a service fails.
Do not send passwords, API keys, or raw participant records in diagnostic reports.

An explicit end-to-end API check is available (one billable live AI question):

```bash
backend/.venv/bin/python scripts/verify_public_test.py
```

This requires a development runtime and creates a synthetic `external-smoke-*`
round with `P9999`. It checks login-free public assets, protected Admin/exports,
real RAG citations, simulated evidence-action writes, session completion, filtered CSV exports, and
preservation of historical interaction IDs. It creates no human correctness or
feedback ratings. Exclude this round from analysis; retain the verification
record separately from participant data. It does not replace a manual browser
usability check or establish semantic correctness of the generated answer.

## Local Tools

No global package installation or sudo is required. The Apple Silicon Mac setup
uses official release archives, verified against the SHA-256 digests in GitHub's
release metadata, and extracts only the executables into ignored `.tools/bin`:

- Cloudflared 2026.9.3, `cloudflared-darwin-arm64.tgz`:
  `587c2cfb1c230fe36c7fa7727da78be459dae028cabe8c001291999350f07095`
- Caddy 2.11.6, `caddy_2.11.6_mac_arm64.tar.gz`:
  `4ad5a757d4ebb880e0a2bb333410a0089f09348d9e74693bcf13be0669675f6e`

Official downloads: [Cloudflared release](https://github.com/cloudflare/cloudflared/releases/tag/2026.9.3),
[Caddy release](https://github.com/caddyserver/caddy/releases/tag/v2.11.6).
Place `cloudflared` and `caddy` in `.tools/bin` on another Mac, with executable
permissions, before running the launcher. Choose the correct architecture and
check the official digests when installing a different version.

Cloudflare documents the testing-only lifetime of [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
Gateway authentication and routing use Caddy's maintained
[basic_auth](https://caddyserver.com/docs/caddyfile/directives/basic_auth) and
[reverse_proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
