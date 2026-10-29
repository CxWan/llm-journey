import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

API_KEY = os.environ["ZHIPU_API_KEY"]
CHAT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

app = FastAPI(title="llm-journey API", version="0.1.0")


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000, description="要摘要的原文")
    max_chars: int = Field(120, ge=20, le=500, description="摘要最多多少字")


class SummarizeResponse(BaseModel):
    summary: str
    total_tokens: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest):
    payload = {
        "model": "glm-4-flash",
        "messages": [
            {
                "role": "system",
                "content": f"你是摘要助手，用不超过 {req.max_chars} 字概括文本，只输出摘要本身。",
            },
            {"role": "user", "content": req.text},
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            CHAT_URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json=payload,
        )

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"上游错误 {r.status_code}: {r.text[:200]}")

    data = r.json()
    return SummarizeResponse(
        summary=data["choices"][0]["message"]["content"].strip(),
        total_tokens=data.get("usage", {}).get("total_tokens", 0),
    )