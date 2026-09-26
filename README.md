# 山师大知识库 RAG

山东师范大学校园知识问答。注册登录后提问，系统从公共语料和当前用户的私有文档里检索片段，用对话模型作答，并在回答前返回引用来源。

公共语料是 `knowledge/sdnu` 下的 183 篇 txt，内容覆盖学校简介、招生、校历、奖助、教务，以及实验课、占座、体测这类校园说明。由 `scripts/seed.py` 灌入。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 前端 | Vue 3、Vue Router、Ant Design Vue、Vite、TypeScript |
| 接口 | FastAPI、Uvicorn、Pydantic |
| 对话生成 | LangChain（`ChatPromptTemplate`、`ChatOpenAI`），走 OpenAI 兼容接口 |
| 切分 | LangChain `RecursiveCharacterTextSplitter` |
| 向量 | Ollama 原生 `/api/embed`，默认 `qwen3-embedding:0.6b`，1024 维，余弦距离 |
| 向量库 | Qdrant，集合 `sdnu_public`、`sdnu_private` |
| 业务数据 | MySQL 8、SQLAlchemy |
| 登录 | JWT（HS256）、bcrypt |

检索不经过 LangChain。公共库和当前用户的私有库要分开查再合并，所以直接用 `qdrant-client`。

向量和对话是两条链路。向量固定走本机 Ollama。对话默认是本机 Ollama `/v1` 上的 `qwen2.5:1.5b`，页面上可以换成任意 OpenAI 兼容地址。只换对话模型不用重建向量库；换 embedding 模型必须重建集合并重新灌入。

## 实现了什么

### 账号与隔离

- 邮箱注册、登录。密码用 bcrypt，至少 8 个字符，最长 72 字节。
- 登录后签发 JWT，有效期 12 小时，载荷是用户 id、邮箱和过期时间。前端放在 `localStorage` 的 `access_token`，请求带 `Authorization: Bearer`。
- 页面上的「退出」只清除本地令牌。服务端没有吊销名单，过期前旧令牌仍然有效。
- 文档、会话、消息都按 `user_id` 查询。私有向量检索必须带当前用户的 `user_id`，返回后再核对 payload，对不上就丢掉。
- 公共语料挂在固定账号 `public@local` 上。这个账号的密码是随机哈希，不对外登录。

### 语料入库

- 公共语料用 `scripts/seed.py` 灌入，可以重复执行。同一文件再次灌入会覆盖原来的向量；目录里删掉的 txt 会清掉对应文档和向量。灌完后公共文档数必须和 txt 数量一致。
- 私有文档在页面上传，只收 UTF-8 的 `.txt`。同一账号同名文件会覆盖。文件落在 `backend/data/uploads/{用户 id}/`。
- 切分长度 320 字，重叠 48 字，优先在标题和句号处切开。短于 20 字的块丢掉。
- 向量每批 16 条写入。每个点的 id 由用户、文件名和块序号稳定生成，重复入库覆盖同一个点。
- 点上的 payload 有 `user_id`、`document_id`、`filename`、`chunk_index`、`text`、`source`。`source` 是 `public` 或 `user`。

### 检索与回答

- 只用当前这句提问做 embedding。公共库和当前用户的私有库各取 5 条，按余弦分合并、去重后再留 5 条。
- 私有库有命中、但这 5 条里没有用户片段时，拿掉分数最低的一条，换上该用户分数最高的私有片段。只保底 1 条。
- 没有分数门槛，没有关键词检索，没有重排序，也没有查询改写。追问里的「那」不参与检索，只在生成时由对话模型根据历史理解。
- 历史存在 MySQL，不进向量库。生成时放进提示词：最近 20 轮，大约 12000 字，更早的从旧到新丢掉。本次提问单独放在问题位置。
- 提示词约束生成：事实只认这次给出的片段；上下文没写的就说没有找到，不用记忆补全；历史只用来理解指代；无关片段忽略，不同校区、不同事项不能拼成一件事；只能回答一部分时说明其余没找到；同一事实有两种说法时并列两边，标明来源和文件名。
- 回答通过 SSE 推送，顺序是 `citation`、`token`、`done`。失败时发送 `error`。引用在模型开口之前就由检索结果确定，并随助手消息写入 `citations_json`。
- 用户消息在检索前写入。检索失败时这条用户消息还在，没有助手回复。助手消息在整段生成完成后写入。

### 页面

- 登录、注册。未登录访问会回到登录页。
- 对话：会话列表、新建、删除、流式回答。引用收在折叠面板里，标明公共或用户，以及文件名和原文。会话标题取第一条提问的前 40 字。
- 文档：当前账号上传过的文件，显示状态（待处理、处理中、已就绪、失败）、片段数和错误说明。公共语料不在这个列表里。
- 设置：强调色；按账号修改对话接口的 `base_url`、`model`、`api_key`。密钥不会从接口返回。不填密钥表示保持原值，也可以清除。换成另一个地址时，如果密钥仍是环境变量里的那一份，会自动丢掉。`base_url` 只接受公网或本机回环，内网地址和云元数据地址会被拒绝。配置只存在进程内存里，重启后回到 `backend/.env`。向量模型在页面上只展示，不能在这里改。

### 数据

MySQL 四张表：`users`、`documents`、`chat_sessions`、`chat_messages`。启动时自动建表，并确保两个 Qdrant 集合存在。集合使用余弦距离，并为 `user_id`、`document_id` 建 payload 索引。

## 启动

本机需要 MySQL 8 和 Ollama。Qdrant 由 Docker Compose 启动，数据目录是 `qdrant_storage/`。

先按 `backend/.env` 里的 `DATABASE_URL` 准备好数据库和账号。示例是库名 `rag`：

```bash
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
cp .env.example backend/.env
```

一键启动会检查 MySQL 和 Ollama，再拉起 Qdrant、API 和前端：

```bash
./start.sh
```

也可以分开启动：

```bash
docker compose up -d
cd backend && uv sync && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
cd backend && uv run python ../scripts/seed.py
cd frontend && npm i && npm run dev
```

| 服务 | 端口 |
| --- | --- |
| 前端 Vite | 5173 |
| API | 8000 |
| Qdrant | 6333 |
| Ollama | 11434 |
| MySQL | 3306 |

Vite 把 `/api` 代理到 `8000`。

## 可以看到的效果

- 问「山东师范大学的校训是什么」。引用里应出现 `01_学校简介.txt`，原文有「弘德明志、博学笃行」。
- 再上传一份把校训写成别的 txt，问同一句。引用里应同时有公共和用户，答案应列出两边并说明冲突。
- 换一个账号登录，看不到前一个账号的会话和私有文档。
