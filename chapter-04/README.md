# Chapter 04: Driving Platform Intelligence with Organizational Knowledge

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

Chapter 4 is about a single idea: a model is only as good as the **context** you give it. This chapter turns that idea into running code. You'll take a pile of organizational knowledge — runbooks, postmortems, blueprints — and make it *consumable by AI* two different ways, then see exactly where each one wins.

Everything here runs on the same local **kind** cluster from [`00-cluster-setup`](../00-cluster-setup/README.md). No managed cloud services, no Kinesis, no OpenSearch — you build the whole thing on your laptop and watch it work.

> **Why local?** Earlier drafts pointed readers at a finished AWS reference architecture (Fluent Bit → Kinesis → Lambda → OpenSearch → Bedrock). It's a great production pattern, but you can't *build it as you read*. This chapter builds the same concepts — RAG and MCP over platform knowledge — from scratch, locally. The AWS architecture remains the production-scale reference; this is the version you can run tonight.

## The two techniques, side by side

| | **RAG** (Lab 2) | **MCP** (Lab 3) |
|---|---|---|
| Answers | "What usually happens / how was it solved before?" | "What is true right now?" |
| Source | A corpus of durable docs, embedded into a vector store | A live system, queried on demand |
| Freshness | As fresh as your last ingest | Always current |
| Best for | Runbooks, postmortems, standards, design wisdom | Deployments in progress, cluster health, live signals |

The chapter's punchline — *RAG for accumulated wisdom, MCP for live system truth* — is something you'll feel directly: in Lab 2 you ask "why does a pod end up in CrashLoopBackOff?" and get an answer grounded in your runbooks; in Lab 3 you ask "which deployments are unhealthy *right now*?" and get the answer from the live cluster.

## Labs

| Lab | What you build | Chapter section |
|---|---|---|
| **0 — Prerequisites** | Cluster + Python + (optional) LLM credentials | — |
| **1 — Knowledge corpus** | A small, *structured* body of organizational knowledge: runbooks, a postmortem, platform blueprints | §4.4–4.8 (Organizational Knowledge Systems) |
| **2 — Local RAG pipeline** | Postgres + pgvector in-cluster, an ingestion step that embeds the corpus, and a retrieval+generation API that answers platform questions grounded in it | §4.9 (Implementing RAG Systems) |
| **3 — MCP server** | A `list_deployments` MCP server (the §4.10 example, made real) that queries the live cluster — RAG vs MCP, demonstrated | §4.10 (Why MCP matters) |

## Defaults

- **Cluster:** the shared kind cluster from [`00-cluster-setup`](../00-cluster-setup/README.md). ArgoCD is **not** required for this chapter — `SKIP_ARGOCD=1 ./setup-cluster.sh` is enough. (GitOps deployment is introduced in Chapter 5.)
- **Embeddings:** a small local model via [`fastembed`](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`, runs on CPU, no cloud credentials). Amazon Titan embeddings are a documented option.
- **Generation LLM:** Amazon Bedrock with Claude by default; Anthropic API direct as a fallback — the same pattern Chapter 7 uses.

Override any of these via environment variables documented in each lab's README.

## Start here

```bash
cd 0-prereqs
```
