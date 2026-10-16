# Lab 0: Prerequisites

Complete Chapter 7 through Lab 5. Reuse its kind cluster, components repository, Backstage catalog/chat, model credentials, and `agent-backstage-read` service token. Backstage must remain reachable while the Chapter 8 runtime starts and handles requests. Lab 3 deploys a local Keycloak instance in the existing cluster.

Set the repository paths and cluster architecture in your lab terminal:

```bash
export BOOK_REPO=/absolute/path/to/ai-driven-platform-engineering-book
export COMPONENTS_REPO=/absolute/path/to/backstage-components
export BACKSTAGE_APP=/absolute/path/to/my-backstage-app
export KIND_PLATFORM=linux/arm64 # linux/amd64 for Intel/AMD
```

Read the GitHub owner from the existing ArgoCD repository Secret:

```bash
export GITHUB_USERNAME="$(kubectl -n argocd get secret github-creds -o json \
  | jq -er '.data.url | @base64d | capture("^https://github\\.com/(?<owner>[A-Za-z0-9-]+)/").owner')"
: "${GITHUB_USERNAME:?Could not read the GitHub repository owner}"
```

Verify the existing services and required Secrets:

```bash
kubectl -n agent-platform get deployments,services,pvc
kubectl -n agent-platform get secret gitops-mcp-github agent-backstage-read
kubectl -n argocd get applications
```

The GitHub Secret is reused under `GITHUB_PERSONAL_ACCESS_TOKEN` for the lab. In production, use dedicated least-privilege service credentials and protect the default branch with required review. The Backstage service token identifies the runtime service; it does not identify Alice or Bob.

You need Docker, kind, kubectl, Git, GitHub CLI, curl, jq, OpenSSL, and Python 3. No host pip installation or virtual environment is required. Start each lab from the updated default branch with a clean components working tree; choose a fresh branch name when repeating a lab.

Continue to [Lab 1](../1-guardrails-mcp-catalog/README.md).
