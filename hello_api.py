import os

from dotenv import load_dotenv
from openai import OpenAI

# ① 把 .env 里的变量读进 os.environ
load_dotenv()

# ② 建客户端：告诉它"钥匙"和"去哪个服务器"
client = OpenAI(
    api_key=os.environ["ZHIPU_API_KEY"],
    base_url="https://open.bigmodel.cn/api/paas/v4/",
)

# ③ 发一次请求
resp = client.chat.completions.create(
    model="glm-4-flash",
    messages=[
        {"role": "system", "content": "你是一个简洁的助手，回答不超过两句话。"},
        {"role": "user", "content": "用一句话解释什么是 RAG。"},
    ],
    temperature=0.7,
)

# ④ 从响应里把文字取出来
print(resp.choices[0].message.content)
print("-" * 40)
print(resp.usage)