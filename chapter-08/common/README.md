# Shared Chapter 8 runtime

The three agents use mandatory hooks around the upstream MCP tools. `security/catalog.py` retrieves reviewed MCP entries, agent profiles, and application metadata from Backstage. `security/policy.py` enforces the profile and sends authorization input to OPA from Lab 2 onward. `security/identity.py` validates the Keycloak access tokens introduced in Lab 3.

The shared Lab 3 identity contains only the verified subject and role. Lab 4 layers its tenant-aware identity validator and tenant Rego rule over this image, so tenant enforcement is introduced only in that lab.

Profiles are loaded before MCP connections open and refreshed for each invocation. Applications are resolved from Backstage on first use within that invocation. A request keeps one policy/target snapshot (with a catalog digest in tool audit records); catalog changes apply to the next invocation, not halfway through an in-flight request. MCP endpoint or tool additions require a runtime restart; revocations take effect on the next invocation. Missing, untrusted, or unavailable catalog data fails closed.

Catalog Resource types `mcp-server`, `guardrail-profile`, and `ai-agent`, plus the `platform.example.com/*` annotations, are conventions implemented by this lab—not built-in Backstage authorization features. Only entities from the expected reviewed Git locations are accepted. Protect those files with platform-owned review rules; Backstage's normal `spec.owner` is descriptive and is not used as an authorization grant.

The lab supports one dedicated namespace per application in the configured GitOps repository and default catalog namespace. Runtime tool restrictions do not protect direct access to an MCP endpoint: production also requires network isolation, scoped service credentials, and protected Git branches. The official servers use platform credentials; end-user tokens stay in the agent runtime.

Dependencies remain exactly pinned in `runtime/requirements.lock`. Images remain Python `3.12.14-slim-bookworm`, Kubernetes MCP `v0.0.66`, GitHub MCP `v1.12.1`, OPA `1.4.2-static`, and Keycloak `26.7.4`. Catalog image metadata is checked against the expected configuration; it is not runtime image attestation. The demo applications use the Kubernetes manifests rendered from the installed application template.
