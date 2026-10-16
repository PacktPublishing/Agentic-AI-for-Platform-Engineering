import asyncio
import fcntl
import hashlib
import json
import logging
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from security.audit import Audit
from security.identity import ALICE, AccessDenied, DependencyUnavailable, TokenValidator, bearer, mode
from security.policy import Policy
from security.catalog import BackstageCatalog
from . import telemetry
from .agent import build_agent
from .mcp_clients import MCPConnections
from .settings import settings

logger = logging.getLogger('agent.startup')


class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: str = Field(min_length=1, max_length=12000)
    session_id: str = Field(default='default', pattern=r'^[A-Za-z0-9_-]{1,80}$')


def initialize_dependencies(catalog):
    policy = None
    connections = MCPConnections()
    try:
        policy = Policy(catalog)
        connections.start(policy.registry)
        return policy, connections
    except Exception:
        connections.close()
        if policy is not None:
            policy.client.close()
        raise


async def wait_for_dependencies(app):
    while True:
        try:
            policy, connections = await asyncio.to_thread(initialize_dependencies, app.state.catalog)
        except Exception as exc:
            app.state.dependency_error = f'{type(exc).__name__}: {exc}'
            logger.warning('dependencies not ready; retrying in 5 seconds: %s',
                           app.state.dependency_error)
            await asyncio.sleep(5)
            continue
        app.state.policy = policy
        app.state.mcp = connections
        app.state.dependency_error = None
        app.state.ready = True
        logger.info('dependencies ready; catalog and approved MCP connections loaded')
        return


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        app.state.validator = TokenValidator() if mode() == 'signed-token' else None
        app.state.catalog = BackstageCatalog()
        app.state.policy = None
        app.state.audit = Audit()
        app.state.mcp = None
        app.state.ready = False
        app.state.dependency_error = 'initializing'
        telemetry.configure()
        dependency_task = asyncio.create_task(wait_for_dependencies(app))
        try:
            yield
        finally:
            dependency_task.cancel()
            with suppress(asyncio.CancelledError):
                await dependency_task
            if app.state.mcp is not None:
                app.state.mcp.close()
            if app.state.policy is not None:
                app.state.policy.client.close()
            app.state.catalog.client.close()
            telemetry.flush()

    app = FastAPI(title='Chapter 8 agent', lifespan=lifespan)

    @app.get('/healthz')
    def healthz():
        return {'status': 'alive', 'mode': mode()}

    @app.get('/readyz')
    def readyz():
        if not app.state.ready:
            raise HTTPException(503, 'dependencies_not_ready')
        return {'status': 'ready', 'mode': mode()}

    @app.post('/invoke')
    def invoke(req: InvokeRequest, authorization: str | None = Header(default=None)):
        if not app.state.ready:
            raise HTTPException(503, 'dependencies_not_ready')
        request_id = str(uuid4())
        try:
            if mode() in {'guardrail', 'opa'}:
                principal, token = ALICE, None
            else:
                token = bearer(authorization)
                principal, _ = app.state.validator.validate(token, 'agent-platform')
        except (AccessDenied, DependencyUnavailable) as exc:
            app.state.audit.record(layer='ingress', request_id=request_id,
                                   outcome='authentication_failure', reason=str(exc))
            raise HTTPException(503 if isinstance(exc, DependencyUnavailable) else 401,
                                detail=str(exc), headers={'WWW-Authenticate': 'Bearer'}) from exc
        scoped_session = hashlib.sha256(json.dumps([principal.storage_key(), req.session_id]).encode()).hexdigest()
        settings.session_dir.mkdir(parents=True, exist_ok=True)
        with (settings.session_dir / (scoped_session + '.lock')).open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise HTTPException(409, 'session_busy') from exc
            app.state.audit.record(layer='ingress', request_id=request_id, subject=principal.sub,
                                   session_id=scoped_session, outcome='authenticated',
                                   **principal.audit_context())
            trace = None
            try:
                lf = telemetry.client()
                if lf:
                    trace = lf.trace(name='chapter08.invoke', user_id=principal.sub, session_id=scoped_session,
                                     metadata={'request_id': request_id,
                                               **principal.audit_context()})
                policy = Policy(app.state.catalog, client=app.state.policy.client)
                agent = build_agent(principal, scoped_session, app.state.mcp.gitops_tools, policy,
                                    app.state.audit, request_id, mode() == 'signed-token', trace,
                                    app.state.mcp.cluster_tools)
                result = agent(req.intent)
                return {'session_id': req.session_id, 'request_id': request_id, 'response': str(result)}
            except Exception as exc:
                # Never return dependency bodies or tokens to the caller.
                app.state.audit.record(layer='agent', request_id=request_id, subject=principal.sub,
                                       outcome='invocation_failure',
                                       reason=type(exc).__name__, **principal.audit_context())
                raise HTTPException(503, 'invocation_failed; see correlated audit record') from exc
            finally:
                telemetry.flush()
    return app


app = create_app()
