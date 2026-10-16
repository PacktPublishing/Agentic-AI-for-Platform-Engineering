# OPA's HTTP management API must not be writable by policy consumers.
package system.authz
import rego.v1

default allow := false
allow if { input.method == "GET"; input.path == ["health"] }
allow if { input.method == "POST"; input.path == ["v1", "data", "agent", "tool_validation", "decision"] }
