# Chapter 8: Security in Practice

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

These cumulative labs add enforceable security to the agent platform. Backstage supplies reviewed application metadata, approved MCP entries, and mandatory guardrails. The runtime validates identity and uses OPA to authorize every tool call by role, environment, and tenant.

Kubernetes access remains read-only. Repository changes are proposed through pull requests, reviewed by a person, and applied by ArgoCD after merge.

## Labs

| Lab | Outcome |
|---|---|
| [Prerequisites](0-prereqs/README.md) | Verify the existing platform, paths, architecture, and credentials. |
| [1 — Guardrails and MCP catalog](1-guardrails-mcp-catalog/README.md) | Register approved MCP servers and mandatory agent guardrails in Backstage. |
| [2 — OPA authorization](2-opa-authorization/README.md) | Authorize tools by role, action, and application environment. |
| [3 — Verified identity](3-verified-identity/README.md) | Authenticate Backstage users with Keycloak and validate their short-lived tokens at the runtime. |
| [4 — Tenant isolation](4-tenant-isolation/README.md) | Enforce tenant boundaries across tools, applications, sessions, memory, and the Backstage interface. |

The labs use `logistics-demo`, `payments-demo`, and `logistics-prod` to demonstrate allowed access, tenant denial, and production denial. They share [`common/runtime`](common/README.md) and build it with tags `0.8.1` through `0.8.4`.

The runnable content stays outside the printed book so it can evolve independently. Lab details may change as the supporting projects change.

Start with [Lab 0: Prerequisites](0-prereqs/README.md).
