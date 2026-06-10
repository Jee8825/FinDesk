#!/usr/bin/env python3
"""Dev-only OpenAI-compatible model server for the Recall memory stack.

Two endpoints, zero API cost, fully deterministic:

* ``/v1/embeddings`` — static embeddings via model2vec (torch-free, ~30MB
  potion-base-8M, CPU-instant).
* ``/v1/chat/completions`` — a stand-in LLM. For Recall's extraction prompt it
  returns the ingested span verbatim as one semantic fact (FinDesk writes
  pre-distilled single-fact sentences, so identity-extraction is appropriate
  in dev); for anything else it echoes a truncation (summarize role).

Memory stack config:

    RECALL_LLM_PROVIDER=local
    RECALL_EMBEDDING_PROVIDER=local
    RECALL_LOCAL_BASE_URL=http://host.docker.internal:8090/v1
    RECALL_EMBEDDING_MODEL=potion-base-8M
    RECALL_EMBEDDING_DIM=256

Run: .venv/bin/python infra/dev/embedding_shim.py   (serves :8090)
NOT for staging/prod — real deployments use hosted models (Anthropic/Qwen).
"""

from __future__ import annotations

import json
import re
import time

from fastapi import FastAPI
from model2vec import StaticModel
from pydantic import BaseModel

MODEL_NAME = "minishlab/potion-base-8M"

app = FastAPI(title="dev-embedding-shim")
_model: StaticModel | None = None


def get_model() -> StaticModel:
    global _model
    if _model is None:
        _model = StaticModel.from_pretrained(MODEL_NAME)
    return _model


class EmbeddingRequest(BaseModel):
    model: str = MODEL_NAME
    input: str | list[str]
    encoding_format: str | None = None


@app.post("/v1/embeddings")
async def embeddings(body: EmbeddingRequest) -> dict:
    texts = [body.input] if isinstance(body.input, str) else list(body.input)
    vectors = get_model().encode(texts)
    return {
        "object": "list",
        "model": body.model,
        "data": [
            {"object": "embedding", "index": i, "embedding": vec.tolist()}
            for i, vec in enumerate(vectors)
        ],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "dev-echo"
    messages: list[ChatMessage]
    max_tokens: int | None = None
    temperature: float | None = None


_SPAN_RE = re.compile(r"---\s*\n(.*?)\n---", re.DOTALL)
_NEW_BELIEF_RE = re.compile(r'New belief:\s*\n\s*content: "(.*?)"', re.DOTALL)


def _fake_completion(prompt: str) -> str:
    if "conflict-resolution component" in prompt:
        # Deterministic conservative stance: never auto-resolve a belief
        # conflict in dev — flag it for the human queue (which is also the
        # right default posture for a finance product).
        m = _NEW_BELIEF_RE.search(prompt)
        return json.dumps(
            {
                "resolution": "flagged",
                "resolved_belief": m.group(1) if m else "",
                "rationale": "dev-shim: contradictory beliefs always flagged for human review",
            }
        )
    if '"facts"' in prompt or "memory-extraction" in prompt:
        spans = _SPAN_RE.findall(prompt)
        content = spans[-1].strip() if spans else ""
        facts = (
            [{"content": content, "tier": "semantic", "confidence": 0.7, "cluster": "finance"}]
            if content
            else []
        )
        return json.dumps({"facts": facts})
    # summarize/other light roles: deterministic truncation
    words = prompt.split()
    return " ".join(words[-60:])


@app.post("/v1/chat/completions")
async def chat_completions(body: ChatRequest) -> dict:
    prompt = "\n".join(m.content for m in body.messages if m.role == "user")
    return {
        "id": f"devcmpl-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _fake_completion(prompt)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "model": MODEL_NAME, "dim": int(get_model().dim)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)
