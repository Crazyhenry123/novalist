# Novalist

A multi-agent AI system for writing novels, powered by Amazon Bedrock (Claude Sonnet 4.6) and orchestrated with the Strands Agents SDK. Users provide story elements — premise, genre, characters, style preferences — and a pipeline of six specialized AI agents collaborates to produce structured, publication-ready fiction. The web interface streams agent thinking and prose generation in real time over WebSocket.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Multi-Agent Pipeline](#multi-agent-pipeline)
3. [Narrative Models & Story Composition](#narrative-models--story-composition)
4. [Project Structure](#project-structure)
5. [Infrastructure (AWS CDK)](#infrastructure-aws-cdk)
6. [Backend](#backend)
7. [Frontend](#frontend)
8. [Streaming Protocol](#streaming-protocol)
9. [Data Model](#data-model)
10. [Deployment Guide](#deployment-guide)
11. [Configuration Reference](#configuration-reference)
12. [Local Development](#local-development)
13. [Security Considerations](#security-considerations)
14. [Cost Estimation](#cost-estimation)
15. [Extending the System](#extending-the-system)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React SPA)                                            │
│  Cognito JWT Auth ─── WebSocket Client ─── Streaming UI         │
└────────────┬────────────────────────────────────────────────────┘
             │ wss://
┌────────────▼────────────────────────────────────────────────────┐
│  API Gateway WebSocket (novalist-ws)                            │
│  $connect ──→ Lambda (ConnectFn)   ──→ DynamoDB connections     │
│  $default ──→ Lambda (MessageFn)   ──→ HTTP POST to Fargate     │
│  $disconnect → Lambda (DisconnectFn) → DynamoDB cleanup         │
└────────────┬────────────────────────────────────────────────────┘
             │ HTTP (internal ALB)
┌────────────▼────────────────────────────────────────────────────┐
│  ECS Fargate Service (FastAPI + Uvicorn)                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Strands Agents Graph Pipeline                             │ │
│  │                                                            │ │
│  │  ┌────────────────┐ ┌──────────────────┐ ┌──────────────┐│ │
│  │  │ Story Architect│ │Character Developer│ │ World Builder ││ │
│  │  │  (temp 0.4)    │ │   (temp 0.4)     │ │  (temp 0.4)  ││ │
│  │  └───────┬────────┘ └────────┬─────────┘ └──────┬───────┘│ │
│  │          └───────────────────┼───────────────────┘        │ │
│  │                              ▼                             │ │
│  │                     ┌──────────────┐                      │ │
│  │                     │ Plot Weaver  │                      │ │
│  │                     │  (temp 0.4)  │                      │ │
│  │                     └──────┬───────┘                      │ │
│  │                            ▼                               │ │
│  │                     ┌──────────────┐                      │ │
│  │                     │ Prose Writer │                      │ │
│  │                     │  (temp 0.85) │                      │ │
│  │                     └──────┬───────┘                      │ │
│  │                            ▼                               │ │
│  │                     ┌──────────────┐                      │ │
│  │                     │   Editor     │                      │ │
│  │                     │  (temp 0.7)  │                      │ │
│  │                     └──────────────┘                      │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Amazon Bedrock  ←──  Claude Sonnet 4.6                         │
│  DynamoDB        ←──  novels, chapters, connections             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  S3 Bucket (static assets)  ──→  CloudFront CDN (HTTPS)         │
│  Origin Access Identity (OAI) — bucket is not publicly exposed  │
└─────────────────────────────────────────────────────────────────┘
```

**Request flow:**

1. User opens the CloudFront-served React app and authenticates via Cognito.
2. The app opens a WebSocket connection to API Gateway, passing the Cognito JWT as a query parameter.
3. The `$connect` Lambda records the connection in DynamoDB.
4. User submits a novel request; the app sends a JSON message over the WebSocket.
5. The `$default` Lambda forwards the message via HTTP to the Fargate backend, including the `connection_id` and `callback_url`.
6. The FastAPI backend invokes the Strands Agents graph pipeline. As each agent completes, streaming messages are posted back to the client through the API Gateway Management API (`post_to_connection`).
7. The React app renders agent activity, prose chunks, and chapter completions in real time.

---

## Multi-Agent Pipeline

The system uses the **Strands Agents SDK Graph pattern** — a directed acyclic graph where nodes are specialized AI agents and edges represent data dependencies. The graph builder ensures agents only execute once their upstream dependencies have completed.

### Agent Roles

| # | Agent | Purpose | Model Temp | Max Tokens | Tools |
|---|-------|---------|-----------|------------|-------|
| 1 | **Story Architect** | Designs narrative structure: acts, chapter plan, turning points, theme statement | 0.4 | 8,192 | `save_story_element` |
| 2 | **Character Developer** | Creates character profiles: backstory, motivation, arc, voice, relationships | 0.4 | 8,192 | `save_story_element` |
| 3 | **World Builder** | Constructs settings: locations, rules, atmosphere, cultural details | 0.4 | 8,192 | `save_story_element` |
| 4 | **Plot Weaver** | Threads plots: beat sheet, scene outlines, subplots, foreshadowing, tension curve | 0.4 | 8,192 | `save_story_element` |
| 5 | **Prose Writer** | Generates chapter prose in the configured writing style | 0.85 | 16,384 | `save_chapter` |
| 6 | **Editor** | Polishes prose: quality, pacing, voice, continuity, show-vs-tell | 0.7 | 8,192 | `save_chapter` |

### Execution Phases

```
Phase 1 (parallel):  Story Architect + Character Developer + World Builder
Phase 2 (sequential): Plot Weaver (receives output from all Phase 1 agents)
Phase 3 (sequential): Prose Writer (receives the plot outline)
Phase 4 (sequential): Editor (receives draft chapters)
```

Phase 1 agents run concurrently because they have no mutual dependencies — the graph builder handles the parallelism. Each subsequent phase waits for its upstream to complete before executing.

### Temperature Strategy

Three distinct model configurations control the creativity-precision trade-off:

- **Planning model (temp 0.4)**: Used by Story Architect, Character Developer, World Builder, and Plot Weaver. Lower temperature produces more structured, consistent, and logically coherent planning output. These agents need to produce reliable JSON-structured data that downstream agents can consume.
- **Creative model (temp 0.85)**: Used by the Prose Writer. Higher temperature produces more varied, surprising, and literarily rich prose. Creative writing benefits from controlled unpredictability in word choice and phrasing.
- **Standard model (temp 0.7)**: Used by the Editor. Balanced temperature allows the editor to make improvements while preserving the writer's voice — not too rigid to miss enhancements, not too wild to rewrite unnecessarily.

### Shared State

All agents share an `invocation_state` dictionary containing:

```python
{
    "user_id": "cognito-sub-id",
    "novel_id": "uuid",
    "novel_request": { ... }  # Full NovelRequest as dict
}
```

This allows tools to persist data to the correct DynamoDB records without the agent needing explicit instructions about storage keys.

---

## Narrative Models & Story Composition

The system supports five established narrative structures, selectable by the user:

### Three-Act Structure (Default)
The most widely used framework in commercial fiction and screenwriting.
- **Act 1 — Setup (25%)**: Introduce protagonist, world, and status quo. Establish stakes. End with the inciting incident.
- **Act 2 — Confrontation (50%)**: Rising complications. Midpoint reversal. Protagonist pursues goal while obstacles escalate. Ends at the "dark moment."
- **Act 3 — Resolution (25%)**: Climax, final confrontation, and denouement.

### Hero's Journey (Joseph Campbell / Christopher Vogler)
A 12-stage mythic structure ideal for adventure, fantasy, and transformation narratives.
- Ordinary World → Call to Adventure → Refusal → Meeting the Mentor → Crossing the Threshold → Tests, Allies, Enemies → Approach to Inmost Cave → The Ordeal → Reward → The Road Back → Resurrection → Return with the Elixir

### Save the Cat Beat Sheet (Blake Snyder)
A 15-beat commercial story framework that provides the tightest structural guidance.
- Opening Image → Theme Stated → Set-Up → Catalyst → Debate → Break into Two → B Story → Fun and Games → Midpoint → Bad Guys Close In → All Is Lost → Dark Night of the Soul → Break into Three → Finale → Final Image

### Kishotenketsu (East Asian Four-Part Structure)
A conflict-optional structure common in Japanese, Chinese, and Korean narratives.
- **Ki (Introduction)**: Establish the situation
- **Sho (Development)**: Develop it naturally
- **Ten (Twist)**: An unexpected turn or new perspective
- **Ketsu (Reconciliation)**: Harmonize all elements into resolution

### Freytag's Pyramid (Five-Act Classical)
The classical dramatic structure suited for literary fiction and tragedy.
- Exposition → Rising Action → Climax → Falling Action → Denouement

### Story Elements Collected

The Story Setup form collects:

| Element | Description | Agent Consumer |
|---------|-------------|---------------|
| **Premise** | Core story idea or logline | All agents |
| **Genre** | Fantasy, sci-fi, mystery, thriller, romance, horror, literary, historical, YA | All agents |
| **Structure** | Which narrative model to follow | Story Architect |
| **Writing Style** | Literary, commercial, minimalist, ornate, dialogue-heavy, action-paced, introspective | Prose Writer |
| **POV** | First person, third limited, third omniscient | Prose Writer, Editor |
| **Target Chapters** | 3–50 chapters | Story Architect, Plot Weaver |
| **Characters** | Name, role, description, motivation per character | Character Developer |
| **Setting Notes** | Free-text world and setting guidance | World Builder |
| **Theme Notes** | Free-text thematic direction | Story Architect, Plot Weaver |
| **Tone** | Free-text tone descriptor (e.g., "dark and atmospheric") | All agents |

### Writing Styles

The Prose Writer agent adapts its output based on the selected style:

| Style | Characteristics | Best For |
|-------|----------------|----------|
| **Literary** | Rich metaphor, thematic depth, complex sentences, psychological nuance | Character-driven, award-caliber fiction |
| **Commercial** | Clean prose, strong hooks, fast pacing, accessible language | Bestseller-oriented genre fiction |
| **Minimalist** | Short sentences, sparse description, subtext-heavy | Hemingway-esque literary fiction, noir |
| **Ornate** | Lush description, complex sentence structures, poetic language | Fantasy, historical, gothic |
| **Dialogue-Heavy** | Story told primarily through conversation, minimal narration | Contemporary, comedy, drama |
| **Action-Paced** | Quick cuts, short paragraphs, visceral language, constant momentum | Thrillers, action-adventure |
| **Introspective** | Deep interior monologue, stream of consciousness, psychological focus | Literary fiction, psychological thrillers |

---

## Project Structure

```
novalist/
├── infra/                              # AWS CDK infrastructure-as-code
│   ├── app.py                          # CDK app entry point — wires all stacks
│   ├── cdk.json                        # CDK configuration
│   ├── requirements.txt                # CDK Python dependencies
│   └── stacks/
│       ├── storage_stack.py            # DynamoDB tables
│       ├── auth_stack.py               # Cognito + admin user creation
│       ├── backend_stack.py            # ECS Fargate + ALB + IAM
│       ├── api_stack.py                # API Gateway WebSocket + Lambda handlers
│       └── frontend_stack.py           # S3 + CloudFront + BucketDeployment
│
├── backend/
│   ├── Dockerfile                      # Python 3.12 slim container
│   ├── requirements.txt                # Python dependencies
│   └── app/
│       ├── main.py                     # FastAPI application
│       ├── config.py                   # Environment-based configuration
│       ├── auth.py                     # Cognito JWT verification
│       ├── agents/
│       │   ├── models.py               # Bedrock model configurations (3 temp levels)
│       │   ├── orchestrator.py         # Graph pipeline builder and runner
│       │   ├── story_architect.py      # Narrative structure agent
│       │   ├── character_dev.py        # Character development agent
│       │   ├── world_builder.py        # Setting/world creation agent
│       │   ├── plot_weaver.py          # Plot threading agent
│       │   ├── prose_writer.py         # Prose generation agent
│       │   └── editor.py              # Editing/polish agent
│       ├── tools/
│       │   └── story_tools.py          # DynamoDB persistence tools for agents
│       └── models/
│           └── schemas.py              # Pydantic data models
│
├── frontend/
│   ├── index.html                      # HTML entry point
│   ├── package.json                    # Node dependencies
│   ├── tsconfig.json                   # TypeScript config
│   ├── vite.config.ts                  # Vite bundler config
│   ├── .env.example                    # Environment variable template
│   └── src/
│       ├── index.tsx                   # React entry point
│       ├── App.tsx                     # Root component with auth wrapper
│       ├── vite-env.d.ts              # Vite env type declarations
│       ├── types/
│       │   └── index.ts                # Shared TypeScript types
│       ├── auth/
│       │   ├── CognitoProvider.tsx      # Auth context with Cognito SDK
│       │   ├── LoginPage.tsx           # Login form UI
│       │   └── ProtectedRoute.tsx      # Auth-gated route wrapper
│       ├── hooks/
│       │   └── useWebSocket.ts         # WebSocket hook with auto-reconnect
│       ├── components/
│       │   ├── Layout.tsx              # App shell (header + nav)
│       │   ├── NovelWorkspace.tsx      # Main workspace orchestrator
│       │   ├── StorySetup.tsx          # Story configuration form
│       │   ├── AgentThoughts.tsx       # Live agent activity feed
│       │   └── ChapterView.tsx         # Generated prose reader
│       └── pages/
│           └── Dashboard.tsx           # Main page
│
└── README.md                           # This document
```

---

## Infrastructure (AWS CDK)

All infrastructure is defined as Python CDK stacks in `infra/stacks/`. The stacks are deployed in dependency order by `infra/app.py`.

### Stack Dependency Chain

```
StorageStack  ──→  BackendStack (needs novels_table, chapters_table)
                ──→  ApiStack    (needs connections_table)
AuthStack     ──→  ApiStack    (needs user_pool)
                ──→  FrontendStack (needs user_pool, user_pool_client)
BackendStack  ──→  ApiStack    (needs backend_url)
ApiStack      ──→  FrontendStack (needs websocket_url)
```

### StorageStack (`NovalistStorage`)

Three DynamoDB tables, all pay-per-request billing:

| Table | Partition Key | Sort Key | TTL | Purpose |
|-------|-------------|----------|-----|---------|
| `novalist-novels` | `user_id` (S) | `novel_id` (S) | — | Novel metadata + story elements |
| `novalist-chapters` | `novel_id` (S) | `chapter_num` (N) | — | Chapter content |
| `novalist-connections` | `connection_id` (S) | — | `ttl` | Active WebSocket connections |

### AuthStack (`NovalistAuth`)

- **Cognito User Pool** (`novalist-users`): Email-based sign-in, auto-verify email, self-sign-up enabled.
- **Password policy**: 8+ characters, uppercase + lowercase + digits required, symbols optional.
- **User Pool Client** (`novalist-web`): SPA-compatible (no client secret), SRP + user-password auth flows.
- **Token validity**: ID/access tokens 1 hour, refresh tokens 30 days.
- **Admin user**: Created via CloudFormation Custom Resource backed by a Lambda function. On stack creation, the Lambda calls `AdminCreateUser` and `AdminSetUserPassword` to create a permanent admin account.

**Default admin credentials:**
- Email: `admin@novalist.ai`
- Password: `Admin123!Change`

### BackendStack (`NovalistBackend`)

- **VPC**: 2 AZs, 1 NAT Gateway (cost-conscious single-NAT setup).
- **ECR Repository** (`novalist-backend`): Stores the backend Docker image.
- **CodeBuild Project** (`novalist-backend-build`): Builds the Docker image from `backend/Dockerfile` in the cloud — no local Docker required. Uses `STANDARD_7_0` Linux image with privileged mode for Docker-in-Docker. Triggered on every `cdk deploy` via a Custom Resource Lambda that polls for build completion.
- **ECS Cluster + Fargate Service**: 512 CPU units, 1024 MiB memory, 1 desired task, `minHealthyPercent=100`.
- **Application Load Balancer**: Public-facing, health check on `/health` every 30 seconds.
- **IAM permissions**:
  - Read/write on `novalist-novels` and `novalist-chapters` DynamoDB tables.
  - `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on all Bedrock resources.
- **Environment variables**: `NOVELS_TABLE`, `CHAPTERS_TABLE`, `AWS_REGION`, `LOG_LEVEL`.
- **Logging**: CloudWatch Logs with 1-week retention.
- **Build pipeline**: Source uploaded to S3 → CodeBuild builds and pushes to ECR → Fargate deploys the image (dependency enforced via `add_dependency`).

### ApiStack (`NovalistApi`)

- **WebSocket API** (`novalist-ws`): Protocol type `WEBSOCKET`, route selection `$request.body.action`.
- **Three Lambda functions** (Python 3.12):
  - `ConnectFn` (10s timeout): Records `connection_id` + token in DynamoDB with 24-hour TTL.
  - `DisconnectFn` (10s timeout): Deletes the connection record.
  - `MessageFn` (300s timeout, 512 MiB memory): Forwards messages to the Fargate backend via HTTP, relays responses back to the client via `post_to_connection`.
- **Stage**: `prod`, auto-deploy enabled.
- **IAM**: Lambda invoke permissions for API Gateway; `execute-api:ManageConnections` for MessageFn to post back to WebSocket clients.

### FrontendStack (`NovalistFrontend`)

- **S3 Bucket**: Private (all public access blocked), `RemovalPolicy.DESTROY` for dev convenience.
- **CloudFront Distribution**: Origin Access Identity for secure S3 access, HTTPS-only, cache-optimized policy.
- **SPA routing**: 403 and 404 errors redirect to `/index.html` with 200 status (required for client-side routing).
- **BucketDeployment**: Syncs `frontend/dist/` to S3 and invalidates CloudFront cache on deploy.
- **CfnOutputs**: `DistributionUrl`, `CognitoUserPoolId`, `CognitoClientId`, `WebSocketUrl`.

---

## Backend

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI 0.115+ |
| Server | Uvicorn (ASGI) |
| Agent SDK | Strands Agents 1.0+ |
| AI Model | Amazon Bedrock — Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) |
| Storage | Amazon DynamoDB (via boto3) |
| Auth | Cognito JWT verification (python-jose) |
| Container | Python 3.12 slim |

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check (used by ALB target group) |
| `POST` | `/agent/invoke` | Main entry point — called by WebSocket Lambda |
| `GET` | `/novels/{user_id}` | List all novels for a user |
| `GET` | `/novels/{novel_id}/chapters` | List all chapters for a novel |

### Agent Invoke Actions

The `/agent/invoke` endpoint dispatches on the `action` field:

| Action | Description | Payload |
|--------|-------------|---------|
| `start_novel` | Runs the full multi-agent novel generation pipeline | `NovelRequest` fields |
| `generate_chapter` | Reserved for single-chapter regeneration (future) | `novel_id`, `chapter_num` |
| `ping` | Connection health check | — |

### Agent Tools

Tools are defined using the Strands `@tool` decorator with `context=True` to access shared state:

**`save_story_element(novel_id, element_type, element_data)`**
- Persists a story element (structure, characters, world, plot) to the novels DynamoDB table.
- Uses `UpdateExpression` to set individual attributes on the novel record.

**`save_chapter(novel_id, chapter_num, title, content, summary)`**
- Persists a complete chapter to the chapters DynamoDB table.
- Automatically calculates `word_count` from the content.

**`load_story_element(novel_id, element_type)`**
- Retrieves a previously saved story element from DynamoDB.
- Returns the raw JSON string for the requested element type.

### Configuration

All configuration is environment-variable driven (see `backend/app/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | AWS region for all services |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-6` | Bedrock model identifier |
| `NOVELS_TABLE` | `novalist-novels` | DynamoDB table for novel metadata |
| `CHAPTERS_TABLE` | `novalist-chapters` | DynamoDB table for chapter content |
| `COGNITO_USER_POOL_ID` | _(empty)_ | Cognito User Pool ID (empty = auth disabled) |
| `COGNITO_REGION` | `us-east-1` | Cognito region |
| `WEBSOCKET_API_ENDPOINT` | _(empty)_ | WebSocket API endpoint |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Frontend

### Technology Stack

| Component | Technology |
|-----------|-----------|
| Framework | React 19 |
| Language | TypeScript (strict mode) |
| Bundler | Vite 6 |
| Auth | amazon-cognito-identity-js |
| Routing | react-router-dom 7 |
| Styling | CSS-in-JS (inline styles, no external library) |

### Components

**`AuthProvider` / `useAuth` (src/auth/CognitoProvider.tsx)**
- React Context wrapping the Cognito SDK.
- Handles `authenticateUser`, session persistence, `newPasswordRequired` challenge (for first admin login), and sign-out.
- Exposes: `isAuthenticated`, `idToken`, `email`, `login()`, `logout()`, `loading`.

**`LoginPage` (src/auth/LoginPage.tsx)**
- Email + password form with error display.
- Dark theme, centered card layout.

**`ProtectedRoute` (src/auth/ProtectedRoute.tsx)**
- Wraps children; renders `LoginPage` if not authenticated.
- Shows loading state while checking existing session.

**`useWebSocket` (src/hooks/useWebSocket.ts)**
- Manages WebSocket connection lifecycle.
- Auto-reconnects up to 5 times with 3-second delay.
- Passes Cognito JWT as `?token=` query parameter on connect.
- Returns: `connected`, `messages[]`, `sendMessage(action, payload)`, `clearMessages()`.

**`StorySetup` (src/components/StorySetup.tsx)**
- Comprehensive form for novel configuration.
- Dynamic character list (add/remove rows).
- Dropdowns for genre (9 options), structure (5 options), style (7 options), POV (3 options).
- Number input for target chapters (3–50).
- Free-text fields for premise, setting notes, theme notes, tone.

**`AgentThoughts` (src/components/AgentThoughts.tsx)**
- Live-scrolling feed of agent activity messages.
- Color-coded by agent (amber, green, blue, purple, pink, cyan).
- Emoji icons per agent role.
- Expandable preview pane for agent output data.

**`ChapterView` (src/components/ChapterView.tsx)**
- Renders completed chapters in a readable serif-font layout.
- Accumulates `prose_chunk` messages into continuous chapter text.

**`NovelWorkspace` (src/components/NovelWorkspace.tsx)**
- Orchestrates the workspace: connection status indicator, form submission, progress spinner, agent feed, and chapter display.
- Manages the `generating` state — disables the form during generation and re-enables on completion or error.

### Environment Variables

Create `frontend/.env` from `.env.example`:

```bash
VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_WEBSOCKET_URL=wss://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod
```

These values come from CDK stack outputs after deployment.

---

## Streaming Protocol

All real-time communication uses a JSON-based WebSocket protocol.

### Client → Server Messages

```json
{
  "action": "start_novel",
  "payload": {
    "premise": "A young astronomer discovers...",
    "genre": "science_fiction",
    "structure": "heros_journey",
    "style": "literary",
    "pov": "third_limited",
    "target_chapters": 12,
    "characters": [
      { "name": "Lyra", "role": "protagonist", "description": "...", "motivation": "..." }
    ],
    "setting_notes": "A research station on Europa",
    "theme_notes": "The cost of obsession",
    "tone": "dark and atmospheric"
  }
}
```

### Server → Client Messages

| `type` | Fields | Description |
|--------|--------|-------------|
| `pipeline_start` | `novel_id`, `content` | Pipeline has begun |
| `agent_start` | `agent`, `content` | Agent(s) beginning work |
| `agent_result` | `agent`, `content`, `data.preview` | Agent completed — includes preview of output |
| `thought` | `agent`, `content` | Intermediate agent thinking (for future streaming enhancement) |
| `prose_chunk` | `chapter`, `content` | Incremental prose text |
| `chapter_complete` | `chapter`, `content`, `word_count` | Full chapter finished |
| `novel_complete` | `novel_id`, `content`, `data` | All agents done; `data` includes `status` and `agents_completed` |
| `error` | `content` or `message` | Error occurred |
| `pong` | `content` | Response to `ping` |
| `info` | `content` | Informational message |

### Message Flow Diagram

```
Client                    API GW Lambda              Fargate Backend
  │                            │                           │
  │── start_novel ──→          │                           │
  │                            │── POST /agent/invoke ──→  │
  │                            │                           │── pipeline_start ──→ (via post_to_connection)
  │  ◄── pipeline_start ──────────────────────────────────│
  │                            │                           │── run graph phase 1
  │  ◄── agent_start (3 agents) ──────────────────────────│
  │                            │                           │   ... architect completes
  │  ◄── agent_result (architect) ────────────────────────│
  │                            │                           │   ... character_dev completes
  │  ◄── agent_result (character_dev) ────────────────────│
  │                            │                           │   ... world_builder completes
  │  ◄── agent_result (world_builder) ────────────────────│
  │                            │                           │── run graph phase 2
  │  ◄── agent_result (plot_weaver) ──────────────────────│
  │                            │                           │── run graph phase 3
  │  ◄── agent_result (prose_writer) ─────────────────────│
  │                            │                           │── run graph phase 4
  │  ◄── agent_result (editor) ───────────────────────────│
  │                            │                           │
  │  ◄── novel_complete ──────────────────────────────────│
  │                            │◄── HTTP 200 ─────────────│
```

---

## Data Model

### NovelRequest (Input)

```python
class NovelRequest(BaseModel):
    premise: str                          # Required — core story idea
    genre: Genre = "fantasy"              # 9 genre options
    structure: NarrativeStructure = "three_act"  # 5 structure options
    style: WritingStyle = "commercial"    # 7 style options
    pov: POV = "third_limited"            # 3 POV options
    target_chapters: int = 12             # Range: 3–50
    characters: list[CharacterBrief] = [] # Optional character briefs
    setting_notes: str = ""               # Free-text world notes
    theme_notes: str = ""                 # Free-text theme guidance
    tone: str = "engaging and immersive"  # Free-text tone descriptor
```

### Agent Output Schemas

**StoryStructure** (Story Architect → DynamoDB `structure` attribute):
```json
{
  "title": "The Cartographer of Stars",
  "theme_statement": "Obsession with the past blinds us to the future",
  "act_breakdown": ["Act 1: ...", "Act 2A: ...", "Act 2B: ...", "Act 3: ..."],
  "chapter_plan": ["Ch1: Lyra observes...", "Ch2: The anomaly..."],
  "turning_points": ["Midpoint: Lyra discovers...", "Climax: ..."]
}
```

**CharacterProfile** (Character Developer → DynamoDB `characters` attribute):
```json
[
  {
    "name": "Lyra",
    "role": "protagonist",
    "backstory": "Born on a research vessel...",
    "motivation": "External: map the signal. Internal: prove her mother's theory.",
    "arc": "From isolated perfectionist to collaborative leader",
    "voice_notes": "Precise, technical vocabulary. Short declarative sentences...",
    "relationships": { "Kael": "Reluctant ally...", "Director Voss": "Antagonist..." }
  }
]
```

**WorldDetail** (World Builder → DynamoDB `world` attribute):
```json
{
  "setting_description": "Europa Research Station Kepler-7...",
  "time_period": "2340 CE, 12 years after the Signal",
  "locations": ["Observatory dome", "The Underbelly corridors", "Ice caves"],
  "rules_and_systems": "Gravity is 0.13g. Radiation suits required on surface...",
  "atmosphere": "Claustrophobic, humming with machinery...",
  "cultural_notes": "Crew follows a merit-based hierarchy..."
}
```

**PlotOutline** (Plot Weaver → DynamoDB `plot` attribute):
```json
{
  "beats": ["Beat 1: Discovery of the signal pattern", "Beat 2: ..."],
  "scene_outline": ["Ch1 Scene 1: Lyra alone in the observatory (POV: Lyra)...", "..."],
  "subplots": ["B plot: Lyra and Kael's reluctant partnership...", "C plot: ..."],
  "foreshadowing": ["Ch2: Lyra notices a shadow in the ice (pays off Ch9)", "..."]
}
```

### DynamoDB Record Structures

**Novels table** (`novalist-novels`):
```json
{
  "user_id": "cognito-sub-abc123",
  "novel_id": "uuid-...",
  "structure": "{ ... }",
  "characters": "[ ... ]",
  "world": "{ ... }",
  "plot": "{ ... }"
}
```

**Chapters table** (`novalist-chapters`):
```json
{
  "novel_id": "uuid-...",
  "chapter_num": 1,
  "title": "The Signal",
  "content": "The observation dome was silent except for...",
  "summary": "Lyra discovers an anomalous pattern in the stellar data.",
  "word_count": 3200
}
```

**Connections table** (`novalist-connections`):
```json
{
  "connection_id": "abc123=",
  "token": "eyJ...",
  "connected_at": 1712534400,
  "ttl": 1712620800
}
```

---

## Deployment Guide

### Prerequisites

- **AWS CLI** configured with credentials that have admin-level access
- **AWS CDK CLI** v2.170+ (`npm install -g aws-cdk`)
- **Python 3.12+**
- **Node.js 18+** and npm
- **Amazon Bedrock model access**: Enable Claude Sonnet 4.6 in the Bedrock console for your target region (default: `us-east-1`)

> **Note**: Docker is **not** required locally. The backend container image is built in the cloud using AWS CodeBuild.

### Step-by-Step Deployment

```bash
# 1. Clone and enter the project
cd novalist

# 2. Install frontend dependencies and build
cd frontend
npm install
# Don't build yet — need CDK outputs for env vars
cd ..

# 3. Set up CDK virtual environment
cd infra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Bootstrap CDK (first time only)
cdk bootstrap aws://ACCOUNT_ID/us-east-1

# 5. Deploy infrastructure stacks (except frontend — needs env vars)
cdk deploy NovalistStorage NovalistAuth NovalistBackend NovalistApi --require-approval never

# 6. Note the CDK outputs:
#    NovalistAuth.UserPoolId = us-east-1_XXXXXXX
#    NovalistAuth.UserPoolClientId = XXXXXXXXXXXXXXXXXXXXXXXXXX
#    NovalistApi.WebSocketUrl = wss://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/prod

# 7. Configure frontend environment
cd ../frontend
cp .env.example .env
# Edit .env with the values from step 6:
#   VITE_COGNITO_USER_POOL_ID=us-east-1_XXXXXXX
#   VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
#   VITE_WEBSOCKET_URL=wss://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/prod

# 8. Build frontend
npm run build

# 9. Deploy frontend stack
cd ../infra
cdk deploy NovalistFrontend --require-approval never

# 10. Access the app
# The CloudFront URL is printed in the NovalistFrontend outputs:
#   NovalistFrontend.DistributionUrl = https://d1234567890abc.cloudfront.net

# 11. Log in with admin credentials
#   Email: admin@novalist.ai
#   Password: Admin123!Change
```

### Updating After Code Changes

```bash
# Backend changes only:
cd infra && cdk deploy NovalistBackend

# Frontend changes only:
cd frontend && npm run build && cd ../infra && cdk deploy NovalistFrontend

# All stacks:
cd infra && cdk deploy --all
```

### Tearing Down

```bash
cd infra
cdk destroy --all
```

All tables have `RemovalPolicy.DESTROY` and the S3 bucket has `auto_delete_objects=True`, so `cdk destroy` will clean up everything.

---

## Configuration Reference

### Backend Environment Variables

| Variable | Required | Default | Set By |
|----------|----------|---------|--------|
| `AWS_REGION` | No | `us-east-1` | CDK (BackendStack) |
| `BEDROCK_MODEL_ID` | No | `us.anthropic.claude-sonnet-4-6` | Manual override |
| `NOVELS_TABLE` | Yes | `novalist-novels` | CDK (BackendStack) |
| `CHAPTERS_TABLE` | Yes | `novalist-chapters` | CDK (BackendStack) |
| `COGNITO_USER_POOL_ID` | No | _(empty = auth disabled)_ | Manual / CDK |
| `COGNITO_REGION` | No | `us-east-1` | Manual / CDK |
| `LOG_LEVEL` | No | `INFO` | CDK (BackendStack) |

### Frontend Environment Variables

| Variable | Required | Source |
|----------|----------|--------|
| `VITE_COGNITO_USER_POOL_ID` | Yes | CDK output: `NovalistAuth.UserPoolId` |
| `VITE_COGNITO_CLIENT_ID` | Yes | CDK output: `NovalistAuth.UserPoolClientId` |
| `VITE_WEBSOCKET_URL` | Yes | CDK output: `NovalistApi.WebSocketUrl` |

---

## Local Development

### Running the Backend Locally

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Auth is automatically disabled when COGNITO_USER_POOL_ID is empty
export AWS_REGION=us-east-1
export NOVELS_TABLE=novalist-novels
export CHAPTERS_TABLE=novalist-chapters

uvicorn app.main:app --reload --port 8000
```

Note: You need valid AWS credentials with Bedrock and DynamoDB access. For fully local development, consider using DynamoDB Local and mocking Bedrock calls.

### Running the Frontend Locally

```bash
cd frontend
npm install

# Create .env with local settings:
# VITE_COGNITO_USER_POOL_ID=   (empty = allows any login locally)
# VITE_COGNITO_CLIENT_ID=local
# VITE_WEBSOCKET_URL=ws://localhost:8080

npm run dev
```

### Testing the Health Endpoint

```bash
curl http://localhost:8000/health
# {"status": "ok", "service": "novalist"}
```

---

## Security Considerations

### Authentication

- **Cognito User Pool** handles all user registration and authentication. Passwords require 8+ characters with uppercase, lowercase, and digits.
- **JWT tokens** have 1-hour expiry for ID/access tokens. The frontend automatically refreshes sessions using Cognito's 30-day refresh tokens.
- **WebSocket auth**: The JWT is passed as a query parameter on the WebSocket `$connect` handshake and stored in DynamoDB. Future enhancement: add a Lambda authorizer on `$connect` to validate the JWT server-side before allowing the connection.

### Network Security

- **S3 bucket** is private (all public access blocked). Content is served exclusively through CloudFront via an Origin Access Identity.
- **CloudFront** enforces HTTPS — HTTP requests are redirected.
- **Fargate ALB** is currently public-facing. For production, consider placing it in a private subnet and routing WebSocket Lambda traffic through a VPC endpoint.

### IAM Permissions

- **Fargate task role**: Scoped to DynamoDB read/write on specific tables and Bedrock invoke. The Bedrock permission uses `Resource: *` because Bedrock model ARNs vary by region and inference profile.
- **Lambda roles**: Each WebSocket Lambda has only the permissions it needs (DynamoDB for connections, `execute-api:ManageConnections` for posting back to clients).

### Data

- All DynamoDB tables use AWS-managed encryption at rest (default).
- Novel content and chapters are stored as plain text. For sensitive content, consider enabling KMS encryption.
- The connections table uses TTL (24-hour expiry) to automatically clean up stale records.

---

## Cost Estimation

Monthly cost estimate for light usage (one user, a few novel generations per week):

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| **CloudFront + S3** | $1–3 | Minimal traffic for static site |
| **Cognito** | $0 | Free tier covers 50,000 MAU |
| **API Gateway WebSocket** | $1–5 | $1/million connection-minutes + $1/million messages |
| **Lambda** | $0–2 | Free tier covers most light usage |
| **ECS Fargate** | $15–40 | 0.5 vCPU / 1 GB — runs continuously |
| **DynamoDB** | $0–5 | Pay-per-request, minimal storage |
| **Bedrock (Claude Sonnet 4.6)** | $20–100+ | Depends on novel length and frequency |
| **VPC NAT Gateway** | $30+ | Fixed cost for NAT Gateway hours + data |
| **ECR** | $0–1 | Container image storage |
| **CloudWatch Logs** | $1–3 | Log ingestion and storage |
| **Total** | **~$70–190/month** | Dominated by Fargate + NAT + Bedrock |

**Cost optimization tips:**

- Scale Fargate to 0 when not in use (remove from CDK `desired_count` or use scheduled scaling).
- Use Fargate Spot for non-production workloads (up to 70% savings).
- Reduce NAT Gateway cost by using VPC endpoints for DynamoDB and Bedrock.
- Use smaller models (e.g., Claude Haiku) for planning agents to reduce Bedrock costs.
- Set `desired_count: 0` and use ECS Service Auto Scaling to spin up on demand.

---

## Extending the System

### Adding New Agents

1. Create a new agent file in `backend/app/agents/` following the pattern:

```python
from strands import Agent
from app.agents.models import get_model  # or get_planning_model / get_creative_model
from app.tools.story_tools import save_story_element

SYSTEM_PROMPT = """Your agent's system prompt..."""

def create_your_agent() -> Agent:
    return Agent(
        name="your_agent",
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[save_story_element],
        callback_handler=None,
    )
```

2. Add the agent to the graph in `orchestrator.py`:

```python
from app.agents.your_agent import create_your_agent

# In build_novel_graph():
your_agent = create_your_agent()
builder.add_node(your_agent, "your_agent")
builder.add_edge("upstream_agent", "your_agent")
```

### Adding New Tools

Define tools with the Strands `@tool` decorator:

```python
from strands import tool
from strands.types.tools import ToolContext

@tool(context=True)
def your_tool(arg1: str, arg2: int, tool_context: ToolContext) -> str:
    """Tool description for the LLM to understand when to use it.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.
    """
    user_id = tool_context.invocation_state.get("user_id")
    # ... implementation ...
    return "result string"
```

### Adding New Writing Styles

1. Add the style to `WritingStyle` enum in `backend/app/models/schemas.py`.
2. Add the style description to the Prose Writer's system prompt in `backend/app/agents/prose_writer.py`.
3. Add the style option to the `STYLES` array in `frontend/src/components/StorySetup.tsx`.

### Adding New Narrative Structures

1. Add to `NarrativeStructure` enum in `backend/app/models/schemas.py`.
2. Add the structure definition to the Story Architect's system prompt in `backend/app/agents/story_architect.py`.
3. Add the option to the `STRUCTURES` array in `frontend/src/components/StorySetup.tsx`.

### Future Enhancements

- **Per-chapter regeneration**: Use the `generate_chapter` action to re-run the Prose Writer + Editor pipeline for a single chapter without re-running the entire graph.
- **Interactive editing**: Allow users to provide feedback on individual chapters and have the Editor agent revise based on that feedback.
- **WebSocket Lambda authorizer**: Add JWT validation on `$connect` to reject unauthenticated WebSocket connections at the gateway level.
- **Streaming prose**: Enhance the Prose Writer to stream token-by-token prose output using Strands' `stream_async()` API, sending `prose_chunk` messages for each token batch.
- **Novel export**: Add PDF/EPUB export functionality using a dedicated export tool.
- **Collaborative editing**: Allow multiple users to contribute to the same novel using optimistic concurrency on DynamoDB records.
- **Cost reduction**: Swap planning agents to Claude Haiku for structured tasks; reserve Claude Sonnet for prose and editing.

---

## Test Suite

The project includes 51 backend unit tests covering all components.

### Running Tests

```bash
cd backend
source venv/bin/activate  # or create with: python3 -m venv venv && pip install -r requirements.txt pytest pytest-asyncio moto httpx
python -m pytest tests/ -v
```

### Test Coverage

| File | Tests | Coverage |
|------|-------|---------|
| `tests/test_schemas.py` | 22 | All Pydantic models, enum values, validation bounds |
| `tests/test_main.py` | 10 | All FastAPI endpoints with mocked dependencies |
| `tests/test_orchestrator.py` | 6 | Prompt building, graph structure, node edges |
| `tests/test_tools.py` | 8 | DynamoDB persistence tools with mocked AWS |
| `tests/test_auth.py` | 5 | JWT verification, local-dev bypass, error handling |
| **Total** | **51** | |

All AWS services (DynamoDB, Bedrock, API Gateway) are mocked — no real AWS calls are made during testing.
