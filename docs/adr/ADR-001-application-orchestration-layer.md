# ADR-001: Application Orchestration Layer

Status: accepted

Use one `ChatOrchestrator` to coordinate context validation, pre-retrieval scope checks, OpenAI embedding, Chroma retrieval, official passage selection, OpenAI generation, citation validation, response construction, and provenance. It does not query SQLModel, import FastAPI request types, construct provider clients, or return SDK objects. The chat route owns persistence and every execution context uses this orchestrator.
