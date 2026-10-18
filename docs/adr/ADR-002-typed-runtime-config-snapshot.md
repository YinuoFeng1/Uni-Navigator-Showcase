# ADR-002: Typed RuntimeConfigSnapshot

Status: accepted

Create an immutable, non-secret runtime snapshot using canonical JSON and SHA-256. Resolution order is test/CLI override, environment, non-secret local configuration, then safe defaults. Participant-critical invalid modes/providers/releases fail clearly. API keys, credentials, absolute home paths, and raw provider errors are excluded.
