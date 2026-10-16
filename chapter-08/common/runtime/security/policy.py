"""Guard the official MCP tools with a reviewed catalog and optional OPA."""

import os
import re

import httpx

from .identity import AccessDenied, DependencyUnavailable


MCP_SERVER_FOR_TOOL = {
    "resources_get": "kubernetes",
    "resources_list": "kubernetes",
    "pods_list_in_namespace": "kubernetes",
    "pods_get": "kubernetes",
    "pods_log": "kubernetes",
    "events_list": "kubernetes",
    "get_file_contents": "github",
    "create_branch": "github",
    "create_or_update_file": "github",
    "create_pull_request": "github",
}

NON_RESOURCE_TOOLS = {
    "consult_skill",
    "save_to_memory",
    "search_catalog",
    "search_documentation",
}

DELEGATION_TOOLS = {"diagnose_application", "review_configuration", "propose_change"}
KUBERNETES_RESOURCE_KINDS = {"Pod", "Service", "Deployment", "ReplicaSet"}


class Policy:
    def __init__(self, catalog, registry=None, url=None, client=None):
        self.catalog = catalog
        self.registry = registry if registry is not None else catalog.guardrails()
        self.targets = {}
        self.url = url or os.getenv("OPA_URL", "http://opa-policy-engine:8181")
        self.client = client or httpx.Client(timeout=2, trust_env=False)
        self.opa_enabled = os.getenv("OPA_ENABLED", "0").lower() in {"1", "true", "yes"}

    def application(self, name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', name):
            raise AccessDenied("invalid_application")
        if name not in self.targets:
            self.targets[name] = self.catalog.target(name)
        return self.targets[name]

    def approved_mcp(self, actor, name):
        server = self.registry.get("mcp_servers", {}).get(name)
        if not server or actor not in server.get("allowed_agents", []):
            raise AccessDenied("mcp_server_not_approved")
        return server

    def target(self, tool, arguments, application=None):
        if not isinstance(arguments, dict):
            raise AccessDenied("invalid_arguments")
        if tool in NON_RESOURCE_TOOLS:
            return None
        component = application or arguments.get("application")
        if application and arguments.get("application", application) != application:
            raise AccessDenied("delegation_scope_mismatch")
        target = self.application(component)
        if tool in {"get_file_contents", "create_or_update_file"}:
            if arguments.get("path") != target["path"]:
                raise AccessDenied("path_not_allowed")
        return target

    def authorize(
        self,
        principal,
        tool,
        arguments,
        memory_enabled=False,
        actor="coordinator",
        application=None,
    ):
        if tool not in set(MCP_SERVER_FOR_TOOL) | NON_RESOURCE_TOOLS | DELEGATION_TOOLS:
            raise AccessDenied("unknown_tool")
        target = self.target(tool, arguments, application)
        if tool == "save_to_memory" and not memory_enabled:
            raise AccessDenied("memory_disabled")
        agent_permissions = self.registry.get("agent_permissions", {})
        if tool not in agent_permissions.get(actor, []):
            raise AccessDenied("agent_permission_denied")

        mcp_server = MCP_SERVER_FOR_TOOL.get(tool)
        if mcp_server:
            server = self.approved_mcp(actor, mcp_server)
            if tool not in server.get("allowed_tools", []):
                raise AccessDenied("mcp_server_not_approved")

        if mcp_server == "github":
            if (
                arguments.get("owner") != os.getenv("GITHUB_REPO_OWNER")
                or arguments.get("repo") != os.getenv("GITHUB_REPO_NAME")
            ):
                raise AccessDenied("repository_not_approved")

        if mcp_server == "kubernetes":
            if arguments.get("namespace") != target["namespace"]:
                raise AccessDenied("namespace_not_allowed")
            if tool in {"resources_get", "resources_list"}:
                if arguments.get("kind") not in KUBERNETES_RESOURCE_KINDS:
                    raise AccessDenied("resource_kind_not_allowed")
            # The lab authorizes a dedicated application namespace, including its
            # dynamically named Pods, ReplicaSets, Services and events.
            if arguments.get("context"):
                raise AccessDenied("cluster_override_not_allowed")
            if tool in {"resources_get", "resources_list"}:
                expected = "apps/v1" if arguments["kind"] in {"Deployment", "ReplicaSet"} else "v1"
                if arguments.get("apiVersion") != expected:
                    raise AccessDenied("resource_api_not_allowed")
            if tool == "pods_log" and (type(arguments.get("tail", 100)) is not int or
                                        not 1 <= arguments.get("tail", 100) <= 200):
                raise AccessDenied("log_limit_exceeded")

        if tool == "create_pull_request":
            title = arguments.get("title", "")
            body = arguments.get("body", "")
            if not isinstance(title, str) or not title.startswith("[agent] "):
                raise AccessDenied("invalid_pr_title")
            if not isinstance(body, str) or len(body.strip()) < 20:
                raise AccessDenied("invalid_pr_body")
            head = arguments.get("head") or arguments.get("head_branch") or ""
            base = arguments.get("base") or arguments.get("base_branch")
            if not str(head).startswith("agent/"):
                raise AccessDenied("invalid_branch_prefix")
            if base != os.getenv("GITHUB_DEFAULT_BRANCH", "main"):
                raise AccessDenied("invalid_base_branch")

        if tool in {"create_branch", "create_or_update_file"}:
            branch = arguments.get("branch") or arguments.get("head_branch") or ""
            if not str(branch).startswith("agent/"):
                raise AccessDenied("invalid_branch_prefix")
            from_branch = arguments.get("from_branch") or arguments.get("base_branch")
            if from_branch and from_branch != os.getenv("GITHUB_DEFAULT_BRANCH", "main"):
                raise AccessDenied("invalid_base_branch")

        doc = {
            "actor": actor,
            "schema_version": 1,
            "identity": principal.document(),
            "tool": tool,
            "arguments": arguments,
            "target": target,
            "mcp_server": mcp_server,
            "guardrails": self.registry,
            "repository": {
                "owner": os.getenv("GITHUB_REPO_OWNER", ""),
                "name": os.getenv("GITHUB_REPO_NAME", ""),
                "default_branch": os.getenv("GITHUB_DEFAULT_BRANCH", "main"),
            },
            "policy_revision": self.registry["revision"],
            "memory_enabled": memory_enabled,
        }

        if not self.opa_enabled:
            return {"target": target, "policy_revision": self.registry["revision"],
                    "catalog_digest": self.registry["catalog_digest"]}

        try:
            response = self.client.post(
                f"{self.url}/v1/data/agent/tool_validation/decision",
                json={"input": doc},
            )
            response.raise_for_status()
            decision = response.json()["result"]
            if (
                not isinstance(decision, dict)
                or type(decision.get("allow")) is not bool
                or not isinstance(decision.get("deny"), list)
                or not all(isinstance(value, str) for value in decision["deny"])
                or not isinstance(decision.get("revision"), str)
            ):
                raise ValueError("malformed_decision")
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise DependencyUnavailable("policy_unavailable") from exc

        if not decision["allow"] or decision["deny"]:
            raise AccessDenied(",".join(decision["deny"]) or "policy_denied")
        if decision["revision"] != self.registry["revision"]:
            raise DependencyUnavailable("policy_revision_mismatch")
        return {"target": target, "policy_revision": decision["revision"]}
