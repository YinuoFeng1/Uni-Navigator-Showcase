FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
RUN npm install --global pnpm@11.2.2
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
ENV NEXT_PUBLIC_API_BASE_URL="" NEXT_PUBLIC_CLOUD_DEMO=true NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ANONYMIZED_TELEMETRY=False \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
COPY backend/requirements.txt backend/requirements.txt
COPY deploy/cloud/requirements.txt deploy/cloud/requirements.txt
RUN pip install --no-cache-dir -r deploy/cloud/requirements.txt
COPY backend/ backend/
COPY data/corpus/corpus_scope.json data/corpus/corpus_scope.json
COPY data/study/experimental_conditions.json data/study/experimental_conditions.json
COPY deploy/cloud/ deploy/cloud/
RUN python deploy/cloud/bootstrap_index.py --output /app/data/vector_store/demo
COPY --from=frontend /build/frontend/out /app/frontend/out
RUN useradd --create-home demo && chown -R demo:demo /app
USER demo
ENV APP_ENV=cloud_demo STUDY_MODE=development EXECUTION_CONTEXT=development \
    UNI_NAVIGATOR_DB_PATH=/tmp/uni-navigator-demo/activity.db \
    AI_PROVIDER=openai AI_MODEL=gpt-5.4-mini-2026-03-17 \
    EMBEDDING_PROVIDER=openai EMBEDDING_MODEL=text-embedding-3-small \
    VECTOR_STORE_PROVIDER=chroma VECTOR_STORE_ALLOW_FALLBACK=false \
    VECTOR_STORE_PATH=data/vector_store/demo VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_openai \
    RETRIEVAL_SOURCE_MODE=official RETRIEVAL_TOP_K=5 \
    RETRIEVAL_PARTIAL_SCORE_THRESHOLD=0.35 RETRIEVAL_GROUNDED_SCORE_THRESHOLD=0.55 \
    PROMPT_TEMPLATE_VERSION=grounded-v9 GENERATION_TEMPERATURE=0 \
    GENERATION_MAX_TOKENS=400 GENERATION_REASONING_EFFORT=none \
    CLOUD_DEMO_CHAT_LIMIT=30
WORKDIR /app/backend
CMD ["sh", "-c", "exec uvicorn cloud_demo:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --no-access-log"]
