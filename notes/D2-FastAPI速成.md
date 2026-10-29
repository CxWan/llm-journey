# D2 笔记 · FastAPI 速成

> 日期：2026-10-29
> 对应计划：D2「FastAPI 速成，写出 /summarize 接口」
> 用途：当日复盘 + 面试前复习
> 状态：代码已在 Python 3.14.6 实际环境跑通（见第九节测试结果）

---

## 一、为什么要从"脚本"走到"服务"

`hello_api.py` 能跑，但三个致命限制：

| 限制 | 后果 |
|---|---|
| 只有自己能跑 | 别人无法访问，无法演示、无法接前端 |
| 跑完就退出 | 不是常驻进程，无法持续提供服务 |
| 没有接口契约 | 输入输出只能看代码猜，无法被其他程序调用 |

**Web 服务的本质：让代码成为一个常驻进程，监听端口，等别人发 HTTP 请求。**

这是"作业"和"作品"的分界线。

---

## 二、补齐 HTTP 知识

### 方法

| 方法 | 语义 | 用途 |
|---|---|---|
| `GET` | 读取，不该改变数据 | 查列表、查详情、健康检查 |
| `POST` | 提交，会改变数据 | 提交文本、上传文件、发起对话 |
| `PUT` / `PATCH` | 更新 | 改配置 |
| `DELETE` | 删除 | 删会话 |

### 状态码

| 码 | 含义 | 何时用 |
|---|---|---|
| `200` | 成功 | 正常返回 |
| `404` | 路径不存在 | 访问了没写的接口 |
| `422` | 参数校验失败 | 空字符串、类型错（FastAPI 自动返回） |
| `500` | 服务端自身崩了 | 代码 bug |
| `502` | 上游（大模型）出错 | 厂商 API 返回错误 |

**设计原则：客户端错 → 4xx；服务端/上游错 → 5xx。**

---

## 三、FastAPI 与 uvicorn 的分工（新手最易混）

```
main.py        业务逻辑：什么路径 → 做什么事
   ↓
FastAPI 对象   路由表 + Pydantic 校验 + 自动生成 OpenAPI 文档
   ↓
uvicorn        真正监听 8000 端口、收发 HTTP、把请求转给 FastAPI
```

uvicorn 是 **ASGI 服务器**（服务员），FastAPI 是**厨房**。没有 uvicorn，FastAPI 只是一个没人访问的 Python 对象。

启动命令逐段拆解：

```powershell
uv run uvicorn main:app --reload
#        ↑      ↑    ↑    ↑
#     项目环境  文件  对象名  改代码自动重启（仅开发用）
```

---

## 四、为什么选 FastAPI

| 特性 | 对你的意义 |
|---|---|
| 自动生成 `/docs` | 零成本演示、零成本自测 |
| Pydantic 校验 | 声明式，不用写一堆 if |
| 类型提示驱动 | 编辑器补全 + 报错定位 |
| 原生异步 | 调大模型这类等待型任务并发能力强 |
| 轻量 | 一个文件即可启动 |

---

## 五、Pydantic：校验声明化

```python
# 传统写法
if not text or len(text) > 8000:
    return 400

# FastAPI 写法
class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
```

`...` 表示必填；`ge`/`le` 是数值上下界。不合法自动 422 并附带精确错误位置。

---

## 六、完整代码（main.py，已实测）

```python
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
```

要点：

| 代码 | 作用 |
|---|---|
| `@app.post("/summarize")` | 声明路由 |
| `response_model=SummarizeResponse` | 输出也校验 + 进文档 |
| `async def` + `await` | 等上游时让出 CPU，别的请求能进来 |
| `HTTPException(502, ...)` | 主动返回错误码，而不是崩成 500 |
| `httpx` 而非 `requests` | 前者支持 async |

---

## 七、启动与验收

```powershell
uv add fastapi uvicorn httpx
uv run uvicorn main:app --reload
```

浏览器打开 **http://127.0.0.1:8000/docs** → 展开 `POST /summarize` → Try it out → Execute。

请求体示例：

```json
{
  "text": "检索增强生成（RAG）是一种把外部知识库的检索结果注入大模型上下文的技术……",
  "max_chars": 50
}
```

`200` + 一段摘要 = 成功。

> 端口占用就加 `--port 8001`。终端窗口要保持不关。

---

## 八、环境排错（本机实测踩到的两个坑）

### 坑 1：uv 不读 pip 的镜像配置

你之前配的是 `pip config set global.index-url ...`，**uv 完全不看这个配置**。uv 要单独配：

```powershell
uv add --default-index https://pypi.tuna.tsinghua.edu.cn/simple 包名
# 或永久生效（写用户级配置）
uv config --global index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### 坑 2：`HTTPS_PROXY` 指向一个没启动的代理

本机环境变量：

```
HTTPS_PROXY = http://127.0.0.1:7890   ← 但 7890 端口没有进程监听
no_proxy    = localhost,127.0.0.1,api.deepseek.com,open.bigmodel.cn,::1,[::1]
```

后果：所有 pip / uv 下载都报

```
tunnel error: failed to create underlying connection
tcp connect error: 由于目标计算机积极拒绝，无法连接。 (os error 10061)
```

**这不代表没网**——浏览器直连正常（实测清华镜像返回 200）。是代理变量在误导工具。

三种解法（任选其一）：

```powershell
# ① 把代理客户端（Clash 等）启动起来，让它真的监听 7890

# ② 临时清空代理变量（只影响当前窗口）
Remove-Item Env:HTTPS_PROXY, Env:HTTP_PROXY -ErrorAction SilentlyContinue

# ③ 让 NO_PROXY 覆盖所有域名
$env:NO_PROXY = "*"
```

> 注意 ③ 的副作用：httpx 解析含 IPv6 的 no_proxy 规则可能报
> `Invalid port: ':1]'`。所以**跑 Python 代码时清空代理变量比设 `NO_PROXY=*` 更稳**。

### 坑 3（非错误）：`uv init` 依赖目录名

`uv init --bare` 会从**当前目录名**推断项目名。目录名含下划线开头、空格、中文等非法字符时直接报错：

```
error: The current directory (`_verify_d2`) is not a valid package name.
```

解法：加 `--name`。

```powershell
uv init --bare --name my-project
```

---

## 九、实测验证结果

环境：Python 3.14.6 / fastapi 0.162.0 / starlette 1.10.0 / pydantic 2.14.1 / httpx 0.28.1 / uvicorn 0.54.0

| 用例 | 期望 | 实际 | 结果 |
|---|---|---|---|
| `GET /health` | 200 `{"status":"ok"}` | 一致 | PASS |
| `POST /summarize` `{"text": ""}` | 422 | 422 | PASS |
| `POST /summarize` `{"text": 123}` | 422 | 422 | PASS |
| `POST /summarize` `{}`（缺字段） | 422 | 422 | PASS |
| `POST /summarize` `{"text":"你好","max_chars":10}` | 422 | 422 | PASS |
| 合法请求 + 假 Key | 502 + 上游原始错误 | 502，`detail` 含 `401 令牌已过期或验证不正确` | PASS |
| `GET /openapi.json` | 含 `/summarize` | 含 `/health`、`/summarize` | PASS |

**结论：代码逻辑、校验、错误处理、文档生成全部正常。**

小提示：用 `TestClient` 时会有 `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`——**只影响测试客户端，不影响生产运行**。

---

## 十、拓展知识（面试向）

### ① 同步 vs 异步到底差在哪

```python
def summarize(req):        # 普通 def → FastAPI 丢到线程池
async def summarize(req):  # async def → 在事件循环里跑
```

区别在**等待时做什么**：

- 同步：等智谱 3 秒，线程被占住干等
- 异步：`await` 期间让出控制权，事件循环处理别的请求

**IO 密集型（调 API、读写 DB、读文件）→ async 收益巨大。**
**CPU 密集型（纯计算、本地推理）→ async 无收益，要 `run_in_threadpool`。**

> 面试题「FastAPI 为什么快？」答：Starlette（ASGI）+ 原生 async，IO 并发强。**别说成"Python 更快"。**

### ② `--reload` 为什么不能上生产

文件监控随时重启 → 请求中断、内存翻倍、启动变慢。生产用
`gunicorn -k uvicorn.workers.UvicornWorker -w 4`（多进程）。D23 写 Dockerfile 时会用。

### ③ CORS

浏览器同源策略：Gradio（`:7860`）调 API（`:8000`）会被拦。解法是 `CORSMiddleware`。D24 会遇到。

### ④ 依赖注入 Depends

```python
def get_client() -> AsyncClient:
    return AsyncClient(timeout=60)

@app.post("/summarize")
async def summarize(req: SummarizeRequest, client: AsyncClient = Depends(get_client)):
    ...
```

好处：可测试（替换假客户端）、可复用（鉴权、DB 连接都这么写）。D21 重构时用。

### ⑤ 为什么不直接用 Gradio 连大模型

**接口才是资产。** 有了 `/summarize`：可接 Gradio（D6）、可接 React、可被 Agent 调用（D17 MCP）。
**Gradio 是皮肤，FastAPI 是骨架。**

---

## 十一、自测题

1. FastAPI 和 uvicorn 各干什么？（三）
2. 为什么校验用 Pydantic 而不写 if？（五）
3. `async def` 和 `def` 在 FastAPI 里的区别？（十①）
4. 什么错误该 4xx，什么该 5xx？（二）
5. 为什么用 `httpx` 不用 `requests`？（六）
6. uv 下载报 `tunnel error` 先查什么？（八）

---

## 十二、作业清单

| # | 作业 | 验收 |
|---|---|---|
| 1 | 跑通 `POST /summarize` | `/docs` 里 Execute 出 200 + 摘要 |
| 2 | `{"text": ""}` | 422，错误指出 text 太短 |
| 3 | `{"text": 123}` | 422，错误指出类型应为 string |
| 4 | Key 改错（记得改回） | 502，detail 含上游原始报错 |
| 5 | 自加 `GET /models` | 返回模型列表，`/docs` 可见 |
| 6 | `git push` | GitHub 上有 `main.py`、`notes/`、`uv.lock` |
