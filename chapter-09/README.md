# Chapter 9 — Future Directions

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

The closing chapter is about where AI-driven platform engineering is heading: a vocabulary for
what's next (the agentic harness as *just an architecture*; governance and context as modules),
the shift to *Forward Engineering*, and a bet on curated context becoming a tradeable good.

Most of the chapter is forward-looking prose rather than a lab. But one idea is meant to outlive
the page — so it ships as running code you can connect to and extend.

| Path | What it is |
|---|---|
| [`memory-graph/`](./memory-graph/) | The **living memory graph** — an MCP server over a curated, PR-extensible knowledge graph seeded with the whole book. Connect a local agent and query it; add to it as the field moves. |
