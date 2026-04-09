# Novalist v2

A step-by-step AI novel composition platform powered by Amazon Bedrock (Claude Sonnet 4.6) and the Strands Agents SDK. Six specialized AI agents collaborate to write Chinese novels -- especially Chinese web fiction (网文) -- through a guided three-step workflow. Users provide story elements, review and edit AI-generated foundations at each step, then generate chapters one at a time with real-time streaming. A separate free chat mode enables conversational brainstorming with an AI creative advisor.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Multi-Agent Pipeline](#multi-agent-pipeline)
3. [Step-by-Step Composition Flow](#step-by-step-composition-flow)
4. [Free Chat Mode](#free-chat-mode)
5. [Project Structure](#project-structure)
6. [Infrastructure (AWS CDK)](#infrastructure-aws-cdk)
7. [API Reference](#api-reference)
8. [SSE Event Types](#sse-event-types)
9. [Data Model](#data-model)
10. [Deployment Guide](#deployment-guide)
11. [Configuration Reference](#configuration-reference)
12. [Local Development](#local-development)
13. [Cost Estimation](#cost-estimation)

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser (React 19 SPA)                                              │
│  Cognito Auth ─── SSE Streaming (XHR) ─── Step Wizard / Chat UI     │
└─────────────┬────────────────────────────────────────────────────────┘
              │ HTTPS
┌─────────────▼────────────────────────────────────────────────────────┐
│  CloudFront CDN                                                       │
│  ┌──────────────────┐    ┌──────────────────────────────────────────┐│
│  │ /* (default)      │    │ /api/* + /health                        ││
│  │ → S3 Bucket (OAI) │    │ → ALB Origin (HTTP, cache disabled)     ││
│  │   static assets   │    │   All methods, all viewer headers       ││
│  └──────────────────┘    └───────────────┬──────────────────────────┘│
└──────────────────────────────────────────┼───────────────────────────┘
                                           │ HTTP
┌──────────────────────────────────────────▼───────────────────────────┐
│  Application Load Balancer (idle timeout: 300s)                       │
│  Health check: GET /health every 30s                                  │
└──────────────────────────────────────────┬───────────────────────────┘
                                           │
┌──────────────────────────────────────────▼───────────────────────────┐
│  ECS Fargate Service (0.5 vCPU / 1 GB)                                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI + Uvicorn (port 8000)                                 │  │
│  │                                                                │  │
│  │  POST /api/step1 ──→ SSE stream                                │  │
│  │  POST /api/step2 ──→ SSE stream                                │  │
│  │  POST /api/step3/chapter ──→ SSE stream                        │  │
│  │  POST /api/chat ──→ SSE stream                                 │  │
│  │                                                                │  │
│  │  Strands Agents (in-thread) ──→ Amazon Bedrock                 │  │
│  │  ┌───────────────┐ ┌──────────────────┐ ┌──────────────────┐  │  │
│  │  │Story Architect│ │Character Developer│ │  World Builder   │  │  │
│  │  │  (temp 0.4)   │ │   (temp 0.4)     │ │  (temp 0.4)      │  │  │
│  │  └───────┬───────┘ └────────┬─────────┘ └────────┬─────────┘  │  │
│  │          └──────────────────┼──────────────────────┘           │  │
│  │                             ▼                                  │  │
│  │                      ┌──────────────┐                         │  │
│  │                      │ Plot Weaver  │                         │  │
│  │                      │  (temp 0.4)  │                         │  │
│  │                      └──────┬───────┘                         │  │
│  │                             ▼                                  │  │
│  │                      ┌──────────────┐                         │  │
│  │                      │ Prose Writer │                         │  │
│  │                      │ (temp 0.85)  │                         │  │
│  │                      └──────┬───────┘                         │  │
│  │                             ▼                                  │  │
│  │                      ┌──────────────┐                         │  │
│  │                      │   Editor     │                         │  │
│  │                      │  (temp 0.7)  │                         │  │
│  │                      └──────────────┘                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  Amazon Bedrock  ←──  Claude Sonnet 4.6                                │
│  DynamoDB        ←──  novalist-novels, novalist-chapters               │
└───────────────────────────────────────────────────────────────────────┘
```

**Request flow (step-by-step composition):**

1. User opens the CloudFront-served React app and authenticates via Cognito.
2. User fills out the Story Setup form (premise, genre, structure, style, characters, etc.).
3. The frontend POSTs to `/api/step1`. FastAPI returns a `StreamingResponse` with SSE events.
4. The backend spawns a thread running three Strands Agents in parallel via `GraphBuilder`. Token chunks are pushed to a thread-safe queue, consumed by an async generator, and sent as SSE events.
5. The frontend parses SSE events via XHR `onprogress`, routing `text_chunk` events to the correct tab (structure / characters / world) by agent name.
6. User reviews, edits, and confirms Step 1. The frontend saves edits via `PUT /api/novel/{id}/step1`, then POSTs to `/api/step2` for outline generation.
7. After confirming the outline, Step 3 generates chapters one at a time via `/api/step3/chapter` (prose_writer then editor, sequentially).

---

## Multi-Agent Pipeline

The system uses the **Strands Agents SDK** with `GraphBuilder` for parallel execution and direct `Agent()` invocation for sequential steps. All agents communicate through SSE streaming -- each agent runs in a dedicated thread with a callback handler that pushes text chunks to a thread-safe queue.

### Agent Roles

| # | Agent | Chinese Name | Purpose | Model Config | Max Tokens |
|---|-------|-------------|---------|-------------|------------|
| 1 | **story_architect** | 故事架构师 | Designs narrative structure: title, theme, act breakdown, chapter plan, turning points | Planning (temp 0.4) | 8,192 |
| 2 | **character_developer** | 角色开发师 | Creates character profiles: backstory, motivation, arc, voice, relationships | Planning (temp 0.4) | 8,192 |
| 3 | **world_builder** | 世界构建师 | Constructs settings: locations, rules, atmosphere, cultural details | Planning (temp 0.4) | 8,192 |
| 4 | **plot_weaver** | 情节编织师 | Threads plots: per-chapter outline, beats, subplots, foreshadowing | Planning (temp 0.4) | 8,192 |
| 5 | **prose_writer** | 文笔写手 | Generates chapter prose in the configured writing style | Creative (temp 0.85) | 32,768 |
| 6 | **editor** | 编辑 | Polishes prose: quality, pacing, voice, continuity, show-vs-tell | Standard (temp 0.7) | 16,384 |

A 7th virtual agent, **创意顾问** (creative advisor), is used only in free chat mode.

### Temperature Strategy

| Config | Temperature | Max Tokens | Used By |
|--------|-----------|------------|---------|
| `get_planning_model()` | 0.4 | 8,192 | story_architect, character_developer, world_builder, plot_weaver |
| `get_creative_model()` | 0.85 | 32,768 | prose_writer |
| `get_model()` | 0.7 | 16,384 | editor, chat advisor |

All models use `us.anthropic.claude-sonnet-4-6` via Bedrock with streaming enabled, 600s read timeout, and adaptive retry (3 attempts).

### MaxTokensContinuationHook

A custom Strands hook (`MaxTokensContinuationHook`) automatically continues generation when the model hits `max_tokens`. It retries once (configurable), effectively doubling the output limit before stopping.

### Execution Across Steps

```
Step 1 (parallel graph):   story_architect ─┐
                           character_developer ──→ results saved to DynamoDB
                           world_builder ────┘

          ↓ user reviews, edits, confirms ↓

Step 2 (single agent):    plot_weaver → chapter-by-chapter outline

          ↓ user reviews outline, confirms ↓

Step 3 (per chapter):     prose_writer → editor → save chapter
                           (repeat for each chapter)
```

---

## Step-by-Step Composition Flow

### Step 1: Foundation (Structure + Characters + World)

The user fills out the Story Setup form with:

| Field | Description | Default |
|-------|-------------|---------|
| Premise | Core story idea (required) | -- |
| Genre | 21 options (9 Western + 12 Chinese web novel) | xuanhuan (玄幻) |
| Structure | 9 options (5 Western + 4 Chinese) | three_act |
| Style | 14 options (7 Western + 7 Chinese) | commercial |
| POV | first_person, third_limited, third_omniscient | third_limited |
| Target chapters | 3--50 | 12 |
| Characters | Name, role, description, motivation (dynamic list) | empty |
| Setting notes | Free-text world guidance | empty |
| Theme notes | Free-text thematic direction | empty |
| Tone | Free-text tone descriptor | "引人入胜、沉浸感强" |

Three agents run in parallel via `GraphBuilder`. Their output streams into three tabs in the `ResultEditor` component (Story Structure / Characters / World). The user can:

- Edit any tab's content directly
- Use the **RefineChat** (AI refinement assistant) to request changes like "让主角更有个性"
- Confirm to proceed to Step 2

### Step 2: Plot Outline

The `plot_weaver` agent receives the (possibly user-edited) Step 1 results and generates a detailed per-chapter outline. The outline is displayed as:

- Collapsible chapter-by-chapter abstracts (parsed from `第X章：...` headings)
- Each chapter's abstract is individually editable
- Fallback to a raw textarea if parsing fails
- RefineChat available for outline adjustments

### Step 3: Chapter Writing

After confirming the outline, chapters are parsed into a list. For each chapter:

1. User clicks "Generate" on a chapter card
2. `prose_writer` writes the initial draft (streaming)
3. `editor` polishes the draft (streaming)
4. Final text is saved to DynamoDB
5. Chapter card shows the completed text

The user can modify a chapter's outline before generating it, and can re-generate any chapter.

### Genres

**Western (9):** Fantasy, Science Fiction, Mystery, Thriller, Romance, Horror, Literary, Historical, Young Adult

**Chinese Web Novel (12):** 玄幻 (xuanhuan), 仙侠 (xianxia), 武侠 (wuxia), 穿越 (chuanyue), 重生 (chongsheng), 都市 (dushi), 言情 (yanqing), 耽美 (danmei), 系统文 (xitong), 宫斗 (gongdou), 末世 (moshi), 军事 (junshi)

### Narrative Structures

**Western (5):** Three-Act, Hero's Journey, Save the Cat, Kishotenketsu, Freytag's Pyramid

**Chinese (4):** 升级流 (shengji -- level-up progression), 爽文节奏 (shuangwen -- rapid payoff pacing), 伏笔回收 (fucho -- foreshadowing payoff), 起伏流 (qifu -- emotional rollercoaster)

### Writing Styles

**Western (7):** Literary, Commercial, Minimalist, Ornate, Dialogue-Heavy, Action-Paced, Introspective

**Chinese (7):** 爽快打脸 (shuangkuai), 细腻情感 (xijie), 轻松搞笑 (qingsong), 热血燃文 (rexue), 虐心催泪 (nuexin), 古言雅韵 (guyan), 职场真实 (zhichang)

---

## Free Chat Mode

A conversational brainstorming mode where the user chats with an AI creative advisor (创意顾问). Features:

- Standalone chat interface (`FreeChatPage`)
- Maintains conversation history (last 20 messages for context)
- Creates a novel record with status `chat` in DynamoDB
- Can transition to step-by-step composition from chat
- Uses the standard model (temp 0.7)

---

## Project Structure

```
novalist/
├── README.md                              # This document
├── USER_GUIDE_CN.md                       # Chinese user guide
│
├── infra/                                 # AWS CDK infrastructure-as-code
│   ├── app.py                             # CDK app entry point — wires all 5 stacks
│   ├── cdk.json                           # CDK configuration
│   ├── requirements.txt                   # CDK Python dependencies
│   └── stacks/
│       ├── storage_stack.py               # DynamoDB tables (novels, chapters, connections)
│       ├── auth_stack.py                  # Cognito User Pool + admin user creation
│       ├── backend_stack.py               # ECR + CodeBuild + ECS Fargate + ALB + IAM
│       ├── api_stack.py                   # API Gateway WebSocket + Lambda (mostly unused in v2)
│       └── frontend_stack.py              # S3 + CloudFront with /api/* → ALB routing
│
├── backend/
│   ├── Dockerfile                         # Python 3.12 slim container
│   ├── requirements.txt                   # strands-agents, fastapi, uvicorn, boto3, etc.
│   ├── tests/                             # pytest test suite
│   └── app/
│       ├── main.py                        # FastAPI app — SSE streaming endpoints + REST CRUD
│       ├── config.py                      # Environment-based Settings (Pydantic)
│       ├── auth.py                        # Cognito JWT verification
│       ├── agents/
│       │   ├── models.py                  # 3 Bedrock model configs (planning/creative/standard)
│       │   ├── hooks.py                   # MaxTokensContinuationHook for auto-continue
│       │   ├── orchestrator.py            # Step pipeline: stream_step1/2/3, stream_chat
│       │   ├── story_architect.py         # 故事架构师 system prompt + factory
│       │   ├── character_dev.py           # 角色开发师 system prompt + factory
│       │   ├── world_builder.py           # 世界构建师 system prompt + factory
│       │   ├── plot_weaver.py             # 情节编织师 system prompt + factory
│       │   ├── prose_writer.py            # 文笔写手 system prompt + factory
│       │   └── editor.py                 # 编辑 system prompt + factory
│       ├── models/
│       │   ├── schemas.py                 # Pydantic models (requests, enums, data schemas)
│       │   └── novel_store.py             # DynamoDB CRUD (NovelStore class)
│       └── tools/
│           └── story_tools.py             # @tool-decorated DynamoDB persistence functions
│
└── frontend/
    ├── index.html                         # HTML entry point
    ├── package.json                       # React 19, Vite 6, amazon-cognito-identity-js
    ├── tsconfig.json                      # TypeScript config
    ├── vite.config.ts                     # Vite bundler config with /api proxy for dev
    └── src/
        ├── index.tsx                      # React entry point
        ├── App.tsx                        # Root: AuthProvider → ProtectedRoute → page router
        ├── types/
        │   └── index.ts                   # TypeScript types (Genre, Structure, Style, etc.)
        ├── auth/
        │   ├── CognitoProvider.tsx         # Auth context (login, logout, token refresh)
        │   ├── LoginPage.tsx              # Email + password login form
        │   └── ProtectedRoute.tsx         # Auth gate — shows LoginPage if unauthenticated
        ├── hooks/
        │   ├── useSSE.ts                  # XHR-based SSE client (POST + streaming parse)
        │   ├── useNovel.ts                # Novel CRUD hooks (load, save step1/step2)
        │   └── useWebSocket.ts            # WebSocket hook (legacy, unused in v2)
        ├── components/
        │   ├── Layout.tsx                 # App shell (header bar)
        │   ├── StorySetup.tsx             # Step 1 form (all genres/structures/styles/POV)
        │   ├── StepProgress.tsx           # 3-step progress indicator
        │   ├── ResultEditor.tsx           # Tabbed editor for step 1 output
        │   ├── ChapterList.tsx            # Chapter cards with outline editing + generate
        │   ├── ChapterView.tsx            # Chapter prose reader
        │   ├── RefineChat.tsx             # Inline AI refinement chat box
        │   ├── ChatPanel.tsx              # Chat message display
        │   ├── NovelList.tsx              # Novel list with status + resume
        │   ├── NovelWorkspace.tsx         # Legacy workspace (v1)
        │   └── AgentThoughts.tsx          # Agent activity feed (legacy v1)
        └── pages/
            ├── HomePage.tsx               # Mode selection + novel list
            ├── StepComposer.tsx           # 3-step wizard (main composition page)
            ├── FreeChatPage.tsx           # Chat brainstorming interface
            └── Dashboard.tsx              # Legacy dashboard (v1)
```

---

## Infrastructure (AWS CDK)

All infrastructure is defined as Python CDK stacks in `infra/stacks/`, deployed by `infra/app.py`.

### Stack Dependency Chain

```
StorageStack ──→ BackendStack (needs novels_table, chapters_table)
AuthStack    ──→ FrontendStack (needs user_pool, user_pool_client)
BackendStack ──→ FrontendStack (needs fargate_service.load_balancer)
StorageStack ──→ ApiStack (needs connections_table)
AuthStack    ──→ ApiStack (needs user_pool)
BackendStack ──→ ApiStack (needs backend_url)
```

### StorageStack (`NovalistStorage`)

Three DynamoDB tables, all pay-per-request billing, `RemovalPolicy.DESTROY`:

| Table | Partition Key | Sort Key | TTL | Purpose |
|-------|-------------|----------|-----|---------|
| `novalist-novels` | `user_id` (S) | `novel_id` (S) | -- | Novel metadata + all step outputs |
| `novalist-chapters` | `novel_id` (S) | `chapter_num` (N) | -- | Chapter content |
| `novalist-connections` | `connection_id` (S) | -- | `ttl` | WebSocket connections (unused in v2) |

### AuthStack (`NovalistAuth`)

- **Cognito User Pool** (`novalist-users`): Email sign-in, auto-verify, self-sign-up enabled.
- **Password policy**: 8+ characters, uppercase + lowercase + digits, symbols optional.
- **User Pool Client** (`novalist-web`): No client secret (SPA-compatible), SRP + user-password auth.
- **Token validity**: ID/access 1 hour, refresh 30 days.
- **Admin user**: Created via Custom Resource Lambda on deploy.

**Default admin credentials:**
- Email: `admin@novalist.ai`
- Password: `Admin123!Change`

### BackendStack (`NovalistBackend`)

- **VPC**: Default VPC (looked up, not created).
- **ECR Repository** (`novalist-backend`): Docker image storage.
- **CodeBuild Project** (`novalist-backend-build`): Builds Docker image in the cloud (no local Docker required). `STANDARD_7_0`, privileged mode, triggered by Custom Resource on every `cdk deploy`.
- **ECS Fargate Service**: 512 CPU / 1024 MiB, 1 desired task, public ALB.
- **ALB idle timeout**: 300 seconds (for long SSE streams).
- **Force deploy mechanism**: A second Custom Resource calls `ecs:UpdateService` with `forceNewDeployment=True` after every CodeBuild, ensuring the new image is pulled.
- **IAM**: DynamoDB read/write, Bedrock invoke (model + stream), execute-api ManageConnections.
- **Logging**: CloudWatch Logs, 1-week retention.

### ApiStack (`NovalistApi`)

WebSocket API Gateway with Lambda handlers. **Mostly unused in v2** -- the v2 architecture uses SSE over HTTP via CloudFront/ALB instead of WebSocket. Retained for potential future use.

### FrontendStack (`NovalistFrontend`)

- **S3 Bucket**: Private, `BLOCK_ALL` public access, OAI for CloudFront.
- **CloudFront Distribution**:
  - Default behavior: S3 origin (static assets), cache-optimized.
  - `/api/*`: ALB origin, cache disabled, all methods, all viewer headers forwarded.
  - `/health`: ALB origin, cache disabled.
- **SPA routing**: 403/404 errors redirect to `/index.html` with 200 status.
- **BucketDeployment**: Syncs `frontend/dist/` to S3, invalidates CloudFront `/*`.

---

## API Reference

All SSE streaming endpoints accept POST with JSON body and return `text/event-stream`. The `user_id` is passed as a query parameter.

### POST /api/step1

Generate story structure, characters, and world in parallel.

**Request body** (`Step1Request`):
```json
{
  "novel_id": "",
  "premise": "一个废柴少年意外获得上古传承...",
  "genre": "xuanhuan",
  "structure": "shengji",
  "style": "shuangkuai",
  "pov": "third_limited",
  "target_chapters": 12,
  "characters": [
    { "name": "林风", "role": "主角", "description": "废柴少年", "motivation": "证明自己" }
  ],
  "setting_notes": "九州大陆，修仙世界",
  "theme_notes": "逆天改命",
  "tone": "热血、爽快"
}
```

**Response**: SSE stream with events: `pipeline_start`, `agent_start`, `text_chunk` (per agent), `agent_complete`, `step_complete`, `done`.

### POST /api/step2

Generate plot outline from Step 1 results.

**Request body** (`Step2Request`):
```json
{
  "novel_id": "uuid-...",
  "structure": "...(user-edited structure text)...",
  "characters": "...(user-edited characters text)...",
  "world": "...(user-edited world text)..."
}
```

**Response**: SSE stream. The `plot_weaver` agent generates a chapter-by-chapter outline.

### POST /api/step3/chapter

Write and edit one chapter.

**Request body** (`Step3ChapterRequest`):
```json
{
  "novel_id": "uuid-...",
  "chapter_num": 1,
  "chapter_outline": "林风在宗门比武中被羞辱，意外跌入深渊...",
  "style": "shuangkuai",
  "pov": "third_limited"
}
```

**Response**: SSE stream. `prose_writer` generates the draft, then `editor` polishes it. Both stream `text_chunk` events.

### POST /api/chat

Brainstorming conversation with AI creative advisor.

**Request body** (`ChatRequest`):
```json
{
  "novel_id": "",
  "message": "我想写一个穿越到古代的故事，有什么好的切入点？",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

**Response**: SSE stream. Creates a novel record with status `chat` if `novel_id` is empty.

### PUT /api/novel/{novel_id}/step1

Save user edits to Step 1 results.

**Request body** (`SaveStep1Request`):
```json
{
  "structure": "...",
  "characters": "...",
  "world": "..."
}
```

**Response**: `{ "status": "ok", "novel_id": "..." }`

### PUT /api/novel/{novel_id}/step2

Save user edits to Step 2 results.

**Request body** (`SaveStep2Request`):
```json
{
  "plot": "..."
}
```

**Response**: `{ "status": "ok", "novel_id": "..." }`

### GET /api/novels

List all novels for a user.

**Query parameter**: `user_id`

**Response**:
```json
{
  "novels": [
    {
      "user_id": "...",
      "novel_id": "...",
      "status": "step2_done",
      "premise": "...",
      "created_at": 1712534400,
      "title": "..."
    }
  ]
}
```

### GET /api/novel/{novel_id}

Get full novel state including chapters.

**Query parameter**: `user_id`

**Response**: Full novel record from DynamoDB with `chapters` array appended.

### GET /health

Health check.

**Response**: `{ "status": "ok", "service": "novalist" }`

---

## SSE Event Types

All events follow the format:
```
event: <event_type>
data: <json_payload>
```

Heartbeat comments (`: heartbeat`) are sent every 15 seconds to keep connections alive.

| Event Type | Fields | Description |
|------------|--------|-------------|
| `pipeline_start` | `novel_id`, `content` | Pipeline has begun; contains the novel_id |
| `agent_start` | `agent`, `content` | Agent(s) beginning work; `agent` may be comma-separated for parallel agents |
| `text_chunk` | `agent`, `agent_name`, `content` | Incremental text from an agent; `agent_name` is the Chinese name |
| `agent_complete` | `agent`, `content`, `preview` | Agent finished; `preview` contains first 500 chars of output |
| `step_complete` | `step`, `novel_id`, `content`, `chapter_num` (step 3 only) | Step finished successfully |
| `error` | `content` | Error occurred during generation |
| `done` | `content` | Stream has ended |

### Text Chunk Batching

Text chunks are accumulated in a buffer and flushed every 100 characters or 0.5 seconds, whichever comes first. This reduces SSE event volume while maintaining responsive streaming.

---

## Data Model

### DynamoDB: novalist-novels

| Attribute | Type | Description |
|-----------|------|-------------|
| `user_id` | S (PK) | Cognito user identifier |
| `novel_id` | S (SK) | UUID |
| `status` | S | One of: `chat`, `step1_draft`, `step1_done`, `step2_draft`, `step2_done`, `writing`, `completed` |
| `premise` | S | Original story premise |
| `genre` | S | Genre enum value |
| `target_chapters` | N | Target chapter count |
| `structure` | S | Step 1 output: story structure text |
| `characters` | S | Step 1 output: character profiles text |
| `world` | S | Step 1 output: world building text |
| `plot` | S | Step 2 output: chapter-by-chapter outline |
| `last_chat` | S | Most recent chat response |
| `created_at` | N | Unix timestamp |
| `updated_at` | N | Unix timestamp |

### DynamoDB: novalist-chapters

| Attribute | Type | Description |
|-----------|------|-------------|
| `novel_id` | S (PK) | Parent novel UUID |
| `chapter_num` | N (SK) | Chapter number (1-based) |
| `title` | S | Chapter title |
| `content` | S | Full chapter text |
| `word_count` | N | Character count of content |
| `updated_at` | N | Unix timestamp |

### DynamoDB: novalist-connections (unused in v2)

| Attribute | Type | Description |
|-----------|------|-------------|
| `connection_id` | S (PK) | WebSocket connection ID |
| `ttl` | N | TTL for auto-expiry |

### Novel Status Flow

```
(new chat)     → chat
(new step)     → step1_draft → step1_done → step2_draft → step2_done → writing → completed
```

---

## Deployment Guide

### Prerequisites

- **AWS CLI** configured with admin-level credentials
- **AWS CDK CLI** v2.170+ (`npm install -g aws-cdk`)
- **Python 3.12+**
- **Node.js 18+** and npm
- **Amazon Bedrock model access**: Enable `anthropic.claude-sonnet-4-6` in the Bedrock console (us-east-1)

Docker is **not** required locally -- the backend image is built in the cloud via CodeBuild.

### Step-by-Step Deployment

```bash
# 1. Clone and enter the project
cd novalist

# 2. Install frontend dependencies
cd frontend
npm install
cd ..

# 3. Set up CDK virtual environment
cd infra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT_ID/us-east-1

# 5. Deploy backend stacks first (frontend needs ALB reference)
cdk deploy NovalistStorage NovalistAuth NovalistBackend NovalistApi --require-approval never

# 6. Note CDK outputs:
#    NovalistAuth.UserPoolId = us-east-1_XXXXXXX
#    NovalistAuth.UserPoolClientId = XXXXXXXXXXXXXXXXXXXXXXXXXX

# 7. Configure frontend environment
cd ../frontend
cat > .env << 'EOF'
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXX
VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
EOF

# 8. Build frontend
npm run build

# 9. Deploy frontend stack (uploads dist/ to S3, creates CloudFront)
cd ../infra
cdk deploy NovalistFrontend --require-approval never

# 10. Access the app at the CloudFront URL from outputs:
#     NovalistFrontend.DistributionUrl = https://dXXXXXXXXXXXX.cloudfront.net

# 11. Log in with admin credentials:
#     Email: admin@novalist.ai
#     Password: Admin123!Change
```

### Updating After Code Changes

```bash
# Backend changes:
cd infra && cdk deploy NovalistBackend --require-approval never

# Frontend changes:
cd frontend && npm run build && cd ../infra && cdk deploy NovalistFrontend --require-approval never

# All stacks:
cd infra && cdk deploy --all --require-approval never
```

### Tearing Down

```bash
cd infra
cdk destroy --all
```

All resources have `RemovalPolicy.DESTROY` and S3 has `auto_delete_objects=True`.

---

## Configuration Reference

### Backend Environment Variables

| Variable | Default | Set By | Description |
|----------|---------|--------|-------------|
| `AWS_REGION` | `us-east-1` | CDK | AWS region for all services |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | CDK / manual | Bedrock model identifier |
| `NOVELS_TABLE` | `novalist-novels` | CDK | DynamoDB novels table name |
| `CHAPTERS_TABLE` | `novalist-chapters` | CDK | DynamoDB chapters table name |
| `COGNITO_USER_POOL_ID` | _(empty)_ | CDK / manual | Cognito pool (empty = auth disabled) |
| `COGNITO_REGION` | `us-east-1` | CDK / manual | Cognito region |
| `WEBSOCKET_API_ENDPOINT` | _(empty)_ | CDK | WebSocket endpoint (unused in v2) |
| `LOG_LEVEL` | `INFO` | CDK | Python logging level |

### Frontend Environment Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `VITE_COGNITO_USER_POOL_ID` | CDK output `NovalistAuth.UserPoolId` | Cognito User Pool ID |
| `VITE_COGNITO_CLIENT_ID` | CDK output `NovalistAuth.UserPoolClientId` | Cognito app client ID |

---

## Local Development

### Running the Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Requires valid AWS credentials with Bedrock + DynamoDB access
export AWS_REGION=us-east-1
export NOVELS_TABLE=novalist-novels
export CHAPTERS_TABLE=novalist-chapters

uvicorn app.main:app --reload --port 8000
```

### Running the Frontend

```bash
cd frontend
npm install

# Create .env for local dev:
cat > .env << 'EOF'
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXX
VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
EOF

npm run dev
# Vite dev server at http://localhost:5173
# Configure vite.config.ts proxy to forward /api/* to localhost:8000
```

### Running Tests

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio moto httpx
python -m pytest tests/ -v
```

### Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"novalist"}
```

---

## Cost Estimation

Monthly estimate for light usage (1 user, a few novels per week):

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| **CloudFront + S3** | $1--3 | Minimal traffic |
| **Cognito** | $0 | Free tier (50K MAU) |
| **ECS Fargate** | $15--40 | 0.5 vCPU / 1 GB, running continuously |
| **DynamoDB** | $0--5 | Pay-per-request |
| **Bedrock (Claude Sonnet 4.6)** | $20--100+ | Depends on novel count and chapter length |
| **ECR** | $0--1 | Image storage |
| **CloudWatch Logs** | $1--3 | Log ingestion |
| **CodeBuild** | $0--1 | 100 free build-minutes/month |
| **Total** | **~$40--150/month** | Dominated by Fargate + Bedrock |

**Cost optimization:**

- Scale Fargate `desired_count` to 0 when idle; use ECS auto-scaling.
- Use Fargate Spot for non-production (up to 70% savings).
- Use VPC endpoints for DynamoDB and Bedrock to eliminate NAT Gateway costs.
- Use Claude Haiku for planning agents (story_architect, character_developer, world_builder) to reduce Bedrock costs.
- Reduce `max_tokens` for planning agents if outputs are consistently shorter.
