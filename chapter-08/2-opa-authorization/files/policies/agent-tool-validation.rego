package agent.tool_validation

import rego.v1

default allow := false

decision := {"allow": allow, "deny": sort(deny), "revision": data.revision}

known_tool if {
    input.tool in {
        "resources_get", "resources_list", "pods_list_in_namespace", "pods_get", "pods_log", "events_list",
        "get_file_contents", "create_branch", "create_or_update_file", "create_pull_request",
        "consult_skill", "save_to_memory", "search_catalog", "search_documentation",
        "diagnose_application", "review_configuration", "propose_change",
    }
}

resource_tool if {
    input.tool in {
        "resources_get", "resources_list", "pods_list_in_namespace", "pods_get", "pods_log", "events_list",
        "get_file_contents", "create_branch", "create_or_update_file", "create_pull_request",
        "diagnose_application", "review_configuration", "propose_change",
    }
}

valid_identity if {
    is_string(input.identity.sub)
    input.identity.sub != ""
    is_string(input.identity.role)
    input.identity.role != ""
}

known_role if { is_object(data.role_permissions[input.identity.role]) }
permitted_agent if { input.tool in input.guardrails.agent_permissions[input.actor] }

approved_mcp if {
    input.mcp_server != null
    server := input.guardrails.mcp_servers[input.mcp_server]
    input.actor in server.allowed_agents
    input.tool in server.allowed_tools
}

approved_repository if {
    input.mcp_server != "github"
}

allowed_kubernetes_kind if {
    input.arguments.kind in {"Pod", "Service", "Deployment", "ReplicaSet"}
}

valid_kubernetes_scope if {
    input.mcp_server == "kubernetes"
    input.arguments.namespace == input.target.namespace
    input.tool in {"resources_get", "resources_list"}
    allowed_kubernetes_kind
}

valid_github_path if {
    input.mcp_server == "github"
    input.tool in {"get_file_contents", "create_or_update_file"}
    input.arguments.path == input.target.path
}

valid_github_path if {
    input.mcp_server == "github"
    input.tool in {"create_branch", "create_pull_request"}
}

valid_kubernetes_scope if {
    input.mcp_server == "kubernetes"
    input.arguments.namespace == input.target.namespace
    input.tool in {"pods_list_in_namespace", "events_list"}
}

valid_kubernetes_scope if {
    input.mcp_server == "kubernetes"
    input.arguments.namespace == input.target.namespace
    input.tool in {"pods_get", "pods_log"}
}

approved_repository if {
    input.mcp_server == "github"
    input.repository.owner == input.arguments.owner
    input.repository.name == input.arguments.repo
}

# Target and guardrails are resolved by the runtime from reviewed Backstage entities.
# They are never accepted from /invoke or from model-generated tool arguments.
valid_target if {
    resource_tool
    is_object(input.target)
    every field in {"component", "path", "name", "namespace", "tenant_id", "environment"} {
        is_string(input.target[field])
        input.target[field] != ""
    }
}

permitted_action if {
    environments := data.role_permissions[input.identity.role][input.tool]
    input.target.environment in environments
}

deny contains "invalid_identity" if { not valid_identity }
deny contains "invalid_schema" if { not input.schema_version == 1 }
deny contains "unknown_tool" if { not known_tool }
deny contains "agent_permission_denied" if { not permitted_agent }
deny contains "mcp_server_not_approved" if { input.mcp_server != null; not approved_mcp }
deny contains "repository_not_approved" if { input.mcp_server == "github"; not approved_repository }
deny contains "namespace_not_allowed" if { input.mcp_server == "kubernetes"; not valid_kubernetes_scope }
deny contains "path_not_allowed" if { input.mcp_server == "github"; not valid_github_path }
deny contains "unknown_role" if { not known_role }
deny contains "unknown_target" if { resource_tool; not valid_target }
deny contains "permission_denied" if { resource_tool; not permitted_action }
deny contains "revision_mismatch" if { input.policy_revision != data.revision }

valid_title if { is_string(input.arguments.title); startswith(input.arguments.title, "[agent] ") }
valid_body if { is_string(input.arguments.body); count(trim_space(input.arguments.body)) >= 20 }
deny contains "invalid_pr_title" if { input.tool == "create_pull_request"; not valid_title }
deny contains "invalid_pr_body" if { input.tool == "create_pull_request"; not valid_body }
valid_head if {
    is_string(input.arguments.head)
    startswith(input.arguments.head, "agent/")
}
valid_base if {
    is_string(input.arguments.base)
    input.arguments.base == input.repository.default_branch
}
valid_write_branch if {
    input.tool in {"create_branch", "create_or_update_file"}
    is_string(input.arguments.branch)
    startswith(input.arguments.branch, "agent/")
}
valid_from_branch if {
    input.tool == "create_branch"
    not input.arguments.from_branch
}
valid_from_branch if {
    input.tool == "create_branch"
    input.arguments.from_branch == input.repository.default_branch
}
valid_from_branch if {
    input.tool == "create_or_update_file"
    not input.arguments.from_branch
}
valid_from_branch if {
    input.tool == "create_or_update_file"
    input.arguments.from_branch == input.repository.default_branch
}
deny contains "invalid_branch_prefix" if { input.tool == "create_pull_request"; not valid_head }
deny contains "invalid_base_branch" if { input.tool == "create_pull_request"; not valid_base }
deny contains "invalid_branch_prefix" if { input.tool in {"create_branch", "create_or_update_file"}; not valid_write_branch }
deny contains "invalid_base_branch" if { input.tool in {"create_branch", "create_or_update_file"}; not valid_from_branch }
deny contains "unknown_skill" if { input.tool == "consult_skill"; input.arguments.name != "fix-image-tag" }
deny contains "memory_disabled" if { input.tool == "save_to_memory"; input.memory_enabled != true }
deny contains "invalid_memory" if {
    input.tool == "save_to_memory"
    not is_string(input.arguments.fact)
}

allow if {
    input.schema_version == 1
    valid_identity
    known_tool
    count(deny) == 0
}
