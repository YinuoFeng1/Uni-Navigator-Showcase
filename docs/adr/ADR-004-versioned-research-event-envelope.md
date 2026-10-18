# ADR-004: Versioned Research Event Envelope

Status: accepted

Add a common versioned envelope for new pilot-critical events while retaining existing event writers. `EventRepository` enforces event-specific payload allowlists, excludes participant free text and secrets, and supports idempotency keys. No summary projection or full event-sourcing rewrite is included.
