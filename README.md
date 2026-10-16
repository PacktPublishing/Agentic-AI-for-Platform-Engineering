# AI-Driven Platform Engineering — Code

Companion code for the book *AI-Driven Platform Engineering*. The labs build a local platform on one shared [kind](https://kind.sigs.k8s.io/) cluster, then extend it with organizational context, Backstage, collaborating agents, and enforceable security. Amazon EKS can replace kind; model-backed labs require credentials for a documented LLM provider.

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

## Start here

```bash
cd 00-cluster-setup
./setup-cluster.sh   # kind cluster 'agentic-platform' + Metrics Server + ArgoCD
./verify.sh          # sanity-check the environment
```

See [`00-cluster-setup/README.md`](./00-cluster-setup/README.md) for details, EKS notes, and teardown.

## Learning path

| Path | What it builds |
|---|---|
| [`00-cluster-setup/`](./00-cluster-setup/) | The shared kind cluster, Metrics Server, and ArgoCD. |
| [`chapter-04/`](./chapter-04/) | Organizational knowledge through a local RAG pipeline and an MCP server for live platform data. |
| [`chapter-05/`](./chapter-05/) | Backstage, software templates, GitOps delivery, an AI assistant, catalog context, and Kubernetes actions. |
| [`chapter-07/`](./chapter-07/) | A coordinator with diagnostics and GitOps specialists, official Kubernetes and GitHub MCP servers, Backstage integration, and observability. |
| [`chapter-08/`](./chapter-08/) | Mandatory guardrails, an approved MCP catalog, OPA authorization, Keycloak identity in Backstage, and tenant isolation. |
| [`chapter-09/`](./chapter-09/) | A PR-extensible memory graph for exploring future platform-engineering knowledge. |

Chapter 4 can be explored independently. Chapters 5, 7, and 8 are cumulative: Chapter 5 establishes Backstage and GitOps, Chapter 7 adds operational agents, and Chapter 8 secures their capabilities and user access.

## Conventions across chapters

- **Cluster:** reuse the `agentic-platform` cluster instead of creating one per chapter.
- **LLM provider:** Amazon Bedrock is shown by default; Anthropic API access is documented as an alternative.
- **GitOps:** application changes follow branch → pull request → human review and merge → ArgoCD.
- **Safety:** cluster diagnostics are read-only, credentials come from local environment variables or Kubernetes Secrets, and Chapter 8 evaluates identity and policy before tool execution.
