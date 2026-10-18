# Uni-Navigator Frontend

UQ-inspired student-facing prototype for a source-aware university policy chatbot.
The frontend supports the HCI study flow described in the development document:
landing page, mock chat, four evidence display conditions, study mode, and an
admin dashboard with mock logs.

## Routes

- `/` landing page
- `/chat` student chatbot prototype
- `/study` controlled HCI study interface
- `/admin` researcher dashboard mockup

## Local Development

This workspace includes a local pnpm wrapper one level above the project. From
the `frontend` directory:

```bash
node ../.tools/pnpm/package/bin/pnpm.cjs dev
```

Open [http://localhost:3000](http://localhost:3000).

For a production preview:

```bash
node ../.tools/pnpm/package/bin/pnpm.cjs build
node node_modules/next/dist/bin/next start -p 3001
```

## Checks

```bash
node ../.tools/pnpm/package/bin/pnpm.cjs lint
node ../.tools/pnpm/package/bin/pnpm.cjs exec tsc --noEmit
node ../.tools/pnpm/package/bin/pnpm.cjs build
```

## Notes

- The UI uses mock data only. There is no backend integration yet.
- The app avoids "100% accurate" or "official decision" language by design.
- The Next.js scripts use Webpack because this Codex environment cannot load
  the native SWC binary; SWC falls back to WASM during build.
- Tailwind is pinned to v3 so the toolchain stays pure JavaScript in this
  environment.

## VSCode

The project includes `.vscode` settings, extension recommendations, and tasks
for running or building the prototype.
