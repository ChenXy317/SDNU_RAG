# 山师大知识库 RAG — 实现计划

作品集项目：山东师范大学校园知识问答。只做一条能讲清楚的基本链路：入库、检索、生成、引用。

实现由 agent 完成，作者事后按第 16 节顺序熟悉代码。仓库必须保持薄：每个模块职责能用两三句话说明。

## 1. 目标与范围

注册登录后对校园语料提问，系统检索相关片段，用本地 LLM 作答，并返回引用来源。

- 公共语料全站一份，所有登录用户可检索。
- 用户的会话、私有上传彼此隔离。
- 公私内容冲突时：两边都进 Context 并打来源标签，模型应同时列出并明确指出冲突，不偷偷采信一边。
- 第一版只做基本登录（JWT 签发与校验），不做 token 吊销、刷新令牌、Cookie。

本机已具备：MySQL 8.4、Ollama（`qwen3-embedding:0.6b`、`qwen2.5:1.5b`）、语料 183 篇（来自 `/home/nehc/Projects/SDNU_Enterprise_RAG/knowledge/sdnu/`）。

验收提问：

- 「山东师范大学的校训是什么」应引用 `01_学校简介.txt` 中「弘德明志、博学笃行」附近片段。
- 用户再上传一份把校训写成别的 txt，同一句提问：citation 同时含公共与用户；答案同时列出两边并明确说存在冲突。

## 2. 主链路

```
语料 / 用户上传
    → RecursiveCharacterTextSplitter（320 / 48）
    → Ollama embedding（qwen3-embedding:0.6b，1024 维）
    → 写入对应 Qdrant 集合

用户问题
    → 同一 embedding
    → 并行检索：公共集合 + 当前用户私有集合
    → 按余弦分合并，取 5 条（用户库有命中时至少留 1 个名额）
    → 拼 prompt（片段带 来源:公共 / 来源:用户；冲突时两边都保留）
    → OpenAI 兼容 chat（默认本机 Ollama /v1，模型 qwen2.5:1.5b）SSE
    → 事件：citation* → token* → done
    → 整段完成后写入 MySQL 消息
```

换对话模型可以改 `.env`，也可以在登录后的「模型」页按当前账号覆盖 `base_url` / `model` / `api_key`。覆盖只在进程内存里，重启回到环境变量，向量库不动。换 embedding 模型必须重建集合并全量再灌。历史聊天是 MySQL 文本，永远不进 Qdrant。

## 3. 技术选型

| 层 | 选择 | 说明 |
|---|---|---|
| 后端 | FastAPI + Uvicorn | JSON + SSE |
| ORM | SQLAlchemy 2.x + PyMySQL | 本机 MySQL 8，库名 `rag`，字符集 utf8mb4 |
| 向量库 | Qdrant 两个集合 | 见第 5.2 节 |
| Embedding | Ollama `qwen3-embedding:0.6b` | HTTP `POST /api/embed` |
| LLM | OpenAI 兼容 chat，默认 Ollama `qwen2.5:1.5b` | `POST {base_url}/chat/completions`，页面可按账号覆盖 |
| 鉴权 | 注册 / 登录 + JWT HS256 | 请求头 `Authorization: Bearer` |
| 切分 / Prompt / Chat | LangChain | 切分器 + ChatPromptTemplate + ChatOpenAI，生成步 `prompt \| llm` |
| 检索 | `qdrant-client` 直连 | 双集合、用户 filter、按分合并，不用 VectorStore / RetrievalQA |
| 前端 | Vue 3 + Vite + Vue Router + Ant Design Vue | 纸感校色布局，对照旧项目页面 |
| 包管理 | 后端 uv；前端 npm | |

环境变量是启动默认值。对话模型可以在「模型」页按账号覆盖，只存在进程内存，重启回到环境变量。向量模型不能在页面上改。

后端主要依赖：`fastapi`、`uvicorn`、`sqlalchemy`、`pymysql`、`pydantic-settings`、`pyjwt`、`bcrypt`、`qdrant-client`、`httpx`、`langchain-text-splitters`、`langchain-core`、`langchain-openai`、`python-multipart`。

LangChain 的用法（必须在代码里真实出现，供简历关键词和面试指认）：

- `RecursiveCharacterTextSplitter`：入库切分
- `ChatPromptTemplate`：system / user 模板
- `ChatOpenAI`：指向当前账号的 `base_url` + `model`，默认是本机 Ollama 的 `/v1` 和 `OLLAMA_CHAT_MODEL`，流式
- 生成步一条短链：`chain = prompt | llm`，`astream` 推 token

embedding 仍走 Ollama `POST /api/embed`（与入库同一函数）。不用 `langchain-qdrant`、不用 `create_retrieval_chain` / RetrievalQA：双集合合并和 `user_id` filter 是本项目自己的逻辑，套进去反而讲不清。

## 4. 目录

根目录现有空 `main.py` 在第 1 步删除。最终结构：

```
RAG_Project/
  PLAN.md
  README.md
  .env.example
  docker-compose.yml              # 仅 Qdrant :6333
  knowledge/sdnu/                 # 183 篇 txt，从旧项目拷贝
  scripts/seed.py                 # 幂等灌入公共集合
  backend/
    pyproject.toml
    .env                          # gitignore
    data/uploads/{user_id}/       # 用户上传，gitignore
    app/
      main.py                     # FastAPI、CORS、lifespan、挂路由
      config.py                   # Settings
      db.py                       # engine、SessionLocal、get_db、init_db
      models.py
      schemas.py
      deps.py                     # 解析 JWT → user_id
      auth.py
      ingest.py                   # 切分、embed、upsert、按文档删除
      retrieve.py                 # 两路检索 + 合并
      rag.py                      # prompt、调 LLM
      chat.py                     # SSE
      documents.py
      qdrant_client.py            # 集合初始化、upsert、search、delete
      llm.py                      # embedding 的 httpx 封装
      llm_runtime.py              # 当前账号的对话模型覆盖
      llm_config.py               # GET/PUT /llm/config
  frontend/
    package.json
    vite.config.ts                # proxy /api → :8000
    src/main.ts
    src/App.vue
    src/api.ts                    # axios/fetch 封装，带 token
    src/pages/Login.vue
    src/pages/Chat.vue
    src/pages/Docs.vue
    src/pages/Settings.vue
```

每个后端文件职责：

| 文件 | 做什么 | 不做什么 |
|---|---|---|
| `config.py` | 读环境变量 | 默认值写死模型名以外的密钥 |
| `db.py` | 连接池、yield session、`create_all` | 业务 |
| `models.py` | 四张表 | 向量字段 |
| `auth.py` | register/login/me、哈希、签发 | 刷新令牌、黑名单 |
| `llm.py` | embed(texts)→list[list[float]]；chat_stream(messages) | 多 provider |
| `ingest.py` | 读文件、切分、embed、写 Qdrant、更新 Document | 队列 |
| `retrieve.py` | 两路 search + 合并 | 调 LLM |
| `rag.py` | ChatPromptTemplate + ChatOpenAI，`prompt \| llm` 流式；hits → citation | 鉴权、检索 |
| `llm_runtime.py` | 按 user_id 覆盖对话 base_url / model / api_key | 改 embedding、把密钥返回给前端 |
| `llm_config.py` | `GET/PUT /llm/config` | 落库 |
| `chat.py` | 落库、调 retrieve/rag、SSE | 编辑/重试消息 |
| `qdrant_client.py` | 集合 CRUD 的薄封装 | 业务 filter 策略以外的抽象层 |

禁止再加 `RetrievalClient` ABC、多套 embedding backend、worker。

## 5. 数据

### 5.1 MySQL

库名 `rag`，`utf8mb4`。只存业务状态，不存 chunk 全文。SQLAlchemy `create_all` 即可，第一版不上 Alembic。

**users**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | CHAR(36) | PK，UUID |
| email | VARCHAR(255) | UNIQUE，登录名 |
| password_hash | VARCHAR(255) | bcrypt |
| created_at | DATETIME | |

系统用户 `public`：

- 固定 id：`00000000-0000-4000-8000-000000000001`
- email：`public@local`
- password_hash 填不可登录的占位（随机哈希，不对外签发此用户的 JWT）
- lifespan 或 seed 时 `get_or_create`

**documents**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | CHAR(36) | PK |
| user_id | CHAR(36) | FK users.id，INDEX |
| filename | VARCHAR(512) | |
| storage_path | VARCHAR(1024) | 磁盘路径 |
| status | VARCHAR(32) | pending / processing / succeeded / failed |
| error_message | TEXT | 可空 |
| chunk_count | INT | 默认 0 |
| created_at / updated_at | DATETIME | |

唯一约束：`(user_id, filename)`。同一用户不能重复挂同名文件；seed 撞名则走「删旧向量再灌」而不是再插一行。

**chat_sessions**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | CHAR(36) | PK |
| user_id | CHAR(36) | FK，INDEX |
| title | VARCHAR(255) | 可空，首条用户消息前 40 字 |
| created_at / updated_at | DATETIME | |

**chat_messages**

| 字段 | 类型 | 约束 |
|---|---|---|
| id | CHAR(36) | PK |
| session_id | CHAR(36) | FK，ON DELETE CASCADE |
| user_id | CHAR(36) | INDEX，查询隔离 |
| role | VARCHAR(16) | user / assistant |
| content | TEXT | |
| citations_json | TEXT | 可空，assistant 用 |
| created_at | DATETIME | |

所有会话/文档查询必须带 `user_id = 当前用户`。`public` 的 documents 不出现在普通用户的 `/documents` 列表里。

### 5.2 Qdrant

两个集合，向量 1024 维，距离 Cosine。payload 索引：`user_id`、`document_id`，类型 KEYWORD。

**`sdnu_public`**

- 只放公共语料。
- payload.user_id 恒为 public 的 UUID。
- 检索此集合时可以不带 filter（集合内全是公共数据）。

**`sdnu_private`**

- 只放用户上传。
- 检索必须 `must: user_id = 当前用户`。
- 应用层对返回结果再断言 `payload.user_id == 当前用户`，对不上就丢弃并打日志。

point 结构（两集合相同）：

```
id: 确定性 UUID（见 5.3）
vector: float[1024]
payload:
  user_id: str
  document_id: str
  filename: str
  chunk_index: int
  text: str
  source: "public" | "user"
```

删除一篇文档：按 `document_id`（private 再加 `user_id`）删 point，同时更新/删除 MySQL 对应行。

### 5.3 点 id 与 seed 幂等

point id = UUID5(命名空间, `f"{user_id}:{filename}:{chunk_index}"`)。同一文件再灌是 upsert 覆盖，不会叠加。

`scripts/seed.py` 行为：

1. 确保 public 用户存在。
2. 扫描 `knowledge/sdnu/*.txt`（排序，保证稳定）。
3. 对每个文件：按 `(public, filename)` 找 Document；没有则插入 status=processing。
4. 切分、embed、upsert 到 `sdnu_public`。
5. 将该行标 succeeded，写入 `chunk_count`、`storage_path`。
6. 目录里已经消失、库里却还在的 public 文档：删 Qdrant point + 删 MySQL 行（可选，第一版至少打印警告）。

跑十遍后：MySQL 中 public 文档数 = 目录 txt 数；Qdrant `sdnu_public` 点数 = 各文件 chunk 数之和。禁止只清 Qdrant 或只清 MySQL。

## 6. 用户隔离

### 6.1 身份

- JWT payload：`sub`（user_id）、`email`、`exp`。算法 HS256。过期 12 小时。
- 不放密码，不放角色列表。
- 密码：bcrypt，cost 12。明文只在 register/login 请求里出现。
- 受保护接口依赖 `deps.py`：缺头或验签失败 → 401。
- 第一版验签通过后 **信任 `sub`**，不每请求查 users 表。`GET /auth/me` 可以查一次库，用户已删则 401。
- 改密/注销后旧票在 `exp` 前仍可用。第一版不做黑名单。README 写明这是演示范围。

### 6.2 数据

- SQL：sessions / messages / 用户 documents 一律 `user_id = sub`。
- 私有向量：只查 `sdnu_private` + filter。
- 公共向量：只查 `sdnu_public`。
- 用户 A 看不到 B 的文档列表、会话、私有 chunk。
- 不做 `tenant_id`、不做 `X-Tenant-Id`。

忘了给 `sdnu_private` 加 filter 是串数据（隐私事故）。实现时检索函数签名强制接收 `user_id`，禁止提供「无 user_id 的私有检索」。

## 7. HTTP 接口

前缀 `/api/v1`。JSON 用 camel 或 snake 选一种并贯穿前后端，推荐 **snake_case**。

### 7.1 鉴权

**POST `/auth/register`**

```
请求: { "email": str, "password": str }
成功 201: { "access_token": str, "token_type": "bearer", "user": { "id", "email" } }
失败 409: 邮箱已存在
失败 422: 邮箱格式非法或密码短于 8
```

**POST `/auth/login`**

```
请求: 同上
成功 200: 同 register
失败 401: 邮箱或密码错误（文案不区分哪一项）
```

**GET `/auth/me`** 鉴权 → `{ "id", "email" }`

### 7.2 文档

**GET `/documents`** 鉴权 → `{ "items": [ { id, filename, status, chunk_count, created_at } ] }`  
只返回当前用户上传的，不含 public。

**POST `/ingest`** 鉴权，`multipart/form-data` 字段 `file`。

- 第一版只收 `.txt`，其它 400。
- 同步：写盘 `data/uploads/{user_id}/{filename}` → 切分 → embed → upsert `sdnu_private` → 更新行。
- 成功 200：`{ id, filename, status, chunk_count }`
- 同名文件：覆盖（删旧 point，更新行），不 409。
- 失败：status=failed，error_message 写入，HTTP 500 或 400。

### 7.3 会话

| 方法 | 路径 | 行为 |
|---|---|---|
| GET | `/sessions` | 当前用户会话，按 updated_at 倒序 |
| POST | `/sessions` | 空会话 `{ id, title: null }` |
| GET | `/sessions/{id}` | 会话 + messages（含 citations）。别人的 id → 404 |
| DELETE | `/sessions/{id}` | 级联删消息 |

### 7.4 对话 SSE

**POST `/chat/stream`** 鉴权

```
请求: { "session_id": str, "message": str }
Content-Type: text/event-stream
```

处理顺序：

1. 校验 session 属于当前用户，否则 404。
2. 立刻插入 role=user 的消息（刷新后问句还在）。
3. 若 session.title 为空，用 message 前 40 字。
4. retrieve → 推送每条 `citation`。
5. rag 流式生成 → 推送 `token`。
6. 生成成功：插入 assistant 消息（content 全文 + citations_json），推 `done`。
7. 生成失败：推 `error`；不写 assistant 行；user 行保留。

SSE 事件（`event:` + `data:` JSON）：

```
event: citation
data: {"filename":"01_学校简介.txt","chunk_index":0,"text":"...","score":0.82,"source":"public"}

event: token
data: {"text":"弘"}

event: done
data: {"message_id":"...","answer":"完整答案"}

event: error
data: {"detail":"..."}
```

前端用 `fetch` + `ReadableStream` 读流（EventSource 不能自定义 Authorization 头）。

低分策略：集合非空时 Qdrant 几乎总会返回 k 条。仍然调用 LLM；system 要求片段不足就说没找到。前端始终展示 citation，便于判断是检索偏了还是模型在编。不对余弦分设绝对阈值（换模型会失效）。

## 8. 检索合并

```
public_hits  = search(sdnu_public,  vector, k=5)
private_hits = search(sdnu_private, vector, k=5, filter=user_id)

合并：按 score 降序去重（同一 document_id+chunk_index）
若 private_hits 非空且合并后的 top5 里一条私有都没有：
    丢掉 top5 里分数最低的公共命中，插入 private_hits[0]
截断为 5 条
```

同模型、同一余弦，两路分数可以直接比。保底名额防止 183 篇公共近邻把用户自己的一篇课表挤出 top-5。冲突场景下保底名额的意义是：私有那条必须进 top-5，模型才看得到两边。

prompt 里每条 context 前打标签：

```
[来源:公共] 文件:01_学校简介.txt
...正文...

[来源:用户] 文件:我的课表.txt
...正文...
```

### 8.1 公私冲突（产品策略）

用户上传与公共简介矛盾的内容（例如把校训写成别的）时，期望：

| 层 | 期望 |
|---|---|
| 检索 | top-5 里同时有公共 chunk 和用户 chunk（靠按分合并 + 私有保底名额） |
| prompt | 两条都在 Context 里，分别带 `[来源:公共]` / `[来源:用户]` |
| 引用 | SSE citation 两条都推，前端都能展开 |
| 答案 | 同时转述两边，并明确说存在冲突；不擅自裁定对错 |

system 写明：出现不同来源且内容不一致时，必须同时列出并指出冲突，不要只采用其中一方。模型无法判断哪边「正确」，裁定交给用户。

若答案仍只采用公共说法，按层排查（先检索后 prompt）：

1. 私有没进 top-5 → 合并 / 保底 / filter / 切分
2. 进了 top-5 但 prompt 里没打上 `[来源:用户]` → 拼 Context
3. Context 里两边都有，答案仍走单边 → 1.5B 没听 system（收紧指令或换更大的对话模型）

本地 1.5B 对「指出冲突」执行不稳，这是模型能力问题。策略仍按上表实现；演示冲突时可用云端对话模型，向量库不用重建。

## 9. 切分、embedding、Prompt

### 9.1 切分

语料带 `【主题】` 和小标题。

- `chunk_size=320`，`chunk_overlap=48`
- separators：`["\n【", "\n## ", "\n\n", "。", "\n", ""]`
- 空 chunk 丢掉；strip 后长度 < 20 的丢掉

切大（例如 1500）：一个向量摊上多个主题，关键句被稀释。  
切小（例如 50）：命题不完整，query 对不上半句。  
overlap：关键句落在切缝时，完整句至少出现在一个 chunk 里。

### 9.2 embedding

`POST {OLLAMA_BASE_URL}/api/embed`

```
{ "model": "qwen3-embedding:0.6b", "input": [ "chunk1", "chunk2", ... ] }
```

入库与查询走同一个函数 `embed_texts(texts: list[str]) -> list[list[float]]`。校验返回维数为 1024，否则抛错。批量大小 16 即可。

集合创建时把模型名写入 Qdrant collection 的 metadata 注释或本地常量；查询前可用日志打印，便于以后对不上模型时排查。第一版不做硬拒绝开关。

### 9.3 Prompt（LangChain）

`rag.py` 使用 `ChatPromptTemplate.from_messages`：

```
system:
你是山东师范大学校园知识助手。只根据提供的 Context 回答。
Context 不足时明确说没有找到相关信息，不要编造。
中文提问用中文回答。可在答案中点出文件名。
Context 中同时出现[来源:公共]与[来源:用户]且内容不一致时，必须同时列出两边的说法，并明确指出存在冲突，不要只采用其中一方。

user:
Context:
{context}

Question: {question}
```

```python
prompt = ChatPromptTemplate.from_messages([...])
llm = ChatOpenAI(base_url=..., model=..., api_key=..., temperature=0.2, max_tokens=512)
chain = prompt | llm
async for chunk in chain.astream({"context": context, "question": question}):
    ...
```

第一版 **不把多轮历史塞进 prompt**。历史只存在 MySQL，供前端回看。避免 1.5B 上下文被旧对话占满。`num_predict` / max tokens 取 512。

面试时指着这几行说：切分和生成用了 LangChain；检索因为要隔离用户、合并两个集合，所以直连 Qdrant。冲突策略是两边都进 Context、模型点明冲突，不是自动以用户为准。

## 10. 前端

三页，Vue 3 + Vite + Vue Router + Ant Design Vue。布局对照旧项目：侧栏、登录分栏、对话和文档卡片。

| 路由 | 页 | 行为 |
|---|---|---|
| `/login` | 登录/注册切换 | 成功后存 token，跳 `/chat` |
| `/chat` | 对话 | 左栏会话列表；消息区；输入框；引用可折叠 |
| `/docs` | 文档 | 上传 txt、表格显示 status/chunk_count |
| `/settings` | 模型 | 当前账号的对话 base_url / model / api_key；向量模型只展示 |

约束：

- `vite.config.ts` proxy：`/api` → `http://127.0.0.1:8000`
- token：`localStorage` 键 `access_token`；请求头 Bearer
- 无 token 访问 `/chat` `/docs` `/settings` 时跳 `/login`
- 无主题切换、无消息编辑/重试
- 模型页只改对话模型，不改向量模型
- SSE 用 fetch 流，按 `event:` 分帧解析
- citation 在第一个 token 前就能渲染
- 演示范围：token 放 localStorage，XSS 可被窃取；不改 HttpOnly Cookie（跨 5173/8000 还要处理 CSRF）

## 11. 配置与启动

`.env.example`：

```
DATABASE_URL=mysql+pymysql://rag:rag@127.0.0.1:3306/rag
QDRANT_URL=http://127.0.0.1:6333
QDRANT_PUBLIC_COLLECTION=sdnu_public
QDRANT_PRIVATE_COLLECTION=sdnu_private
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
OLLAMA_EMBEDDING_DIM=1024
OLLAMA_CHAT_MODEL=qwen2.5:1.5b
CHAT_BASE_URL=
CHAT_API_KEY=
JWT_SECRET=change-me
JWT_EXPIRE_HOURS=12
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

`docker-compose.yml` 只起 Qdrant（镜像 `qdrant/qdrant`，端口 6333，数据卷本地）。MySQL、Ollama 用本机已有服务。

启动顺序：

1. MySQL 建库：`CREATE DATABASE rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;` 以及专用账号（或沿用本机 root，`.env` 写明）。
2. Ollama 已有两个模型。
3. `docker compose up -d`
4. `cd backend && uv sync && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
5. `uv run python ../scripts/seed.py`（或 `cd` 到仓库根执行，脚本自己找 knowledge 路径）
6. `cd frontend && npm i && npm run dev`

lifespan：`init_db()`、确保两个 Qdrant 集合存在、确保 public 用户存在。

## 12. 明确不做

- 多租户、`tenant_id`、`X-Tenant-Id`
- Redis、限流、入库队列、Celery
- 多种 embedding backend、HashEmbeddings
- 在页面上改 embedding 模型
- 把对话模型配置写入数据库或 `.env`
- LangChain RetrievalQA / create_retrieval_chain / VectorStore 整链封装
- Ragas、评测套件
- Alembic（第一版）
- chunk 正文镜像进 MySQL
- 消息编辑、重试截断、多轮进 prompt
- 刷新令牌、登出黑名单、HttpOnly Cookie
- 把 Qdrant / MySQL / Ollama 端口打到 Cloudflare 隧道（以后远程部署只透前端和 API）

## 13. 落地顺序

| 步 | 内容 | 完成标准 |
|---|---|---|
| 1 | 目录、gitignore、`.env.example`、compose、拷贝 183 篇、删根 `main.py` | 结构符合第 4 节 |
| 2 | Settings、DB、四张表、register/login/me | curl 能拿到 token 和 me |
| 3 | qdrant 集合 + llm.embed + ingest | 登录后上传一个 txt，Qdrant private 集合能搜到对应 text |
| 4 | retrieve 合并 + rag + SSE | curl 流式问校训，事件里出现 `01_学校简介.txt`（需先有公共数据；可本步先手灌一篇简介） |
| 5 | seed 幂等灌 183 篇 | 跑两遍，文档数与 txt 数一致；问校训引用简介 |
| 6 | 会话 CRUD 收口 | 刷新页面问句还在，半句流不会进历史 |
| 7 | Vue 三页 | 浏览器可注册、提问、看引用、上传私有 txt |
| 8 | README | 架构、启动、链路、登录范围、语料篇数与仓库一致 |

每一步可独立演示。前端未完成前用 curl/httpie 验收后端。

## 14. 答错时怎么查（实现后自测也用这个）

对照三份材料：Qdrant top-5（文件名、分数、原文）、最终 prompt、模型输出。

| 情况 | 判据 |
|---|---|
| 没召回对 | top-5 没有校训，但源文件 `01_学校简介.txt` 里有 |
| 召回了对、模型没用 | prompt 的 Context 已有「弘德明志、博学笃行」，答案却是别的 |
| 语料里没有 | 源文件全文也没有这句话 |

模型说「不知道」只是旁证。seed 重复时：同一段以两条近乎同分的 point 出现，top-5 被占位。

## 15. README 必须写清的事实

- 183 篇语料，与 `knowledge/sdnu` 文件数一致。
- 技术栈写明 FastAPI、LangChain、Qdrant、MySQL、Vue（HR / 招聘系统扫词用）。
- LangChain 实际用在：切分、Prompt、ChatOpenAI 流式生成。对话模型可在页面按账号覆盖，向量模型不行。
- 入库与查询同一个 embedding；只换 chat 不用重建库。
- 两个 Qdrant 集合的职责。
- JWT 第一版范围：12 小时过期，无吊销。
- 本地演示用 1.5B；对话模型可换成云端而不动向量。
- 启动命令与端口。

禁止写「企业级多租户」「RetrievalQA 全链路」等代码里没有的能力。LCEL 只写生成那一截 `prompt | llm`，与代码一致。

## 16. 做完后熟悉代码的顺序

不要求通读仓库。按这个走一遍即可对应面试：

1. `ingest.py` + `llm.py` 的 embed：切分 → 向量 → 写入  
2. `retrieve.py`：同模 embed、两路检索、合并与保底名额  
3. `rag.py` + `chat.py`：`prompt | llm`、citation 从 hit 来、SSE 顺序、何时写 assistant  
4. `models.py` + `auth.py`：四张表、JWT 里有什么  
5. 自己操作：seed → 问校训看引用 → 上传一份改写校训的 txt 再问同一句，citation 应同时有公共和用户，答案应点出冲突 → 第二个账号注册，确认看不到第一个人的会话和私有文档

前端只需记住：登录存 token、请求带 Bearer、对话打 `/chat/stream`。

## 17. 面试可用的固定说法

1. 入库和查询必须同一 embedding：维数相同只说明长度一样，坐标系由模型决定；换 embedding 要重建 Qdrant。  
2. chunk 正文只在 Qdrant，MySQL 管账号和任务状态；当次引用读 payload.text，历史读 messages.citations_json。  
3. 公共一份、私有一份集合；合并按分，用户有命中时至少留一个私有名额。忘了 private filter 是泄密。公私冲突时两边都进 prompt 并打标签，答案要指出冲突，不偷偷采信一边。  
4. SSE 先 citation 再 token，因为引用在检索阶段就有了。切分和生成用 LangChain，检索直连 Qdrant。  
5. 切分：大了稀释、小了破碎、overlap 保边界完整。  
6. 招生简章更新：改 txt 再 ingest，不用动 LLM 权重；citation 是证据链。  
7. 登录是基本版：信 JWT 的 sub，改密不作废旧票。
