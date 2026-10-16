# Chapter 05: Building an AI-Powered Backstage Platform

> [!WARNING]
> **For learning and experimentation only.** These labs are reference implementations and are not production-ready baselines. Do not deploy them to production without an independent security review, infrastructure hardening, and testing appropriate to your workloads and compliance requirements. The credentials, IAM permissions, network boundaries, policies, and deployment configurations are intentionally simplified for local exercises.

This chapter walks through setting up a Backstage internal developer portal and progressively enhancing it with an AI chat assistant, catalog awareness, and Kubernetes integration — all in four incremental labs.

## Labs

### [Lab 1: Setting Up Backstage with GitOps](./1-backstage-setup/)

Creates a Backstage application from scratch with GitHub integration and ArgoCD for GitOps. Includes a Web App template that scaffolds Kubernetes manifests and opens a pull request — merging it triggers an automatic deployment via ArgoCD.

### [Lab 2: Adding the AI Chat Assistant](./2-add-chat-assistant/)

Installs the [GenAI Plugin](https://github.com/awslabs/backstage-plugins-for-aws/tree/main/plugins/genai) and wires up an AI-powered chat interface in the Backstage sidebar. At this stage the assistant answers general questions using AWS Bedrock (or OpenAI) but has no access to catalog data yet.

### [Lab 3: Adding Backstage Catalog Actions](./3-add-catalog-actions/)

Gives the chat assistant read access to the Backstage software catalog and TechDocs by registering three built-in actions: `get-catalog-entity`, `search-catalog`, and `search-techdocs`. No extra packages required — just configuration.

### [Lab 4: Adding Kubernetes MCP Actions](./4-add-kubernetes-actions/)

Adds four custom `kubectl` actions (`kubectl_get_pods`, `kubectl_get_deployments`, `kubectl_get_services`, `kubectl_describe_pod`) so the assistant can query live cluster state directly from the chat interface.
