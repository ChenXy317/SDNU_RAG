# 山师大知识库 RAG

山东师范大学校园知识问答。注册登录后提问，系统从公共语料和当前用户的私有文档里检索片段，用本地模型作答，并返回引用来源。

语料 `183` 篇，与 `knowledge/sdnu` 里的 txt 数量一致。

## 技术栈

FastAPI、LangChain、Qdrant、MySQL、Vue。

前端是 Vue 3 和 Ant Design Vue。登录页左侧是校徽和校训，登录后是侧栏：对话、文档、设置。

LangChain 实际用在三处：

- `RecursiveCharacterTextSplitter`：入库切分
- `ChatPromptTemplate`：system / user 模板
- `ChatOpenAI`：OpenAI 兼容对话接口，生成步是 `prompt | llm` 的流式调用。默认指向本机 Ollama 的 `/v1`

检索不走 LangChain。两个 Qdrant 集合要按用户合并，所以 `retrieve.py` 直接用 `qdrant-client`。

## 链路

```
语料 / 用户上传
    → 切分（320 / 48）
    → Ollama embedding（qwen3-embedding:0.6b，1024 维）
    → 写入 sdnu_public 或 sdnu_private

用户问题
    → 同一个 embedding
    → 公共集合 + 当前用户私有集合
    → 按余弦分合并，取 5 条；用户库有命中时至少留 1 条
    → prompt（片段带 [来源:公共] / [来源:用户]）
    → OpenAI 兼容 chat（默认本机 Ollama `/v1` 上的 qwen2.5:1.5b）SSE
    → citation → token → done
    → 整段完成后写入 MySQL
```

入库和查询共用 `llm.embed_texts`。只改对话模型不用重建向量库；换 embedding 模型必须重建集合并重新灌入。历史聊天是 MySQL 里的文本，不进 Qdrant，也不进当次 prompt。

## 模型配置

登录后打开「模型」。每个账号可以改自己的对话 `base_url`、`model`、`api_key`，下一次提问即生效，不用重启。配置只存在进程内存里，重启后回到 `.env`。

`api_key` 不会从接口返回。不填表示保持原值；点「清除密钥」会清掉。换成另一个地址时，如果密钥仍是环境变量里的那一份，会自动丢掉，避免把本机密钥带到新地址。`base_url` 只接受公网或本机回环，内网地址和云元数据地址会被拒绝。

向量模型仍是 `OLLAMA_EMBEDDING_MODEL`，页面只展示。本机 Ollama 不需要密钥，默认地址是 `http://127.0.0.1:11434/v1`。

两个集合：

- `sdnu_public`：全站一份公共语料。检索可以不带过滤。
- `sdnu_private`：用户上传。检索必须带 `user_id`，返回后再核对 payload。

公私内容冲突时，两边都留在 Context 里并打来源标签。模型应同时列出两边并说明存在冲突，不偷偷采信一边。本地 1.5B 对这条指令执行不稳定。演示冲突时在「模型」页把对话模型换成云端接口即可，向量库不用动。

## 登录范围

JWT HS256，载荷是 `sub`（user_id）、`email`、`exp`。有效期 12 小时。验签通过后信任 `sub`，不做刷新令牌，也不做吊销。改密或注销后，旧票在过期前仍然可用。

前端把 token 放在 `localStorage` 的 `access_token`，请求带 `Authorization: Bearer`。这是演示范围：页面上的脚本可以读到 token。第一版不做 HttpOnly Cookie。

## 启动

本机需要 MySQL 8 和 Ollama。Qdrant 由 compose 启动。对话模型默认 `qwen2.5:1.5b`，只适合本机演示。

```bash
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cp .env.example backend/.env
docker compose up -d
cd backend && uv sync && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd backend && uv run python ../scripts/seed.py
cd frontend && npm i && npm run dev
```

端口：前端 `5173`，API `8000`，Qdrant `6333`，Ollama `11434`，MySQL `3306`。Vite 把 `/api` 代理到 `8000`。

`scripts/seed.py` 可以重复执行。同一文件再次灌入会覆盖原来的 point，公共文档数保持和 txt 数量一致。

## 验收

- 问「山东师范大学的校训是什么」，引用里应出现 `01_学校简介.txt`，附近原文有「弘德明志、博学笃行」。
- 再上传一份把校训写成别的 txt，问同一句。引用应同时有公共和用户，答案应列出两边并说明冲突。
- 换一个账号登录，看不到前一个账号的会话和私有文档。

## 熟悉代码的顺序

1. `backend/app/ingest.py` 和 `llm.py`：切分、向量、写入
2. `backend/app/retrieve.py`：两路检索、合并、私有保底名额
3. `backend/app/rag.py` 和 `chat.py`：`prompt | llm`、citation、SSE、何时写助手消息
4. `backend/app/models.py` 和 `auth.py`：四张表、JWT 里有什么
5. 自己跑一遍上面的验收

前端只需要记住：登录后保存 token，请求带 Bearer，对话打 `/api/v1/chat/stream`，换对话模型打 `/api/v1/llm/config`。
