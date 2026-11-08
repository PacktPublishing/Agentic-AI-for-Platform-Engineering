# Chapter 7 — Operational Agents and Collaboration: Deep Dive & Deployment Guide

> **Book:** [*Agentic AI for Platform Engineering*](https://www.oreilly.com/library/view/agentic-ai-for/9781806386659/) — Chapter 7, *Operational Agents and Collaboration*
> **Lab source:** [`chapter-07/`](../chapter-07/) · **Series index:** [guides/README.md](README.md) · **Previous:** [Chapter 5 — AI-Powered Backstage](chapter-05-ai-powered-backstage.md) · **Next:** [Chapter 8 — Security in Practice](chapter-08-security-in-practice.md)

> [!WARNING]
> Learning and experimentation only — see the [repository warning](../README.md). Not a production baseline.

| At a glance | |
|---|---|
| **Builds on** | [Lab 0 cluster setup](00-cluster-setup.md) and all of [Chapter 5](chapter-05-ai-powered-backstage.md): the kind cluster with ArgoCD, the `backstage-app-discovery` ApplicationSet, your `backstage-components` repo, the Backstage app with the Chat Assistant, `my-first-app`, and the `argocd/github-creds` Secret |
| **Feeds into** | [Chapter 8](chapter-08-security-in-practice.md), which secures this same three-agent platform with guardrails, OPA, Keycloak identity, and tenant isolation |
| **Labs** | 0 Prerequisites · 1 Strands runtime · 2 Cluster diagnostics · 3 GitOps and collaboration · 4 Backstage chat · 5 Langfuse and audit |
| **Approx. time** | 4–5 hours end to end (most of it is image builds, PR round trips, and waiting for ArgoCD) |
| **Cost / credentials** | Amazon Bedrock with access to Claude Sonnet 4.5 (default `us.anthropic.claude-sonnet-4-5-20250929-v1:0`, region `us-west-2`) **or** an `ANTHROPIC_API_KEY`; the Chapter 5 GitHub PAT with Contents and Pull requests read/write. Your provider bills model usage per token, and each multi-agent request in Labs 3–5 makes several model calls. |

---

## 1. What you'll build

Chapter 5 gave developers a chat box in Backstage. Chapter 7 replaces the brain behind it with an **agent runtime that lives in the cluster and is delivered through GitOps**. The runtime hosts three agents that work together. The **Platform Coordinator** understands the request and delegates it. The **Cluster Diagnostics Agent** reads live Kubernetes state through the upstream Kubernetes MCP server in read-only mode. The **GitOps Change Agent** reads manifests and proposes repairs as pull requests through GitHub's official MCP server. No agent can change the cluster or merge a PR. Every change goes branch → PR → human review and merge → ArgoCD. Langfuse traces and a hash-chained audit log show what each agent did.

```mermaid
flowchart LR
    User["Developer"] --> Chat["Backstage Chat Assistant<br/>(host, :3000/:7007)"]
    Chat --> Adapter["strands-proxy adapter<br/>(Backstage backend)"]
    Adapter -->|"POST /invoke via<br/>port-forward :18080"| RT
    subgraph K["kind cluster: agent-platform namespace"]
        RT["agent-runtime 0.7.5"]
        subgraph RT_IN["inside the runtime"]
            Coord["Platform Coordinator"] -->|diagnose_application| Diag["Diagnostics Agent"]
            Coord -->|"review_configuration /<br/>propose_change"| Git["GitOps Agent"]
        end
        Diag --> KMCP["cluster-mcp<br/>(kubernetes-mcp-server, read-only)"]
        Git --> GMCP["gitops-mcp<br/>(github-mcp-server)"]
        RT -.-> PVC[("PVCs: memory, audit")]
    end
    Coord -->|"catalog + TechDocs search<br/>(service token)"| BS["Backstage API<br/>host.docker.internal:7007"]
    KMCP -->|"get/list only"| API["Kubernetes API"]
    GMCP --> GH["GitHub: backstage-components"]
    GH --> PR["PR → human review & merge"]
    PR --> Argo["ArgoCD"] --> App["my-first-app"]
    RT -.->|"traces"| LF["Langfuse + Postgres<br/>(langfuse namespace)"]
```

| Lab | What it adds | Key artifacts |
|---|---|---|
| [0 — Prerequisites](../chapter-07/0-prereqs/README.md) | Shell paths, the `agent-platform` namespace, the model and GitHub Secrets, verification | [`verify.sh`](../00-cluster-setup/verify.sh) |
| [1 — Strands runtime](../chapter-07/1-strands-runtime/README.md) | A FastAPI + Strands agent service with `/invoke`, identity from a ConfigMap, memory on a PVC, delivered by ArgoCD | [`agent.py`](../chapter-07/1-strands-runtime/files/agent/app/agent.py), [`configmap-identity.yaml`](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/configmap-identity.yaml) |
| [2 — Cluster diagnostics](../chapter-07/2-cluster-diagnostics/README.md) | The upstream Kubernetes MCP server (read-only, `core` toolset), cluster-wide read RBAC, a diagnostics agent with a tool budget | [`cluster-mcp-deployment.yaml`](../chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-deployment.yaml), [`cluster-mcp-rbac.yaml`](../chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-rbac.yaml) |
| [3 — GitOps and collaboration](../chapter-07/3-gitops-mcp/README.md) | GitHub's official MCP server, the coordinator with agents as tools, scope and PR-format hooks, the `fix-image-tag` skill, a deliberate image break and an agent-proposed repair PR | [`coordinator_tools.py`](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py), [`hooks.py`](../chapter-07/3-gitops-mcp/files/agent/app/hooks.py), [`SKILL.md`](../chapter-07/3-gitops-mcp/files/skills/fix-image-tag/SKILL.md) |
| [4 — Backstage chat](../chapter-07/4-backstage-collaboration/README.md) | A Backstage backend module that sends the existing chat to the runtime, plus a service token for catalog search | [`strands-proxy-agent.ts`](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts) |
| [5 — Observability](../chapter-07/5-langfuse-audit/README.md) | Self-hosted Langfuse v2, per-agent traces linked by session, a hash-chained audit log on a PVC | [`hooks_langfuse.py`](../chapter-07/5-langfuse-audit/files/agent/app/hooks_langfuse.py), [`audit.py`](../chapter-07/5-langfuse-audit/files/agent/app/audit.py) |

### How the code evolves from lab to lab

Each lab ships a **complete** agent source tree (`files/agent/`) and only the **changed or new** Kubernetes manifests (`files/components-repo/`). Your components repo collects these changes over the labs, and later labs overwrite `deployment.yaml` each time.

| Lab | Image tag | Entry point builds… | New or changed code | New or changed manifests |
|---|---|---|---|---|
| 1 | `agent-runtime:0.7.1` | one agent + `save_to_memory` | `agent.py`, `identity.py`, `settings.py`, `main.py` | namespace, SA, Service, Deployment, `agent-identity` ConfigMap, `agent-memory` PVC, Argo marker |
| 2 | `agent-runtime:0.7.2` | one diagnostics agent | `mcp_clients.py` (Kubernetes MCP), `budget.py` (12-call budget); identity and memory are **removed** | `cluster-mcp` Deployment, Service, SA, ClusterRole + Binding; Deployment without identity or memory volumes |
| 3 | `agent-runtime:0.7.3` | coordinator + 2 specialists | `platform_coordinator.py`, `coordinator_tools.py`, `diagnostics_agent.py`, `gitops_agent.py`, `hooks.py`, `skills.py`, `catalog.py`; identity and memory **restored** with skills added | `gitops-mcp` Deployment + Service, skills ConfigMap, Deployment with GitHub env, skills mount, startup probe |
| 4 | *(no new image)* | — | `strands-proxy-agent.ts` in **Backstage** | none (a Secret plus Backstage config) |
| 5 | `agent-runtime:0.7.5` | same as Lab 3 + observability hooks | new: `audit.py`, `hooks_langfuse.py`, `telemetry.py`, `request_context.py`; changed: `settings.py`, `main.py`, `platform_coordinator.py`; `mcp` 1.27.0 → 1.28.1, adds `langfuse==2.60.10` | `agent-audit` PVC, Deployment with Langfuse env and audit mount, and the new `langfuse/` app (Postgres + Langfuse) |

Lab 5 does not change Lab 3's `catalog.py`, `coordinator_tools.py`, `diagnostics_agent.py`, `gitops_agent.py`, `hooks.py`, `identity.py`, `mcp_clients.py`, or `skills.py`. To see exactly what observability adds, run:

```bash
diff -ru "$BOOK_REPO/chapter-07/3-gitops-mcp/files/agent/app" "$BOOK_REPO/chapter-07/5-langfuse-audit/files/agent/app"
```

---

## 2. Concepts deep dive

### 2.1 The agent runtime as a platform service

**What it is.** The runtime is a small FastAPI app. `POST /invoke` takes `{intent, session_id, user_id}` and returns `{session_id, response}` ([main.py L18-39](../chapter-07/1-strands-runtime/files/agent/app/main.py#L18-L39)). Each request builds a fresh [Strands](https://strandsagents.com/) `Agent` with a model, a system prompt, tools, and (from Lab 2 on) hooks. It then calls `agent(intent)`. Strands runs the **agent loop**: the model reasons, picks a tool, Strands runs it, the result goes back to the model, and this repeats until the model gives a final answer. The code contains no hand-written orchestration graph.

**Model providers.** `_make_model()` switches on `LLM_PROVIDER`. `bedrock` uses `BedrockModel(model_id, region_name)` and `anthropic` uses `AnthropicModel(model_id, api_key)` ([agent.py L9-24](../chapter-07/1-strands-runtime/files/agent/app/agent.py#L9-L24)). Credentials come in through `envFrom` the `agent-llm-credentials` Secret ([deployment.yaml L39-41](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/deployment.yaml#L39-L41)). Because the model is behind one factory, the provider is a deployment setting, not a code change.

**Why it matters.** Running agents as a versioned, GitOps-delivered service gives platform teams the same controls they already use for every other workload: image tags, reviewed manifests, probes, resource limits, and rollbacks. A developer's laptop agent has none of these.

**Production would differ:** stream responses (the endpoint is request/response), run more than one replica (blocked here by RWO PVCs and `strategy: Recreate`), and authenticate callers. Chapter 8 adds authentication.

### 2.2 Identity is reviewed config; memory is agent-written state

The runtime keeps three kinds of state, and each one has its own storage and lifecycle:

| State | Where | Who writes it | Survives pod restart? |
|---|---|---|---|
| Identity: `SOUL.md`, `IDENTITY.md`, `USER.md` | `agent-identity` ConfigMap, mounted read-only at `/state/identity` ([configmap-identity.yaml](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/configmap-identity.yaml)) | Humans, through PRs | Yes, because it lives in Git |
| Long-term memory: `MEMORY.md` | `agent-memory` PVC at `/state/memory` ([pvc-memory.yaml](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/pvc-memory.yaml)) | The agent, through `save_to_memory` ([agent.py L27-34](../chapter-07/1-strands-runtime/files/agent/app/agent.py#L27-L34)) | Yes, while the PVC exists |
| Conversation history per `session_id` | `FileSessionManager` under `/state/sessions` ([agent.py L37-48](../chapter-07/1-strands-runtime/files/agent/app/agent.py#L37-L48)) | The Strands runtime | **No.** It is an `emptyDir` ([deployment.yaml L76-77](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/deployment.yaml#L76-L77)) |

`load_system_prompt()` builds the prompt from these files on **every request** ([identity.py L12-34](../chapter-07/1-strands-runtime/files/agent/app/identity.py#L12-L34)). A merged identity PR therefore takes effect as soon as the kubelet refreshes the mounted ConfigMap, with no restart. `SOUL.md` holds the hard constraints, such as "never apply changes to the cluster directly". Keeping them in Git means each constraint has a change history and a reviewer.

> [!IMPORTANT]
> Constraints written in a prompt are guidance, not enforcement. Labs 2–3 add **code** limits (read-only MCP flags, RBAC, hooks) that hold even when the model ignores its prompt. Chapter 8 adds policy enforcement.

### 2.3 MCP as the tool boundary

From Lab 2 on, the runtime does not call the Kubernetes or GitHub APIs itself. It connects to MCP servers over **streamable HTTP** at `<url>/mcp`. At startup it discovers their tools and hands those tools to the agents ([diagnostics_agent.py L18-37](../chapter-07/3-gitops-mcp/files/agent/app/diagnostics_agent.py#L18-L37), [gitops_agent.py L19-41](../chapter-07/3-gitops-mcp/files/agent/app/gitops_agent.py#L19-L41)). Connections open once, in FastAPI's `lifespan` ([main.py L18-22](../chapter-07/3-gitops-mcp/files/agent/app/main.py#L18-L22)). Each one retries 15 times, 2 s apart, so the runtime can start before its MCP servers are ready. The Lab 3 `startupProbe` allows 5 minutes (`periodSeconds: 5`, `failureThreshold: 60`, [deployment.yaml L75-80](../chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/deployment.yaml#L75-L80)).

Two consequences follow:

- **The tool list is fixed at startup.** If you add a tool to an MCP server, restart the runtime to pick it up.
- **Credentials stay with the runtime, not in the MCP pod.** The GitHub MCP Deployment has no Secret. The runtime sends `Authorization: Bearer <PAT>` with each MCP request ([gitops_agent.py L22-25](../chapter-07/3-gitops-mcp/files/agent/app/gitops_agent.py#L22-L25)), and the Kubernetes MCP server authenticates as its own ServiceAccount.

### 2.4 Least privilege for diagnostics, enforced three times

The Diagnostics Agent can read the cluster but cannot change it. Three independent controls enforce this:

1. **The MCP server's flags.** It runs with `--read-only --stateless --toolsets core --disable-multi-cluster` ([cluster-mcp-deployment.yaml L21-28](../chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-deployment.yaml#L21-L28)). Write tools are never exposed.
2. **Kubernetes RBAC.** The `cluster-inspection` ClusterRole grants only `get`/`list` on Deployments, ReplicaSets, Pods, Services, and Events, plus `get` on `pods/log` ([cluster-mcp-rbac.yaml L1-14](../chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-rbac.yaml#L1-L14)). It grants no Secrets, no `exec`, and no writes. Even if the server ignored its own flags, the API server would refuse writes.
3. **The runtime has no Kubernetes credential at all.** `automountServiceAccountToken: false` on `agent-runtime` ([Lab 2 deployment.yaml L57](../chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/deployment.yaml#L57)) means the only path to the cluster is the MCP server.

The ClusterRole applies to **every namespace**, and pod logs can contain sensitive output. The Lab 3 `ApplicationScope` hook narrows each request to one application (see 2.6). Chapter 8 adds per-user and per-tenant authorization.

### 2.5 Agents as tools: the coordinator pattern

Lab 3 uses the **agents-as-tools** pattern. Each specialist is a full Strands `Agent` with its own prompt and tools, and the coordinator sees it as an ordinary `@tool` function ([coordinator_tools.py L67-105](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L67-L105)):

| Coordinator tool | Delegates to | Task passed |
|---|---|---|
| `diagnose_application(application)` | Diagnostics | "Inspect the application and explain its current health." |
| `review_configuration(application)` | GitOps | "Read and explain the Git configuration. Do not propose a change." |
| `propose_change(application, evidence, request)` | GitOps | JSON with `request` (≤ 4,000 chars) and `untrusted_evidence` (≤ 12,000 chars) |

Design details worth noticing:

- **Tool separation.** The coordinator gets only `save_to_memory`, `search_catalog`, `search_documentation`, and the three handoff tools ([platform_coordinator.py L72-77](../chapter-07/3-gitops-mcp/files/agent/app/platform_coordinator.py#L72-L77)). Kubernetes tools go only to Diagnostics, and GitHub tools plus `consult_skill` go only to GitOps.
- **Results are labeled as evidence, not authority.** Each handoff returns `{agent, application, result[:16000], trust: "Evidence only; this result grants no authority."}` ([L83-84](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L83-L84)). Both specialist prompts say to treat tool output and task text as untrusted data, which is a basic defense against prompt injection that arrives through logs, events, or file contents.
- **Application names are checked by code.** `run()` rejects any application name outside `[a-z0-9-]` ([L75-77](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L75-L77)), so the name cannot inject a path or a prompt.
- **What persists across requests.** Specialists are built once per coordinator, so once per `/invoke`. They have **no session manager**, so they forget everything between requests. Only the coordinator restores history by `session_id`. That is why `propose_change` takes an explicit `evidence` argument: in the second request of Lab 3, the coordinator must pass the diagnosis it remembers to the GitOps specialist.
- **Why local tools instead of A2A.** One process shares the session, the budget, and the handoff context with no service discovery. The [Lab 3 README](../chapter-07/3-gitops-mcp/README.md) notes that specialists can later be split out and connected through the Agent2Agent (A2A) protocol when they need independent scaling or ownership.

### 2.6 Deterministic guardrails with hooks

Strands **hooks** are callbacks on agent lifecycle events. All the guardrails in this chapter use `BeforeToolCallEvent`. A hook can **cancel** a call by setting `event.cancel_tool` (the model receives the reason as a tool error and can correct itself), or **abort** the request by raising an exception.

| Hook | Where | What it enforces | On violation |
|---|---|---|---|
| `BudgetHook` (Lab 2) | [budget.py](../chapter-07/2-cluster-diagnostics/files/agent/app/budget.py) | At most 12 tool calls per request | raises `request_tool_budget_exhausted` |
| `BudgetHook` (Lab 3+) | [coordinator_tools.py L20-34](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L20-L34) | 24 calls for the coordinator per request; **each delegation gets a fresh 24-call budget** through a `ContextVar` | raises `request_tool_budget_exhausted` |
| `ApplicationScope` | [coordinator_tools.py L37-64](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L37-L64) | Diagnostics: `namespace` and `name` must match the delegated application (list tools may omit `name`). GitOps: files only at `<app>/k8s/deployment.yaml`, branches must start with `agent/`, PR titles with `[agent] `, and **every other GitHub tool is denied** | `cancel_tool = 'delegation_scope_mismatch'` |
| `AlwaysPRHook` | [hooks.py L12-55](../chapter-07/3-gitops-mcp/files/agent/app/hooks.py#L12-L55) | `create_pull_request` needs a `[agent] ` title prefix and a body of at least 20 characters | `cancel_tool` with a corrective message |

As the `AlwaysPRHook` docstring puts it, "a prompt is a hint the model can ignore. A hook is code that runs on every tool call." `AlwaysPRHook` checks the **quality** of a proposal, not **permission**. Chapter 8 handles permission with OPA.

> [!NOTE]
> The scope hook checks paths, branches, and titles. It does not check the `owner`/`repo` arguments. The GitOps prompt pins them from `GITHUB_REPO_OWNER`/`GITHUB_REPO_NAME` ([gitops_agent.py L47-64](../chapter-07/3-gitops-mcp/files/agent/app/gitops_agent.py#L47-L64)), and the PAT's repository scope is the real limit. Give the PAT access to `backstage-components` only.

### 2.7 Skills and progressive disclosure

A **skill** is a folder with a `SKILL.md`: YAML frontmatter (`name`, `description`, `when_to_use`, `constraints`) followed by a procedure ([SKILL.md](../chapter-07/3-gitops-mcp/files/skills/fix-image-tag/SKILL.md)). `skills.py` reads only the **name and description** of every skill into the system prompt ([skills.py L72-83](../chapter-07/3-gitops-mcp/files/agent/app/skills.py#L72-L83)). The full body loads only when the model calls `consult_skill(name)` ([platform_coordinator.py L48-57](../chapter-07/3-gitops-mcp/files/agent/app/platform_coordinator.py#L48-L57)). This is the progressive-disclosure idea behind Anthropic's Agent Skills: many procedures cost a few lines of context each until one is needed.

The skill ships to the cluster as the `agent-skills-fix-image-tag` ConfigMap, mounted at `/state/skills/fix-image-tag` ([configmap-skills.yaml](../chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/configmap-skills.yaml)). Procedures are therefore versioned and reviewed the same way as identity.

> [!NOTE]
> `files/skills/fix-image-tag/SKILL.md` and the copy embedded in `configmap-skills.yaml` are identical today. If you edit the skill, edit the **ConfigMap** in your components repo, because that is what the runtime reads. Also, the skills section is added to the **coordinator's** system prompt (through `load_system_prompt()`), but `consult_skill` is given only to the **GitOps** specialist ([coordinator_tools.py L72](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py#L72)). The coordinator uses the description to decide when to delegate, and the specialist loads the procedure.

### 2.8 The PR-only change path

The GitHub MCP server runs in HTTP mode with a four-tool allowlist, `GITHUB_TOOLS=get_file_contents,create_branch,create_or_update_file,create_pull_request` ([gitops-mcp-deployment.yaml L24-30](../chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/gitops-mcp-deployment.yaml#L24-L30)). It has no merge tool, and `ApplicationScope` denies anything outside the expected four calls. The skill spells out the order: read the manifest (keep the blob SHA) → `create_branch agent/...` → `create_or_update_file` with that SHA → `create_pull_request`. A human reviews and merges, and ArgoCD's automated sync applies the change. The agent's write access ends at "open a PR". Production should add branch protection with required reviews and no bypass for the agent's token, as the [Lab 0 README](../chapter-07/0-prereqs/README.md) notes.

### 2.9 Observability: traces and tamper-evident audit

Lab 5 adds two hooks to every agent ([platform_coordinator.py L71-72](../chapter-07/5-langfuse-audit/files/agent/app/platform_coordinator.py#L71-L72)):

- **`LangfuseStrandsHook`** ([hooks_langfuse.py](../chapter-07/5-langfuse-audit/files/agent/app/hooks_langfuse.py)) opens a Langfuse **trace per agent invocation**, named `coordinator.invoke`, `diagnostics.invoke`, or `gitops.invoke`, plus a **span per tool call** that records the tool's input arguments. The specialists' traces are **separate traces linked by `session_id`**. They are not nested under the coordinator's span. `main.py` places the session and user IDs in `ContextVar`s ([request_context.py](../chapter-07/5-langfuse-audit/files/agent/app/request_context.py), [main.py L47-58](../chapter-07/5-langfuse-audit/files/agent/app/main.py#L47-L58)). Telemetry stays off unless `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, and `LANGFUSE_SECRET_KEY` are all set ([settings.py L28-34](../chapter-07/5-langfuse-audit/files/agent/app/settings.py#L28-L34)).
- **`AuditHook` + `AuditLog`** ([audit.py](../chapter-07/5-langfuse-audit/files/agent/app/audit.py)) write `before_tool` and `after_tool` JSON lines to `/state/audit/AUDIT.log` on the `agent-audit` PVC. Each record stores `prev_hash` and `hash = sha256(canonical JSON without hash)` ([audit.py L55-68](../chapter-07/5-langfuse-audit/files/agent/app/audit.py#L55-L68)). On startup the log resumes the chain from its last line ([L35-53](../chapter-07/5-langfuse-audit/files/agent/app/audit.py#L35-L53)). Audit records keep only the argument **names** ([L92](../chapter-07/5-langfuse-audit/files/agent/app/audit.py#L92)).

The two hooks have different jobs. Traces are for **debugging and cost**, and they carry argument **values**, so treat Langfuse as a store of sensitive data. The audit log is for **accountability**. A hash chain detects edits inside the chain, but anyone who can write the file can rewrite the whole chain or cut off its tail. Chapter 8 discusses trusted evidence and these limits.

> [!NOTE]
> The lab pins the Langfuse Python SDK v2 (`langfuse==2.60.10`) and its trace/span API, and does not use OTLP. Langfuse also accepts OpenTelemetry, and Strands can emit OTel spans natively. That is the more portable production route; see Further reading.

---

## 3. Prerequisites

**From earlier chapters (check before you start):**

- [ ] The kind cluster `agentic-platform` with Metrics Server and ArgoCD ([00-cluster-setup.md](00-cluster-setup.md))
- [ ] The `backstage-app-discovery` ApplicationSet applied with your GitHub username ([Chapter 5 Lab 1](chapter-05-ai-powered-backstage.md))
- [ ] A local clone of your `backstage-components` repo, with `my-first-app` **Synced/Healthy** in ArgoCD
- [ ] `argocd/github-creds` with `url` and `password` (PAT with **Contents** and **Pull requests** read/write). See [Chapter 5's credential step](../chapter-05/1-backstage-setup/README.md#step-5-configure-github-credentials-required-for-private-repos).
- [ ] The Chapter 5 Backstage app, with the GenAI Chat Assistant working (needed from Lab 4)

**Tools:** Docker, kind, kubectl, curl, jq, Git, the GitHub CLI (`gh`, authenticated), `openssl`, Node.js and Yarn (for Backstage).

> [!IMPORTANT]
> The image-load commands use `docker image save --platform`, which first appeared in **Docker Engine 28**. Check with `docker version --format '{{.Server.Version}}'`. On older engines, upgrade Docker. As a fallback, `kind load docker-image <image>:<tag> --name agentic-platform` usually works for single-platform images.

**Pinned versions in this chapter:** `strands-agents==1.38.0`, `fastapi==0.115.0`, `mcp==1.27.0` (Labs 2–3) / `1.28.1` (Lab 5), `langfuse==2.60.10`, base image `python:3.12-slim`, `quay.io/containers/kubernetes_mcp_server:v0.0.66`, `ghcr.io/github/github-mcp-server:v1.12.1`, `langfuse/langfuse:2`, `postgres:16-alpine`.

### Shell variables

| Variable | Set in | Purpose |
|---|---|---|
| `BOOK_REPO` | Lab 0 | Absolute path to **this** repository's clone. The README's placeholder says `ai-driven-platform-engineering-book`, but use your actual clone path. |
| `COMPONENTS_REPO` | Lab 0 | Absolute path to your `backstage-components` clone |
| `GITHUB_USERNAME` | Lab 0 | Repo owner, parsed from `argocd/github-creds` |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Lab 0 | PAT read from `argocd/github-creds` (never printed) |
| `KIND_PLATFORM` | Lab 1 | `linux/arm64` (Apple Silicon) or `linux/amd64` (Intel/AMD) |
| `SESSION_ID` | Lab 3 | `chapter07-lab3-broken`, shared by the diagnose and repair requests |
| `BACKSTAGE_APP` | Lab 4 | Absolute path to your Chapter 5 Backstage app |
| `BACKSTAGE_SERVICE_TOKEN` | Lab 4 | Static token Backstage accepts from the coordinator |

Re-export these in every new terminal. Labs 1, 2, 3, and 5 fail fast with `${VAR:?...}` guards if a variable is missing.

### Runtime environment (agent-runtime Deployment)

| Env var | Default / value | Purpose | Used in |
|---|---|---|---|
| `LLM_PROVIDER` | `bedrock` | `bedrock` or `anthropic` | all labs |
| `BEDROCK_MODEL_ID` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock inference profile | all labs |
| `AWS_REGION` | `us-west-2` (from the Secret) | Bedrock region | all labs |
| `ANTHROPIC_MODEL_ID` / `ANTHROPIC_API_KEY` | `claude-sonnet-4-5` / from the Secret | Anthropic alternative | all labs |
| `IDENTITY_DIR`, `MEMORY_FILE`, `SESSION_DIR` | `/state/identity`, `/state/memory/MEMORY.md`, `/state/sessions` | Identity, memory, and sessions | 1, 3, 5 |
| `MCP_CLUSTER_URL` | `http://cluster-mcp.agent-platform.svc.cluster.local:8080` | Kubernetes MCP | 2+ |
| `MCP_GITOPS_URL` | `http://gitops-mcp.agent-platform.svc.cluster.local:8080` | GitHub MCP | 3+ |
| `GITHUB_REPO_OWNER` / `_NAME` / `_DEFAULT_BRANCH` | `YOUR_USERNAME` (substituted) / `backstage-components` / `main` | The GitOps agent's fixed repository | 3+ |
| `SKILLS_DIR` | `/state/skills` | Skill folders | 3+ |
| `BACKSTAGE_URL` | `http://host.docker.internal:7007` | Catalog and TechDocs search | 3+ |
| `AUDIT_LOG`, `AGENT_ID` | `/state/audit/AUDIT.log`, `platform-ops` | Audit log | 5 |
| `LANGFUSE_HOST` | `http://langfuse.langfuse.svc.cluster.local:3000` | Trace backend | 5 |

### Secrets (all created by hand, never committed to Git)

| Secret | Namespace | Keys | Created in | Consumed by |
|---|---|---|---|---|
| `agent-llm-credentials` | `agent-platform` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` **or** `ANTHROPIC_API_KEY` | Lab 0 | runtime `envFrom` |
| `gitops-mcp-github` | `agent-platform` | `GITHUB_PERSONAL_ACCESS_TOKEN` | Lab 0 | runtime env (Lab 3+), sent as the MCP bearer token |
| `agent-backstage-read` | `agent-platform` | `BACKSTAGE_SERVICE_TOKEN` | Lab 4 | runtime `envFrom` (optional) |
| `langfuse-db` | `langfuse` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL` | Lab 5 | Postgres + Langfuse |
| `langfuse-app` | `langfuse` | `NEXTAUTH_SECRET`, `SALT` | Lab 5 | Langfuse |
| `agent-langfuse-keys` | `agent-platform` | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Lab 5 | runtime `envFrom` (optional) |

### The delivery loop you will repeat

Every lab follows the same loop. Learn it once:

```mermaid
flowchart LR
    A["docker build<br/>--platform $KIND_PLATFORM"] --> B["docker image save<br/>--platform → tar"]
    B --> C["kind load image-archive"]
    D["cp manifests →<br/>$COMPONENTS_REPO"] --> E["sed YOUR_USERNAME"]
    E --> F["branch → commit → PR<br/>→ review → merge"]
    F --> G["annotate ApplicationSet<br/>refresh"]
    C --> H["ArgoCD sync →<br/>new pod runs new tag"]
    G --> H
```

- **Why the build commands look this way.** A kind node runs containerd and cannot pull `agent-runtime:0.7.x`, because the image exists only in your local Docker. You build for the node's architecture, save **that one platform** to a tarball, and import it with `kind load image-archive`. The Lab 3 README explains that this avoids kind's multi-platform image import issue. To check your node's architecture: `kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.architecture}'`.
- **Why every lab uses a new tag.** Deployments use `imagePullPolicy: IfNotPresent`. A new tag in Git is what tells Kubernetes to roll out a new image. If you change code yourself, either bump the tag in `deployment.yaml` through a PR, or reload the same tag and run `kubectl -n agent-platform rollout restart deployment/agent-runtime`.
- **How ArgoCD finds new folders.** The Chapter 5 ApplicationSet uses a Git *files* generator on `*/argocd/application.yaml` ([argocd-applicationset.yaml L9-26](../chapter-05/1-backstage-setup/files/argocd-applicationset.yaml#L9-L26)). The **folder name** becomes the Application name, the source path `<folder>/k8s`, and the target namespace. That is why the runtime lives in `agent-platform/` and Langfuse in `langfuse/`. The generated Application has `prune` and `selfHeal` enabled.
- **Self-heal undoes manual edits.** A `kubectl edit` or `kubectl set env` on `agent-runtime` is reverted. Make lasting changes in Git. Secrets are the exception, because ArgoCD does not track them.

> [!TIP]
> Before each new lab branch, run `cd "$COMPONENTS_REPO" && git checkout main && git pull --ff-only` so the branch starts from what ArgoCD deploys. If your repo enforces reviews, `gh pr merge` fails until someone approves. Review and merge in the GitHub UI instead.

> [!TIP]
> **Using Anthropic instead of Bedrock?** Every lab overwrites `deployment.yaml` with `LLM_PROVIDER: bedrock`. After each copy step, run:
> `sed -i.bak 's/value: bedrock/value: anthropic/' "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml" && rm "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml.bak"`
> (`value: bedrock` appears exactly once in each lab's Deployment.)

---

## Lab 0 — Prerequisites

### Goal
Confirm that the Chapter 5 platform works, then create the namespace and the two credentials the runtime needs.

### How it works
The lab reuses your Chapter 5 PAT instead of asking for a new one. It reads `GITHUB_USERNAME` and the token **from the ArgoCD Secret** with `jq`'s `@base64d`, so the values never appear on screen. `verify.sh --github-secret argocd/github-creds` checks the cluster, Metrics Server, ArgoCD, and the ApplicationSet, then calls the GitHub API to confirm the PAT can **read** the repo ([verify.sh L95-137](../00-cluster-setup/verify.sh#L95-L137)). It cannot confirm write permission.

### Deploy
1. Set the paths and derive the owner:
   ```bash
   export BOOK_REPO=/absolute/path/to/ai-driven-platform-engineering-book   # use your actual clone path
   export COMPONENTS_REPO=/absolute/path/to/backstage-components
   export GITHUB_USERNAME="$(kubectl -n argocd get secret github-creds -o json \
     | jq -er '.data.url | @base64d | capture("^https://github\\.com/(?<owner>[A-Za-z0-9-]+)/").owner')"
   : "${GITHUB_USERNAME:?Could not read the repository owner from argocd/github-creds}"
   ```
2. Create the namespace:
   ```bash
   kubectl create namespace agent-platform --dry-run=client -o yaml | kubectl apply -f -
   ```
3. Create the model credential. Bedrock (default):
   ```bash
   kubectl create secret generic agent-llm-credentials \
     -n agent-platform --dry-run=client -o yaml \
     --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
     --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
     --from-literal=AWS_REGION="${AWS_REGION:-us-west-2}" \
     | kubectl apply -f -
   ```
   Or Anthropic (then set `LLM_PROVIDER=anthropic` in the runtime Deployment, as described in the tip in Section 3):
   ```bash
   kubectl create secret generic agent-llm-credentials \
     -n agent-platform --dry-run=client -o yaml \
     --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
     | kubectl apply -f -
   ```
4. Create the GitHub MCP credential:
   ```bash
   export GITHUB_PERSONAL_ACCESS_TOKEN="$(kubectl -n argocd get secret github-creds -o json \
     | jq -er '.data.password | @base64d')"
   : "${GITHUB_PERSONAL_ACCESS_TOKEN:?Could not read the GitHub token from argocd/github-creds}"
   kubectl -n agent-platform create secret generic gitops-mcp-github \
     --from-literal=GITHUB_PERSONAL_ACCESS_TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

### Verify
```bash
"$BOOK_REPO/00-cluster-setup/verify.sh" --github-secret argocd/github-creds
kubectl -n argocd get applications
```
Platform checks pass and `my-first-app` shows `Synced` / `Healthy`. Until Lab 4 you can ignore a warning that Backstage on `host.docker.internal:7007` is unreachable.

### Explore further
- Read the generated Secret keys (not values): `kubectl -n agent-platform get secret agent-llm-credentials -o jsonpath='{.data}' | jq 'keys'`.
- Test model access before you deploy anything. For Bedrock, `aws bedrock list-inference-profiles --region us-west-2` should list the Claude Sonnet 4.5 profile if your account has access.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Could not read the repository owner…` | `github-creds` missing, or its `url` is not `https://github.com/<owner>/…` | Redo [Chapter 5 Step 5](../chapter-05/1-backstage-setup/README.md#step-5-configure-github-credentials-required-for-private-repos) |
| `GitHub repository check failed (HTTP 401/403/404)` | PAT expired, or not scoped to `backstage-components` | Regenerate the PAT, then update `argocd/github-creds` and `gitops-mcp-github` |
| AWS keys are empty in the Secret | `AWS_*` not exported, for example when you use SSO profiles | Export static or temporary keys first. With temporary credentials, also add `--from-literal=AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN"`, and recreate the Secret when they expire. |

---

## Lab 1 — A Strands agent as a service

### Goal
Deploy the `agent-runtime` service through GitOps, call `/invoke`, and watch identity (from Git) and memory (on a PVC) shape its answers.

### How it works
- [`main.py`](../chapter-07/1-strands-runtime/files/agent/app/main.py) provides `/healthz` (used by the probes) and `/invoke`, which builds an agent per request.
- [`agent.py`](../chapter-07/1-strands-runtime/files/agent/app/agent.py) gives the agent one tool, `save_to_memory`, and a `FileSessionManager` keyed by `session_id`.
- [`identity.py`](../chapter-07/1-strands-runtime/files/agent/app/identity.py) builds the system prompt from four Markdown files: `# Who you are` (SOUL), `# What you can do` (IDENTITY), `# About the user you serve` (USER), and `# What you have committed to long-term memory` (MEMORY).
- [`deployment.yaml`](../chapter-07/1-strands-runtime/files/components-repo/agent-platform/k8s/deployment.yaml) uses `strategy: Recreate`, because the RWO memory PVC cannot attach to two pods at once during a rolling update.

```mermaid
sequenceDiagram
    participant C as curl
    participant R as agent-runtime
    participant M as Model (Bedrock/Anthropic)
    participant F as /state (ConfigMap, PVC, emptyDir)
    C->>R: POST /invoke {intent, session_id}
    R->>F: read SOUL/IDENTITY/USER/MEMORY, restore session
    R->>M: system prompt + history + intent
    M-->>R: tool_use save_to_memory(fact)
    R->>F: append "- fact" to MEMORY.md
    R->>M: tool result
    M-->>R: final answer
    R-->>C: {session_id, response}
```

### Deploy
1. Build and load the image (keep `KIND_PLATFORM` set for later labs):
   ```bash
   export KIND_PLATFORM=linux/arm64   # linux/amd64 on Intel/AMD
   docker build --platform "$KIND_PLATFORM" -t agent-runtime:0.7.1 \
     "$BOOK_REPO/chapter-07/1-strands-runtime/files/agent/"
   docker image save --platform "$KIND_PLATFORM" -o /tmp/agent-runtime.tar agent-runtime:0.7.1
   kind load image-archive /tmp/agent-runtime.tar --name agentic-platform
   rm /tmp/agent-runtime.tar
   ```
2. Copy the manifests and fill in the owner:
   ```bash
   cp -r "$BOOK_REPO/chapter-07/1-strands-runtime/files/components-repo/agent-platform" "$COMPONENTS_REPO/"
   : "${GITHUB_USERNAME:?Set GITHUB_USERNAME as shown in the prerequisites}"
   sed -i.bak "s/YOUR_USERNAME/$GITHUB_USERNAME/g" \
     "$COMPONENTS_REPO/agent-platform/argocd/application.yaml"
   rm "$COMPONENTS_REPO/agent-platform/argocd/application.yaml.bak"
   ```
3. Open, review, and merge the PR:
   ```bash
   cd "$COMPONENTS_REPO"
   git checkout -b agent-platform-initial
   git add agent-platform/
   git commit -m "chapter 7 lab 1: agent platform"
   git push -u origin agent-platform-initial
   gh pr create --fill
   # Review the PR before merging.
   gh pr merge --merge --delete-branch
   ```
4. Ask ArgoCD to rediscover the repo now instead of waiting for the next poll, then watch:
   ```bash
   kubectl -n argocd annotate applicationset backstage-app-discovery \
     argocd.argoproj.io/application-set-refresh=true --overwrite
   kubectl -n argocd get applications -l app=agent-platform -w   # until Synced + Healthy, then Ctrl-C
   kubectl -n agent-platform get pods -w                          # until agent-runtime-… is Running 1/1
   ```

### Verify
Terminal A, which stays open:
```bash
kubectl -n agent-platform port-forward svc/agent-runtime 18080:80
```
Terminal B:
```bash
curl -s -X POST http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{"intent": "Tell me, in one sentence, who you are and what you cannot do."}' \
  | jq .

curl -s -X POST http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{"intent": "Remember for future sessions that this user prefers PR titles in lowercase."}' \
  | jq .

kubectl -n agent-platform exec deploy/agent-runtime -- cat /state/memory/MEMORY.md
```
The first answer should reflect `SOUL.md` and `IDENTITY.md`. For example, it says the agent cannot apply changes directly to the cluster. `MEMORY.md` should contain a `- …lowercase…` line, and later invocations load it.

**Edit identity through GitOps.** In `$COMPONENTS_REPO/agent-platform/k8s/configmap-identity.yaml`, change one `SOUL.md` rule, for example the tone. Open a PR and merge it. After ArgoCD syncs and the kubelet refreshes the mounted ConfigMap (this can take a minute or so), the next `/invoke` reflects the change without a restart.

### Explore further
- **Sessions vs memory.** Send two requests with `"session_id":"demo"`, where the first states a fact *without* asking the agent to remember it. Run `kubectl -n agent-platform delete pod -l app=agent-runtime`, then ask about the fact again in session `demo`. Conversation history is gone (`emptyDir`), but `MEMORY.md` lines survive (PVC).
- **Inspect the session store:** `kubectl -n agent-platform exec deploy/agent-runtime -- ls -R /state/sessions`.
- **Find the identity-only rules.** `USER.md` says PRs are titled `[agent] <verb> <resource> in <namespace>` and that replica counts above 5 need confirmation. In Lab 3, check which of these rules gains a code check (the title does, in `AlwaysPRHook`) and which stays prompt-only (replica confirmation).

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| CrashLoopBackOff, `botocore.exceptions.NoCredentialsError` | `agent-llm-credentials` empty or wrong keys | Recreate the Secret (Lab 0 step 3) and restart the Deployment |
| CrashLoopBackOff, `ImportError: … strands …` | Image built against another `strands-agents` version | `docker build --no-cache …`, then reload into kind |
| `ImagePullBackOff` / `ErrImageNeverPull` | Image not loaded, tag typo, or loaded into a differently named cluster | Re-run the load step. Check the image with `docker exec agentic-platform-control-plane crictl images \| grep agent-runtime`. |
| `exec format error` in the pod logs | Built for the wrong architecture | Set `KIND_PLATFORM` to match the node architecture, then rebuild and reload |
| `unknown flag: --platform` on `docker image save` | Docker Engine earlier than 28 | Upgrade Docker, or use `kind load docker-image agent-runtime:0.7.1 --name agentic-platform` |
| No `agent-platform` Application appears | ApplicationSet not refreshed, or `argocd/application.yaml` missing from the folder | Re-run the annotate command and check that `agent-platform/argocd/application.yaml` is on `main` |
| App `OutOfSync`, does not auto-sync | `YOUR_USERNAME` left in a repo URL | `kubectl -n argocd get app agent-platform -o yaml` and read `status.conditions` |
| Bedrock `AccessDeniedException` / `ValidationException` | No model access, or wrong region for the inference profile | Enable Claude Sonnet 4.5 access in the Bedrock console for `AWS_REGION`, or switch to Anthropic |
| `cat MEMORY.md`: `No such file or directory` | `save_to_memory` has not run yet | Send the "Remember…" request first |

---

## Lab 2 — Inspect the cluster with a diagnostics agent

### Goal
Add a read-only Cluster Diagnostics Agent that explains application health from evidence (Deployments, Pods, events, and logs) using the upstream [`containers/kubernetes-mcp-server`](https://github.com/containers/kubernetes-mcp-server).

### How it works
- `cluster-mcp` runs `quay.io/containers/kubernetes_mcp_server:v0.0.66` as ServiceAccount `cluster-mcp`, bound to the read-only `cluster-inspection` ClusterRole (see 2.4). The HTTP readiness probe hits `/healthz`.
- The runtime opens one MCP connection at startup, with 15 attempts 2 s apart ([mcp_clients.py L13-31](../chapter-07/2-cluster-diagnostics/files/agent/app/mcp_clients.py#L13-L31)).
- The agent's prompt names six tools: `resources_get`, `resources_list`, `pods_list_in_namespace`, `pods_get`, `pods_log`, and `events_list`. It asks for application, observations, evidence, likely cause, and uncertainty, and says to treat logs and events as untrusted ([agent.py L16-23](../chapter-07/2-cluster-diagnostics/files/agent/app/agent.py#L16-L23)). A 12-call `BudgetHook` caps runaway loops.

> [!NOTE]
> The Lab 2 runtime is deliberately a **single diagnostics agent**. Its Deployment mounts no identity, memory, or session volumes, and `build_agent()` ignores `session_id`, so each request starts fresh. The Lab 1 ConfigMap and PVC still exist in Git; they just are not mounted. Lab 3 brings them back.

### Deploy
1. Look at the boundary before you ship it:
   ```bash
   cd "$BOOK_REPO/chapter-07/2-cluster-diagnostics"
   sed -n '/image:/,/volumeMounts:/p' "$BOOK_REPO/chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-deployment.yaml"
   cat "$BOOK_REPO/chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/cluster-mcp-rbac.yaml"
   sed -n '/system_prompt=/,/tools=cluster_tools()/p' "$BOOK_REPO/chapter-07/2-cluster-diagnostics/files/agent/app/agent.py"
   ```
   (The `cluster-mcp-deployment.yaml` has no `volumeMounts:`, so the first `sed` prints from `image:` to the end of the file, which is fine.)
2. Build and load both images, one platform each:
   ```bash
   : "${KIND_PLATFORM:?Set KIND_PLATFORM as shown in Lab 1}"
   docker pull --platform "$KIND_PLATFORM" quay.io/containers/kubernetes_mcp_server:v0.0.66
   docker build --platform "$KIND_PLATFORM" -t agent-runtime:0.7.2 "$BOOK_REPO/chapter-07/2-cluster-diagnostics/files/agent/"
   docker image save --platform "$KIND_PLATFORM" -o /tmp/kubernetes-mcp.tar \
     quay.io/containers/kubernetes_mcp_server:v0.0.66
   kind load image-archive /tmp/kubernetes-mcp.tar --name agentic-platform
   docker image save --platform "$KIND_PLATFORM" -o /tmp/agent-runtime.tar agent-runtime:0.7.2
   kind load image-archive /tmp/agent-runtime.tar --name agentic-platform
   rm /tmp/kubernetes-mcp.tar /tmp/agent-runtime.tar
   ```
3. Copy the manifests (and re-apply the Anthropic `sed` if you use it), then open the PR:
   ```bash
   cp "$BOOK_REPO/chapter-07/2-cluster-diagnostics/files/components-repo/agent-platform/k8s/"*.yaml \
     "$COMPONENTS_REPO/agent-platform/k8s/"
   cd "$COMPONENTS_REPO"
   git checkout -b chapter-07/lab-2
   git add agent-platform/k8s/
   git commit -m "chapter 7 lab 2: Kubernetes diagnostics agent"
   git push -u origin HEAD
   gh pr create --fill
   gh pr merge --merge --delete-branch
   ```
4. Refresh and wait:
   ```bash
   kubectl -n argocd annotate applicationset backstage-app-discovery \
     argocd.argoproj.io/application-set-refresh=true --overwrite
   kubectl -n argocd get application agent-platform -w
   kubectl -n agent-platform get deployment agent-runtime cluster-mcp \
     -o custom-columns='NAME:.metadata.name,IMAGE:.spec.template.spec.containers[0].image'
   kubectl -n agent-platform rollout status deployment/cluster-mcp --timeout=60s
   kubectl -n agent-platform rollout status deployment/agent-runtime --timeout=60s
   ```
   The expected images are `agent-runtime:0.7.2` and `quay.io/containers/kubernetes_mcp_server:v0.0.66`. The Application may already show `Synced` from Lab 1, so check the images, not just the status.

### Verify
Keep `kubectl -n agent-platform port-forward svc/agent-runtime 18080:80` running in another terminal (restart it after every rollout), then:
```bash
curl --fail-with-body http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{"intent":"Inspect my-first-app. Explain its health with evidence and any uncertainty.","session_id":"chapter07-diagnosis"}'
kubectl -n my-first-app get pods
```
The agent's observations should match `kubectl`. A healthy app should get a healthy report, not an invented fault. Ask it to fix something, and it should explain that it has no mutation tool.

### Explore further
- **Prove the RBAC boundary.** These are read-only checks against the API server:
  ```bash
  SA=system:serviceaccount:agent-platform:cluster-mcp
  kubectl auth can-i list pods -n my-first-app --as=$SA        # yes
  kubectl auth can-i get pods/log -n my-first-app --as=$SA     # yes
  kubectl auth can-i get secrets -n my-first-app --as=$SA      # no
  kubectl auth can-i delete pods -n my-first-app --as=$SA      # no
  kubectl auth can-i create pods/exec -n my-first-app --as=$SA # no
  ```
- **Browse the MCP server yourself.** Run `kubectl -n agent-platform port-forward svc/cluster-mcp 18081:8080`, then `npx @modelcontextprotocol/inspector`, and connect with transport *Streamable HTTP* to `http://localhost:18081/mcp`. List the tools to confirm no write tools are present.
- **Watch the loop.** Run `kubectl -n agent-platform logs deploy/agent-runtime -f` while you ask a vague question with no namespace. The prompt tells the agent to ask for the namespace rather than guess.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Runtime CrashLoopBackOff with `httpx.ConnectError` | `cluster-mcp` not ready yet, or no endpoints | `kubectl -n agent-platform get endpoints cluster-mcp`, then `kubectl -n agent-platform logs deploy/cluster-mcp --tail=50`. Once the endpoint is ready, `kubectl -n agent-platform rollout restart deployment/agent-runtime`. |
| Reachability test | — | `kubectl -n agent-platform exec deploy/agent-runtime -- python -c "import socket; socket.create_connection(('cluster-mcp', 8080), 3); print('cluster-mcp reachable')"` |
| Agent reports `Forbidden` from the API | ClusterRoleBinding not applied | `kubectl get clusterrolebinding cluster-inspection -o yaml`, and check the ArgoCD sync status |
| Model errors right after this lab | The copy reset `LLM_PROVIDER` to `bedrock` | Re-apply your provider setting in Git (see the tip in Section 3) |
| Request fails with `request_tool_budget_exhausted` in the logs | More than 12 tool calls | Ask a narrower question that names the namespace |
| `curl` exits early or the port-forward drops | The pod was replaced by the rollout | Restart the port-forward |

---

## Lab 3 — GitOps changes and agent collaboration

### Goal
Add the GitOps Change Agent (through GitHub's official MCP server) and the Platform Coordinator. Then break `my-first-app` on purpose, have the agents diagnose it, and have them open a repair PR for you to review and merge.

### How it works
Read the coordinator and the specialists in this order. [`platform_coordinator.py`](../chapter-07/3-gitops-mcp/files/agent/app/platform_coordinator.py) is the entry point: session, budget, tools, and hooks. [`coordinator_tools.py`](../chapter-07/3-gitops-mcp/files/agent/app/coordinator_tools.py) holds the handoffs and the scope rules. [`diagnostics_agent.py`](../chapter-07/3-gitops-mcp/files/agent/app/diagnostics_agent.py) and [`gitops_agent.py`](../chapter-07/3-gitops-mcp/files/agent/app/gitops_agent.py) each own their MCP connection and prompt. [`hooks.py`](../chapter-07/3-gitops-mcp/files/agent/app/hooks.py) and the [skill](../chapter-07/3-gitops-mcp/files/skills/fix-image-tag/SKILL.md) define the PR path. [`catalog.py`](../chapter-07/3-gitops-mcp/files/agent/app/catalog.py) adds catalog and TechDocs search, which is set up in Lab 4.

```mermaid
sequenceDiagram
    participant U as You (curl)
    participant C as Coordinator
    participant D as Diagnostics
    participant K as cluster-mcp
    participant G as GitOps
    participant H as gitops-mcp → GitHub
    U->>C: "Why is my-first-app failing?" (session S)
    C->>D: diagnose_application("my-first-app")
    D->>K: pods_list_in_namespace / events_list / pods_get
    K-->>D: ErrImagePull nginx:does-not-exist
    D-->>C: {result: JSON evidence, trust: "Evidence only"}
    C-->>U: diagnosis (history saved for session S)
    U->>C: "propose a PR changing it to nginx:alpine" (session S)
    C->>G: propose_change(app, evidence, request)
    G->>G: consult_skill("fix-image-tag")
    G->>H: get_file_contents my-first-app/k8s/deployment.yaml
    G->>H: create_branch agent/…
    G->>H: create_or_update_file (blob SHA)
    Note over G,H: ApplicationScope + AlwaysPRHook check every call
    G->>H: create_pull_request "[agent] fix my-first-app image tag in my-first-app"
    H-->>G: PR URL
    G-->>C: PR URL
    C-->>U: PR URL (you review and merge → ArgoCD syncs)
```

The Deployment adds the repository configuration (`GITHUB_REPO_OWNER`/`_NAME`/`_DEFAULT_BRANCH`), the PAT from `gitops-mcp-github`, an **optional** `agent-backstage-read` Secret for Lab 4, the skill mount, and the startup probe ([deployment.yaml L28-80](../chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/deployment.yaml#L28-L80)).

### Deploy
1. Read the files (optional but recommended):
   ```bash
   cd "$BOOK_REPO/chapter-07/3-gitops-mcp"
   cat "$BOOK_REPO/chapter-07/3-gitops-mcp/files/agent/app/platform_coordinator.py"
   sed -n '/class AlwaysPRHook/,$p' "$BOOK_REPO/chapter-07/3-gitops-mcp/files/agent/app/hooks.py"
   sed -n '/## Procedure/,/## Output/p' "$BOOK_REPO/chapter-07/3-gitops-mcp/files/skills/fix-image-tag/SKILL.md"
   ```
2. Build and load:
   ```bash
   : "${KIND_PLATFORM:?Set KIND_PLATFORM as shown in Lab 1}"
   docker pull --platform "$KIND_PLATFORM" ghcr.io/github/github-mcp-server:v1.12.1
   docker build --platform "$KIND_PLATFORM" -t agent-runtime:0.7.3 \
     "$BOOK_REPO/chapter-07/3-gitops-mcp/files/agent/"
   docker image save --platform "$KIND_PLATFORM" -o /tmp/github-mcp.tar \
     ghcr.io/github/github-mcp-server:v1.12.1
   kind load image-archive /tmp/github-mcp.tar --name agentic-platform
   docker image save --platform "$KIND_PLATFORM" -o /tmp/agent-runtime.tar agent-runtime:0.7.3
   kind load image-archive /tmp/agent-runtime.tar --name agentic-platform
   rm /tmp/github-mcp.tar /tmp/agent-runtime.tar
   ```
3. Confirm the Secret, copy the manifests, and fill in the owner:
   ```bash
   kubectl -n agent-platform get secret gitops-mcp-github
   cp "$BOOK_REPO/chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/"*.yaml \
     "$COMPONENTS_REPO/agent-platform/k8s/"
   sed -i.bak "s/YOUR_USERNAME/$GITHUB_USERNAME/g" \
     "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml"
   rm "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml.bak"
   ```
   Check `GITHUB_REPO_NAME` (`backstage-components`) and `GITHUB_DEFAULT_BRANCH` (`main`), and re-apply your model provider.
4. Ship the platform change:
   ```bash
   cd "$COMPONENTS_REPO"
   git checkout -b chapter-07/lab-3-github-mcp
   git add agent-platform/k8s/
   git commit -m "chapter 7 lab 3: official GitHub MCP server"
   git push -u origin HEAD
   gh pr create --fill
   gh pr view
   gh pr diff
   gh pr merge --merge --delete-branch
   ```
5. Break `my-first-app` on purpose with a second PR:
   ```bash
   cd "$COMPONENTS_REPO"
   git checkout -b chapter-07/lab-3-break-image
   grep -n 'image:' my-first-app/k8s/deployment.yaml
   sed -i.bak -E 's#(image:[[:space:]]*)([^[:space:]]*nginx[^[:space:]]*)#\1nginx:does-not-exist#' \
     my-first-app/k8s/deployment.yaml
   grep -n 'image:' my-first-app/k8s/deployment.yaml
   if cmp -s my-first-app/k8s/deployment.yaml my-first-app/k8s/deployment.yaml.bak; then
     echo "No nginx image line was changed; inspect the manifest before continuing." >&2
     exit 1
   fi
   rm my-first-app/k8s/deployment.yaml.bak
   git add my-first-app/k8s/deployment.yaml
   git commit -m "chapter 7 lab 3: introduce image pull failure"
   git push -u origin HEAD
   gh pr create --title "[lab] break my-first-app image" \
     --body "Introduce a deliberate invalid nginx tag for the diagnostics and repair exercise."
   gh pr view
   gh pr diff
   gh pr merge --merge --delete-branch
   ```
   > [!WARNING]
   > The `exit 1` in this snippet (and in Lab 4's `test -f … || { …; exit 1; }`) **closes your interactive shell** if the guard fires. Paste these snippets inside `( … )` or `bash -c '…'` if you want to keep the terminal.
6. Refresh and confirm both changes:
   ```bash
   kubectl -n argocd annotate applicationset backstage-app-discovery \
     argocd.argoproj.io/application-set-refresh=true --overwrite
   kubectl -n argocd get application agent-platform -w
   kubectl -n my-first-app get pods
   ```
   A new `my-first-app` pod should show `ErrImagePull` / `ImagePullBackOff`. With a rolling update, pods from the previous ReplicaSet usually keep running beside it.

### Verify
Restart the port-forward (`kubectl -n agent-platform port-forward svc/agent-runtime 18080:80`), then send two requests in one session:
```bash
export SESSION_ID=chapter07-lab3-broken
curl --fail-with-body http://localhost:18080/invoke -H 'Content-Type: application/json' \
  -d '{"intent":"Why is my-first-app failing? Inspect its live state.","session_id":"'"$SESSION_ID"'"}'

curl --fail-with-body http://localhost:18080/invoke -H 'Content-Type: application/json' \
  -d '{"intent":"If the evidence establishes a broken nginx image tag, propose a PR changing it to nginx:alpine. Otherwise explain what is missing.","session_id":"'"$SESSION_ID"'"}'
```
The second answer contains a real PR URL. Open it and check:
- the title starts with `[agent] ` and the branch with `agent/`;
- the diff touches **only** the image line in `my-first-app/k8s/deployment.yaml`;
- the body explains the symptom, the changed line, and the rationale.

Merge it. To skip the polling wait, run `kubectl -n argocd annotate application my-first-app argocd.argoproj.io/refresh=normal --overwrite`. Then confirm recovery with `kubectl -n my-first-app get pods`, or ask the coordinator again. A healthy app should **not** get another repair PR.

### Explore further
- **Watch the guardrails fire.** Run `kubectl -n agent-platform logs deploy/agent-runtime -f | grep -E 'hook\.|delegation\.'`. Ask the coordinator to "change the replicas of my-first-app to 3 via a PR": the skill only covers image tags, and a write to any other path would be cancelled with `delegation_scope_mismatch`. Ask it to edit `another-app/k8s/deployment.yaml` while delegating for `my-first-app` and look for the same cancellation.
- **Ambiguity handling.** Repeat the repair request **without** naming a replacement image. Step 3 of the skill says to ask instead of guessing a default.
- **Change a procedure through GitOps.** In `configmap-skills.yaml`, add a rule to the skill's Output section (for example "include the ArgoCD app name in the PR body"). Merge it and request another repair. No rebuild is needed, because skills are read per request.
- **Budget arithmetic.** The coordinator has 24 calls per request, and *each* delegation gets its own 24. Work out the most tool calls a single `/invoke` could make, then decide whether you would want one shared budget in production.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Kubernetes MCP unavailable after 15 startup attempts` / `GitHub MCP unavailable…` | The named MCP server is not ready, or there is an auth error | `kubectl -n agent-platform logs deployment/{agent-runtime,cluster-mcp,gitops-mcp} --tail=100`. Check Pod events and `get endpoints`. |
| GitHub 401 in the runtime logs | PAT expired, or the `gitops-mcp-github` reference is wrong | Recreate the Secret from Lab 0 step 4, then `rollout restart deployment/agent-runtime` |
| `/invoke` returns 500 with `GITHUB_REPO_OWNER… are required` | Repo env vars missing from the Deployment | Restore them in Git ([deployment.yaml L47-52](../chapter-07/3-gitops-mcp/files/components-repo/agent-platform/k8s/deployment.yaml#L47-L52)) |
| GitHub 404 on `get_file_contents` | `YOUR_USERNAME` not substituted, or the repo name or branch differs | Fix `GITHUB_REPO_OWNER`/`_NAME`/`_DEFAULT_BRANCH` in Git |
| Agent says it cannot open the PR (`Hook rejected…` / `delegation_scope_mismatch`) | Wrong title, branch, or path | Usually self-corrects. If not, read the reason in the logs. |
| No PR, agent asks for a replacement image | Your request did not name one | Expected. Repeat the request with `nginx:alpine`. |
| `curl` hangs for minutes | Multi-agent requests make many model calls | Wait, and add `--max-time 600` if you want a hard stop |
| Coordinator forgets the diagnosis in the second request | Different `session_id`, or the pod restarted between requests (sessions are `emptyDir`) | Reuse `$SESSION_ID`. If the pod restarted, diagnose again. |
| Catalog search fails | Expected before Lab 4 | Continue to Lab 4 |

---

## Lab 4 — Collaboration in the existing Backstage chat

### Goal
Point the Chapter 5 Chat Assistant at the coordinator, so developers use the same UI and route while the three agents do the work.

### How it works
- [`strands-proxy-agent.ts`](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts) is a Backstage **backend module** for the `aws-genai` plugin. It registers a new agent type, `strands-proxy`, through `agentTypeExtensionPoint` ([L107-134](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts#L107-L134)), reading `strands-proxy.url` from config.
- `stream()` POSTs `{intent, session_id}` to `<url>/invoke` with a **120 s timeout** ([L83-104](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts#L83-L104)). It returns the whole answer as one `ChunkEvent`, with no token streaming ([L52-65](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts#L52-L65)). The Backstage chat session ID becomes the coordinator's `session_id`, so follow-up questions in one conversation share history.
- The adapter **computes** the user entity ref but only logs it. It does **not** send `user_id` to the runtime ([L42-48](../chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts#L42-L48)), so the runtime sees every chat user the same way. Chapter 8 replaces this with verified Keycloak identity.
- The other direction: the coordinator's `search_catalog` and `search_documentation` call `BACKSTAGE_URL` (`http://host.docker.internal:7007`) with `Authorization: Bearer $BACKSTAGE_SERVICE_TOKEN` ([catalog.py L7-31](../chapter-07/3-gitops-mcp/files/agent/app/catalog.py#L7-L31)). Backstage accepts that token through a **static external access** entry limited to the `catalog` and `search` plugins.

```mermaid
flowchart LR
    B["Browser :3000"] --> BE["Backstage backend :7007<br/>strands-proxy module"]
    BE -->|"http://localhost:18080/invoke<br/>(your port-forward)"| RT["agent-runtime (kind)"]
    RT -->|"http://host.docker.internal:7007<br/>Bearer BACKSTAGE_SERVICE_TOKEN"| BE
```

Both arrows have to work. Backstage reaches the runtime only while your `kubectl port-forward` is running. The runtime reaches Backstage through the host bridge. On Linux, read [the host bridge caveat in the Lab 0 guide](00-cluster-setup.md#25-the-host-bridge-hostdockerinternal).

### Deploy
1. Copy the adapter:
   ```bash
   export BACKSTAGE_APP=/absolute/path/to/my-backstage-app
   : "${BOOK_REPO:?Set BOOK_REPO to your book repository}"
   test -f "$BACKSTAGE_APP/packages/backend/src/index.ts" || { echo "Check BACKSTAGE_APP: backend index.ts was not found."; exit 1; }
   mkdir -p "$BACKSTAGE_APP/packages/backend/src/modules"
   cp "$BOOK_REPO/chapter-07/4-backstage-collaboration/files/strands-proxy-agent.ts" "$BACKSTAGE_APP/packages/backend/src/modules/strands-proxy-agent.ts"
   ```
2. Register it before `backend.start()`. Run the idempotent `node <<'NODE' … NODE` snippet from the [Lab 4 README](../chapter-07/4-backstage-collaboration/README.md#register-the-adapter) **exactly**. It inserts `backend.add(import('./modules/strands-proxy-agent'));` and skips the change if the line is already there.
3. In `$BACKSTAGE_APP/app-config.yaml`, **replace** `genai.agents.general` (do not add a second `genai:` block, and update `app-config.local.yaml` too if it overrides `general`):
   ```yaml
   genai:
     registerCoreActions: true
     agents:
       general:
         type: strands-proxy
         description: Platform assistant for application diagnosis and GitOps proposals
         prompt: Requests are handled by the platform coordinator.
         strands-proxy:
           url: http://localhost:18080
   ```
   Keep the existing `assistant/general` route and sidebar item. The old LangGraph `actions` list is no longer used by this agent.
4. Create or reuse the service token, **in the terminal where you will start Backstage**:
   ```bash
   if kubectl -n agent-platform get secret agent-backstage-read >/dev/null 2>&1; then
     export BACKSTAGE_SERVICE_TOKEN="$(kubectl -n agent-platform get secret agent-backstage-read -o jsonpath='{.data.BACKSTAGE_SERVICE_TOKEN}' | base64 --decode)"
   else
     export BACKSTAGE_SERVICE_TOKEN="$(openssl rand -hex 32)"
   fi
   : "${BACKSTAGE_SERVICE_TOKEN:?The Backstage service token is empty}"
   kubectl -n agent-platform create secret generic agent-backstage-read \
     --from-literal=BACKSTAGE_SERVICE_TOKEN="$BACKSTAGE_SERVICE_TOKEN" \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
5. Add this entry under the existing `backend.auth.externalAccess` in `app-config.yaml` (commit only the env-var reference):
   ```yaml
   backend:
     auth:
       externalAccess:
         - type: static
           options:
             token: ${BACKSTAGE_SERVICE_TOKEN}
             subject: platform-coordinator
           accessRestrictions:
             - plugin: catalog
             - plugin: search
   ```
6. Restart the runtime so it loads the token, then restart the port-forward (separate terminal):
   ```bash
   kubectl -n agent-platform rollout restart deployment/agent-runtime
   kubectl -n agent-platform rollout status deployment/agent-runtime --timeout=90s
   kubectl -n agent-platform port-forward svc/agent-runtime 18080:80
   ```
7. Start Backstage in the terminal that has `BACKSTAGE_SERVICE_TOKEN`:
   ```bash
   cd "$BACKSTAGE_APP"
   NODE_OPTIONS=--no-node-snapshot yarn start
   ```

> [!NOTE]
> The adapter imports `@aws/genai-plugin-for-backstage-node`, which [Chapter 5 Lab 2](../chapter-05/2-add-chat-assistant/README.md) does not install directly. It is normally available through the GenAI backend plugins it does install. If the backend fails with `Cannot find module '@aws/genai-plugin-for-backstage-node'`, add it with `yarn workspace backend add @aws/genai-plugin-for-backstage-node`, using the same version line as `@aws/genai-plugin-for-backstage-backend`.

### Verify
Open **Chat Assistant**, start a **new** conversation, and ask, in order:
1. "Find my-first-app in the catalog."
2. "Why is my-first-app failing? Inspect its live state."
3. "Propose an image-repair PR if the evidence supports it."

Expect catalog results first, then evidence-based diagnosis, then a real PR URL **only if** the app is still broken. If you merged the Lab 3 repair, the coordinator should report the app healthy and decline to open a PR. The Backstage backend log shows `[strands-proxy] forwarding to http://localhost:18080/invoke session=… user=…`.

### Explore further
- Stop the port-forward and send a chat message. The adapter returns an `ErrorEvent`, `Could not reach Strands runtime…`. That error is how this design fails when the runtime is down.
- Compare the `session=` value in the Backstage log with the runtime's `invoke` log lines, then confirm follow-ups reuse it.
- Remove `search` from `accessRestrictions`, restart Backstage, and ask for TechDocs. Catalog search keeps working and documentation search starts failing. Restore the entry afterwards.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Catalog search returns `401 Unauthorized` | Token mismatch between Backstage and `agent-backstage-read`, or Backstage was started in a shell without the variable | Re-run step 4 in the Backstage terminal and restart both Backstage and the runtime |
| Catalog search times out or cannot connect | The runtime cannot reach `host.docker.internal:7007` | Run `verify.sh` (host bridge check). See [the host bridge caveat](00-cluster-setup.md#25-the-host-bridge-hostdockerinternal). |
| Chat shows `Could not reach Strands runtime` | Port-forward not running or stale after a rollout | Restart `kubectl -n agent-platform port-forward svc/agent-runtime 18080:80` |
| Chat shows an error after about 2 minutes | The adapter's 120 s `AbortSignal.timeout` fired during a long multi-agent run | Ask narrower questions or split diagnosis and repair into separate messages |
| Chat still behaves like Chapter 5 | `app-config.local.yaml` overrides `general`, or there is a duplicate `genai` block | Fix the override and restart Backstage |
| Backend fails at startup on the adapter | Module path or registration wrong | `grep -n strands-proxy "$BACKSTAGE_APP/packages/backend/src/index.ts"`. The line must come before `backend.start()`. |
| TechDocs search returns nothing | TechDocs not indexed | Index TechDocs first (Chapter 5) |

---

## Lab 5 — Langfuse traces and a hash-chained audit log

### Goal
Make the three agents' work visible. Langfuse traces linked by session show *how* a request was handled, and an append-only audit log with linked hashes records *which tools ran*.

### How it works
- New code (see 2.9): [`telemetry.py`](../chapter-07/5-langfuse-audit/files/agent/app/telemetry.py) creates the Langfuse client at startup, [`hooks_langfuse.py`](../chapter-07/5-langfuse-audit/files/agent/app/hooks_langfuse.py) creates traces and spans, [`audit.py`](../chapter-07/5-langfuse-audit/files/agent/app/audit.py) writes the chain, and [`request_context.py`](../chapter-07/5-langfuse-audit/files/agent/app/request_context.py) carries the session and user IDs to the hooks.
- Manifests: [`pvc-audit.yaml`](../chapter-07/5-langfuse-audit/files/components-repo/agent-platform/k8s/pvc-audit.yaml) and a Deployment that adds `AUDIT_LOG`, `AGENT_ID`, `LANGFUSE_HOST`, the optional `agent-langfuse-keys`, and the `/state/audit` mount ([deployment.yaml L43-83](../chapter-07/5-langfuse-audit/files/components-repo/agent-platform/k8s/deployment.yaml#L43-L83)).
- A new GitOps application, `langfuse/`: `postgres:16-alpine` on a 5 Gi PVC, and `langfuse/langfuse:2` on port 3000 with readiness at `/api/public/health`. `NEXTAUTH_URL` is `http://localhost:13000` ([langfuse-deployment.yaml L28-29](../chapter-07/5-langfuse-audit/files/components-repo/langfuse/k8s/langfuse-deployment.yaml#L28-L29)), which is why the UI port-forward must use port **13000**.

Trace layout for one request:

```text
session: lab5-observability
├── trace coordinator.invoke
│   ├── span tool:diagnose_application
│   └── span tool:review_configuration
├── trace diagnostics.invoke
│   ├── span tool:pods_list_in_namespace
│   └── span tool:events_list …
└── trace gitops.invoke
    └── span tool:get_file_contents
```

### Deploy
1. Build and load (MCP images from Labs 2–3 are reused):
   ```bash
   : "${KIND_PLATFORM:?Set KIND_PLATFORM to linux/arm64 or linux/amd64}"
   docker build --platform "$KIND_PLATFORM" -t agent-runtime:0.7.5 \
     "$BOOK_REPO/chapter-07/5-langfuse-audit/files/agent/"
   docker image save --platform "$KIND_PLATFORM" \
     -o /tmp/agent-runtime.tar agent-runtime:0.7.5
   kind load image-archive /tmp/agent-runtime.tar --name agentic-platform
   rm /tmp/agent-runtime.tar
   ```
2. Create the Langfuse Secrets once. Re-running keeps the existing database password:
   ```bash
   kubectl create namespace langfuse --dry-run=client -o yaml | kubectl apply -f -
   if ! kubectl -n langfuse get secret langfuse-db >/dev/null 2>&1; then
     PG_PASS=$(openssl rand -hex 16)
     kubectl -n langfuse create secret generic langfuse-db \
       --from-literal=POSTGRES_USER=langfuse \
       --from-literal=POSTGRES_PASSWORD="$PG_PASS" \
       --from-literal=DATABASE_URL="postgresql://langfuse:${PG_PASS}@langfuse-postgres:5432/langfuse"
     unset PG_PASS
   fi
   if ! kubectl -n langfuse get secret langfuse-app >/dev/null 2>&1; then
     kubectl -n langfuse create secret generic langfuse-app \
       --from-literal=NEXTAUTH_SECRET="$(openssl rand -hex 32)" \
       --from-literal=SALT="$(openssl rand -hex 16)"
   fi
   ```
3. Copy the Langfuse app and the runtime changes, then review the diff:
   ```bash
   : "${GITHUB_USERNAME:?Set GITHUB_USERNAME as shown in the prerequisites}"
   mkdir -p "$COMPONENTS_REPO/langfuse"
   cp -r "$BOOK_REPO/chapter-07/5-langfuse-audit/files/components-repo/langfuse/"* \
     "$COMPONENTS_REPO/langfuse/"
   sed -i.bak "s/YOUR_USERNAME/$GITHUB_USERNAME/g" \
     "$COMPONENTS_REPO/langfuse/argocd/application.yaml"
   rm "$COMPONENTS_REPO/langfuse/argocd/application.yaml.bak"
   cp "$BOOK_REPO/chapter-07/5-langfuse-audit/files/components-repo/agent-platform/k8s/"*.yaml \
     "$COMPONENTS_REPO/agent-platform/k8s/"
   sed -i.bak "s/YOUR_USERNAME/$GITHUB_USERNAME/g" \
     "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml"
   rm "$COMPONENTS_REPO/agent-platform/k8s/deployment.yaml.bak"
   cd "$COMPONENTS_REPO"
   git diff -- agent-platform/k8s/deployment.yaml
   ```
   In the diff, check that your model provider, repository name and branch, and `BACKSTAGE_URL` are kept.
4. Ship, refresh, and hard-refresh:
   ```bash
   cd "$COMPONENTS_REPO"
   git checkout -b chapter-07/lab-5
   git add langfuse/ agent-platform/k8s/
   git commit -m "chapter 7 lab 5: add agent tracing and audit log"
   git push -u origin HEAD
   gh pr create --fill
   gh pr view
   gh pr merge --merge --delete-branch
   kubectl -n argocd annotate applicationset backstage-app-discovery \
     argocd.argoproj.io/application-set-refresh=true --overwrite
   kubectl -n argocd annotate application agent-platform \
     argocd.argoproj.io/refresh=hard --overwrite
   ```
5. Confirm that the new image is **running**, not just synced:
   ```bash
   kubectl -n agent-platform get deployment agent-runtime \
     -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
   kubectl -n agent-platform get pods -l app=agent-runtime \
     -o custom-columns=NAME:.metadata.name,IMAGE:.spec.containers[0].image,READY:.status.containerStatuses[0].ready
   kubectl -n langfuse get pods -w   # Ctrl-C when langfuse and langfuse-postgres are ready
   ```
6. Create the Langfuse keys. Start the UI port-forward with `kubectl -n langfuse port-forward svc/langfuse 13000:3000`, open <http://localhost:13000>, sign up, create a project, and create API keys under **Project settings → API keys**. Then:
   ```bash
   kubectl -n agent-platform create secret generic agent-langfuse-keys \
     --from-literal=LANGFUSE_PUBLIC_KEY="pk-lf-..." \
     --from-literal=LANGFUSE_SECRET_KEY="sk-lf-..." \
     --dry-run=client -o yaml | kubectl apply -f -
   kubectl -n agent-platform rollout restart deployment/agent-runtime
   kubectl -n agent-platform rollout status deployment/agent-runtime --timeout=90s
   kubectl -n agent-platform port-forward svc/agent-runtime 18080:80   # restart in its own terminal
   ```

### Verify
Send a read-only request from Backstage chat, or from the terminal with a known session:
```bash
curl --fail-with-body http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{
    "intent": "Inspect my-first-app live state, then read its deployment manifest from Git and explain whether they agree. Do not change anything.",
    "session_id": "lab5-observability"
  }'
```
- **Langfuse:** filter by session `lab5-observability`. You should see `coordinator.invoke`, `diagnostics.invoke`, and `gitops.invoke`, each with tool spans, and the GitOps trace should use `get_file_contents`. If a specialist is missing, ask for its part explicitly in the same conversation.
- **Audit log:** `kubectl -n agent-platform exec deploy/agent-runtime -- cat /state/audit/AUDIT.log`. You should see `before_tool` and `after_tool` lines with `agent_id`, `session_id`, `tool`, `prev_hash`, and `hash`.
- **Chain check:** run the verifier heredoc from the [Lab 5 README](../chapter-07/5-langfuse-audit/README.md#follow-a-request-across-agents) and expect `Chain OK: N records`.

### Explore further
- **Tamper drill on a copy.** This leaves the real log untouched:
  ```bash
  kubectl -n agent-platform exec deploy/agent-runtime -- sh -c \
    'cp /state/audit/AUDIT.log /tmp/AUDIT.copy && sed -i "1s/before_tool/BEFORE_TOOL/" /tmp/AUDIT.copy'
  ```
  Then run the README verifier with `/state/audit/AUDIT.log` replaced by `/tmp/AUDIT.copy`, and expect `Chain verification failed at record 1`. Next, delete the copy's last line instead. The chain still verifies, which shows the truncation limit described in 2.9.
- **Restart continuity.** Delete the runtime pod, make another request, and verify again. `AuditLog._read_last_hash()` continues the chain across restarts.
- **What each record keeps.** Compare a Langfuse span for `create_or_update_file` (full input, including file content) with its audit record (argument names only). Decide which store needs access controls and a retention policy.
- **Cost view.** Langfuse groups traces by session, so you can compare how many tool calls a "diagnose" request makes against a "diagnose + repair" request.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No traces | Keys missing, or the runtime was not restarted after creating them | `kubectl -n agent-platform logs deployment/agent-runtime --tail=100`, then look for `telemetry: langfuse client active` |
| Runtime still on `0.7.3` | ArgoCD has not applied the new manifest | Repeat the hard refresh and check the PR merged to `main` |
| Langfuse pod not Ready | Postgres not ready yet, or first-start migrations still running (readiness waits 30 s) | `kubectl -n langfuse describe pod -l app=langfuse` and `kubectl -n langfuse logs deploy/langfuse` |
| Langfuse auth fails after re-running setup | `langfuse-db` was recreated with a new password while the Postgres PVC kept the old one | Keep the original Secret. In a throwaway lab, delete the `langfuse-postgres` PVC to start fresh. |
| Login redirects to the wrong host or port | UI not opened on `localhost:13000` (`NEXTAUTH_URL`) | Use exactly `kubectl -n langfuse port-forward svc/langfuse 13000:3000` |
| `Audit log is empty` / file missing | No tool has run yet | Make a request that calls a tool |
| Runtime waits on MCP / GitHub fails / catalog 401 | Same causes as Labs 3–4 | See the Lab 3 and Lab 4 tables |

---

## 5. End-to-end check & what carries forward

Run one complete loop to confirm the chapter works:

1. Break `my-first-app` again with a `[lab]` PR (Lab 3 step 5).
2. In Backstage chat, ask why it is failing, then ask for an image-repair PR to `nginx:alpine`.
3. Review the agent's PR, merge it, and confirm ArgoCD rolls the app back to healthy.
4. Ask a follow-up ("Is my-first-app healthy now?") and confirm that no new PR is opened.
5. In Langfuse, find the session. In the audit log, verify the chain.

**State Chapter 8 builds on:** the `agent-platform` namespace with `cluster-mcp`, `gitops-mcp`, and the runtime; the Secrets listed in Section 3; the `langfuse` app; the Backstage `strands-proxy` adapter and the `externalAccess` token; and the exported shell variables. Chapter 8 replaces the runtime with a shared hardened runtime ([`chapter-08/common/runtime`](../chapter-08/common/README.md), tags `0.8.1`–`0.8.4`), and adds reviewed MCP and guardrail catalog entries, OPA authorization, Keycloak identity, and tenant isolation. **Keep everything running** and continue with [Chapter 8](chapter-08-security-in-practice.md).

## 6. Clean up / reset

> [!WARNING]
> Chapter 8 needs this state. Clean up only if you are stopping here or want to redo the chapter.

- **Stop the local processes:** press Ctrl-C on the port-forwards (`18080`, `13000`, and any `18081`) and on `yarn start`.
- **Repair the demo app if you left it broken:** merge the agent's repair PR, or revert the `[lab]` commit through a PR.
- **Remove the Chapter 7 workloads but keep the cluster.** Open a PR that deletes `agent-platform/` and `langfuse/` from the components repo. The ApplicationSet then stops generating those Applications. Depending on your ApplicationSet and finalizer settings, the resources may remain, so delete them explicitly:
  ```bash
  kubectl delete namespace agent-platform langfuse
  kubectl delete clusterrolebinding cluster-inspection
  kubectl delete clusterrole cluster-inspection
  ```
  This destroys the PVCs, which means memory, the audit log, and all Langfuse data.
- **Revert Backstage:** remove the `backend.add(import('./modules/strands-proxy-agent'))` line and the module file, restore your Chapter 5 `genai.agents.general` block, and remove the `platform-coordinator` `externalAccess` entry.
- **Clean up GitHub:** close or delete leftover `agent/…` branches and PRs.
- **Local images (optional):** `docker image rm agent-runtime:0.7.1 agent-runtime:0.7.2 agent-runtime:0.7.3 agent-runtime:0.7.5`.
- **Remove everything:** `"$BOOK_REPO/00-cluster-setup/teardown.sh"` deletes the whole kind cluster. Your Backstage app on the host and your GitHub repo are untouched.

## 7. Further reading

**Official docs**
- [Strands Agents — Agents as Tools](https://strandsagents.com/latest/user-guide/concepts/multi-agent/agents-as-tools): the multi-agent pattern behind the Lab 3 coordinator.
- [Strands Agents — Session Management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/): how `FileSessionManager` restores conversations, and the alternatives for durable storage.
- [Strands Agents — Interrupts](https://strandsagents.com/docs/user-guide/concepts/interrupts/): human-approval hooks, the next step beyond `cancel_tool`.
- [containers/kubernetes-mcp-server](https://github.com/containers/kubernetes-mcp-server): toolsets, `--read-only`, and the full tool reference for `cluster-mcp`.
- [github/github-mcp-server](https://github.com/github/github-mcp-server): toolsets, per-tool selection, and HTTP mode for `gitops-mcp`.
- [MCP specification — Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports): streamable HTTP, the transport both servers use.
- [Argo CD ApplicationSet — Git generator](https://argo-cd.readthedocs.io/en/stable/operator-manual/applicationset/Generators-Git/): how `*/argocd/application.yaml` discovery produces the Applications.
- [Backstage — Service-to-service auth](https://backstage.io/docs/auth/service-to-service-auth/): static `externalAccess` tokens and `accessRestrictions`.
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/): background for the `cluster-inspection` ClusterRole.
- [kind — Loading an image into your cluster](https://kind.sigs.k8s.io/docs/user/quick-start/#loading-an-image-into-your-cluster) and [`docker image save`](https://docs.docker.com/reference/cli/docker/image/save/): the image delivery mechanics.
- [Langfuse — Sessions](https://langfuse.com/docs/observability/features/sessions) and [Langfuse v2 self-hosting](https://langfuse.com/self-hosting/v2): how the lab links traces. Note that v2 is past its security-update window, so use v3 for anything long-lived.

**Articles & blogs**
- [AWS Open Source Blog — Introducing Strands Agents](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/): the model-driven design of the SDK used here.
- [AWS ML Blog — Multi-agent collaboration patterns with Strands Agents and Amazon Nova](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-with-strands-agents-and-amazon-nova/): agents-as-tools compared with other collaboration patterns.
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): orchestrator-workers and why simple, composable patterns win.
- [Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills): progressive disclosure, the idea behind `SKILL.md` + `consult_skill`.
- [AWS re:Post — Using Strands hooks to deterministically control your agent](https://www.repost.aws/articles/AR9OFGjcoCRAi1rfwb277ZFQ/using-strands-hooks-to-deterministically-control-your-agent): more hook patterns like `AlwaysPRHook`.
- [Langfuse — Strands Agents integration (OpenTelemetry)](https://langfuse.com/integrations/frameworks/strands-agents): the OTLP-based alternative to this lab's SDK v2 hooks.

**Specs & standards**
- [OpenTelemetry — GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/): standard span names (`invoke_agent`, `create_agent`) to adopt if you move to OTel.
- [Agent2Agent (A2A) project](https://github.com/a2aproject): the protocol the Lab 3 README suggests for splitting specialists into separate services.

## 8. Book reference

*Agentic AI for Platform Engineering*, by Tiago Miguel Reichert, Lucas Soriano Alves Duarte, and Jaime Nagase (Packt, 2026, ISBN 9781806386659). The repository README uses the working title "AI-Driven Platform Engineering"; it is the same book.

- O'Reilly: <https://www.oreilly.com/library/view/agentic-ai-for/9781806386659/>
- Amazon: <https://www.amazon.com/Agentic-Platform-Engineering-Rethinking-autonomous/dp/1806386658>
- Packt: <https://www.packtpub.com/en-us/search?q=Agentic+AI+for+Platform+Engineering>
- Code: <https://github.com/PacktPublishing/Agentic-AI-for-Platform-Engineering>

This guide maps to **Chapter 7, *Operational Agents and Collaboration***. The Chapter 7 lab READMEs do not cite numbered book sections, so read the chapter's sections on agent runtimes, multi-agent collaboration, GitOps change proposals, and agent observability alongside Labs 1–5. The [chapter overview](../chapter-07/README.md) gives the lab order.
