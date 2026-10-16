package agent.tool_validation

import rego.v1

valid_tenant_identity if {
    is_string(input.identity.tenant_id)
    input.identity.tenant_id != ""
}

deny contains "invalid_tenant_identity" if {
    not valid_tenant_identity
}

deny contains "tenant_denied" if {
    valid_target
    valid_tenant_identity
    input.identity.tenant_id != input.target.tenant_id
}
