# ADR-005: Live LLM Pilot Configuration Boundary

All chat contexts use source-aware live RAG with `AI_PROVIDER=openai`. Mock, prewritten, and local fallback answer paths are prohibited. `answer_mode` is recorded as the constant `live_llm`; it is not a selectable runtime strategy.

An evaluation round fixes the model, prompt version, generation parameters, embedding and vector configuration, retrieval settings, corpus and scope versions, and application revision. Actual answers and provenance are recorded; generated wording can vary.

The retained backend release manifest also binds task and condition fields from the earlier study design. The current Chat UI has no task or condition selection; it supplies a researcher-started session, with the single presentation resolved by the server. Formal sessions still require a valid frozen configuration. See [study_flow.md](../study_flow.md) and [pilot_runbook.md](../pilot_runbook.md). Historical manifest fields are not a requirement to reintroduce experimental conditions or fixed answers.
