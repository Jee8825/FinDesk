"""Dev-only OpenAI-compatible shim for the vendored Recall stack.

Serves the two endpoints the ``local`` provider hits:

- ``POST /v1/embeddings``       → model2vec ``potion-base-8M`` (256-dim, CPU, no key)
- ``POST /v1/chat/completions`` → deterministic prompt-aware replies (the
  ``dev-echo`` model): extraction prompts get one fact echoing the raw content,
  conflict prompts are always "flagged" for human review (the FinDesk conflicts
  UI annotates exactly this), classify falls back to ``labels[0]``.

Run on the host:  ``python memory/infra/dev/embedding_shim.py``  (port 8090).
Referenced by ``memory/.env`` (RECALL_LOCAL_BASE_URL). Never used in prod.
"""

from __future__ import annotations

import json
import re
import time
import uuid

import uvicorn
from fastapi import FastAPI
from model2vec import StaticModel
from pydantic import BaseModel

app = FastAPI(title="recall-dev-shim")
_model = StaticModel.from_pretrained("minishlab/potion-base-8M")


class EmbeddingsIn(BaseModel):
    model: str
    input: str | list[str]


@app.post("/v1/embeddings")
def embeddings(body: EmbeddingsIn) -> dict:
    texts = [body.input] if isinstance(body.input, str) else body.input
    vectors = _model.encode(texts)
    return {
        "object": "list",
        "model": body.model,
        "data": [
            {"object": "embedding", "index": i, "embedding": vec.tolist()}
            for i, vec in enumerate(vectors)
        ],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }


class ChatIn(BaseModel):
    model: str
    messages: list[dict]
    temperature: float | None = None
    max_tokens: int | None = None


def _dev_reply(prompt: str, max_tokens: int | None) -> str:
    if "memory-extraction component" in prompt:
        m = re.search(r"Conversation:\n---\n(.*?)\n---", prompt, re.DOTALL)
        content = (m.group(1).strip() if m else prompt.strip())[:2000]
        facts = [{"content": content, "tier": "semantic", "confidence": 0.9,
                  "cluster": "findesk-dev"}] if content else []
        return json.dumps({"facts": facts})
    if "conflict-resolution component" in prompt:
        m = re.search(r'New belief:\s*\n\s*content: "(.*?)"\n', prompt, re.DOTALL)
        return json.dumps({
            "resolution": "flagged",
            "resolved_belief": m.group(1) if m else "",
            "rationale": "dev-shim: contradictory beliefs always flagged for human review",
        })
    if "Choose exactly one label" in prompt:
        return ""  # classify() falls back to labels[0]
    return prompt[: max_tokens or 64]  # summarize etc.: truncated echo


@app.post("/v1/chat/completions")
def chat(body: ChatIn) -> dict:
    last = body.messages[-1].get("content", "") if body.messages else ""
    reply = _dev_reply(last, body.max_tokens)
    return {
        "id": f"chatcmpl-dev-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True, "dim": int(_model.dim) if hasattr(_model, "dim") else 256}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090)
