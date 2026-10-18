# ADR-006: Provider Adapters and Composition Root

Status: accepted

Use a lightweight `ProviderRegistry` and application container rather than a dependency-injection framework. AI, embedding, and vector adapters are constructed once at startup and expose requested/active identity. Isolated automated tests may inject provider doubles. All application chat contexts require OpenAI generation, OpenAI embeddings, Chroma, and no silent fallback answers.
