# Chapter 7: Operational Agents and Collaboration

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

Build a separate agent runtime, add collaborating specialists, then connect them to the existing Chapter 5 Backstage Chat Assistant in Lab 4. The chat UI and route stay the same. Three agents diagnose application problems and propose repairs through GitOps:

- **Platform Coordinator** understands the request, delegates work, and explains the result.
- **Cluster Diagnostics Agent** reads live Kubernetes state to investigate the problem.
- **GitOps Change Agent** reads the application manifest and proposes an image-change PR.

The agents share a runtime, with separate prompts and tools. The coordinator manages the handoffs; MCP servers provide access to platform tools. Lab 2 runs the [Kubernetes MCP server](https://github.com/containers/kubernetes-mcp-server) directly in read-only mode. Lab 3 connects the GitOps specialist directly to [GitHub’s official MCP server](https://github.com/github/github-mcp-server).

All workload changes follow **Git branch → PR → human review and merge → ArgoCD**. Cluster access is read-only. A PR hook checks proposal conventions, while Langfuse traces and audit records make the agents’ work visible. After deployment, a follow-up request verifies recovery.

## Labs

Reuse the Chapter 5 kind cluster, Backstage app, components repository, and ArgoCD setup. The example application is `my-first-app` in namespace `my-first-app`.

| Lab | Focus |
| --- | --- |
| [0 — Prerequisites](0-prereqs/README.md) | Check the platform and repository settings |
| [1 — Runtime](1-strands-runtime/README.md) | Deploy the Strands agent service |
| [2 — Diagnostics](2-cluster-diagnostics/README.md) | Add the cluster diagnostics specialist |
| [3 — GitOps and collaboration](3-gitops-mcp/README.md) | Connect the agents and propose repair PRs |
| [4 — Backstage chat](4-backstage-collaboration/README.md) | Connect the existing Chat Assistant |
| [5 — Observability](5-langfuse-audit/README.md) | Inspect traces and audit records |

Chapter 7 focuses on collaboration using shared service credentials. Chapter 8 adds mandatory guardrails, an approved MCP catalog, OPA authorization, verified user identity, and tenant isolation.

Start with [the prerequisites](0-prereqs/README.md).
