from strands.hooks import HookProvider, HookRegistry, BeforeToolCallEvent, AfterToolCallEvent
from security.identity import AccessDenied, DependencyUnavailable


class PolicyValidationHook(HookProvider):
    def __init__(self, principal, policy, audit, request_id, memory_enabled=False,
                 trace=None, actor='coordinator', application=None):
        self.actor = actor
        self.principal, self.policy, self.audit = principal, policy, audit
        self.request_id, self.memory_enabled, self.trace = request_id, memory_enabled, trace
        self.application = application
        self.pending = {}

    def register_hooks(self, registry: HookRegistry):
        registry.add_callback(BeforeToolCallEvent, self.before)
        registry.add_callback(AfterToolCallEvent, self.after)

    def record(self, **fields):
        self.audit.record(layer='agent', actor=self.actor, request_id=self.request_id,
                          subject=self.principal.sub, **self.principal.audit_context(),
                          **fields)

    def before(self, event):
        name = event.tool_use.get('name', '')
        params = event.tool_use.get('input', {})
        outcome, reason, evidence = 'allow', '', {}
        try:
            if event.selected_tool is None or event.selected_tool.tool_name != name:
                raise AccessDenied('unknown_tool')
            evidence = self.policy.authorize(
                self.principal, name, params, self.memory_enabled,
                actor=self.actor, application=self.application,
            )
        except AccessDenied as exc:
            outcome, reason = 'deny', str(exc)
        except DependencyUnavailable as exc:
            outcome, reason = 'dependency_failure', str(exc)
        event_id = event.tool_use.get('toolUseId', '')
        if outcome != 'allow':
            event.cancel_tool = f'{outcome}: {reason}'
        # Audit failures propagate: no tool may execute without this pre-execution record.
        self.record(phase='decision', tool=name, tool_call_id=event_id,
                    outcome=outcome, reason=reason, **evidence)
        self.pending[event_id] = outcome
        if self.trace:
            self.trace.event(name='authorization', metadata={'tool': name, 'outcome': outcome,
                             'reason': reason, 'request_id': self.request_id, **evidence})

    def after(self, event):
        event_id = event.tool_use.get('toolUseId', '')
        allowed = self.pending.pop(event_id, 'deny') == 'allow'
        result = getattr(event, 'result', {}) or {}
        cancelled = not allowed or bool(getattr(event, 'cancel_message', None))
        failed = bool(getattr(event, 'exception', None)) or (
            isinstance(result, dict) and result.get('status') == 'error'
        )
        outcome = 'cancelled' if cancelled else ('error' if failed else 'success')
        self.record(phase='execution', tool=event.tool_use.get('name', ''),
                    tool_call_id=event_id, outcome=outcome)
