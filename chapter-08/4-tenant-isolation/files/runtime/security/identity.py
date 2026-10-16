"""Lab 4 identity: verified role plus one required tenant."""
import hashlib
import json
import os
from dataclasses import asdict, dataclass

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError


class AccessDenied(Exception):
    pass


class DependencyUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    sub: str
    role: str
    tenant_id: str

    @classmethod
    def from_claims(cls, claims):
        subject = claims.get('sub')
        roles = claims.get('roles')
        tenant = claims.get('tenant_id')
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
            raise AccessDenied('invalid_identity_claims')
        if not isinstance(roles, list) or len(roles) != 1 or not all(
            isinstance(value, str) and value.strip() and len(value) <= 100 for value in roles
        ):
            raise AccessDenied('invalid_role_claims')
        if not isinstance(tenant, str) or not tenant.strip() or len(tenant) > 100:
            raise AccessDenied('invalid_tenant_claims')
        return cls(subject, roles[0], tenant)

    def document(self):
        return asdict(self)

    def storage_key(self):
        return hashlib.sha256(json.dumps([self.tenant_id, self.sub]).encode()).hexdigest()

    def audit_context(self):
        return {'tenant_id': self.tenant_id}


ALICE = Principal('alice@company.com', 'platform-engineer', 'tenant-a')
BOB = Principal('bob@company.com', 'developer', 'tenant-b')


def mode():
    value = os.getenv('SECURITY_MODE', 'guardrail')
    if value not in {'guardrail', 'opa', 'signed-token'}:
        raise RuntimeError('SECURITY_MODE must be guardrail, opa, or signed-token')
    return value


class TokenValidator:
    def __init__(self, issuer=None, jwks_url=None):
        self.issuer = issuer or os.environ['TOKEN_ISSUER']
        self.jwks = PyJWKClient(
            jwks_url or os.environ['TOKEN_JWKS_URL'],
            cache_jwk_set=True,
            lifespan=300,
            timeout=2,
        )

    def validate(self, token, audience='agent-platform'):
        try:
            signing_key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key, algorithms=['RS256'], audience=audience,
                                issuer=self.issuer,
                                options={'require': ['exp', 'iat', 'iss', 'aud', 'sub', 'azp']})
            if (claims['exp'] - claims['iat'] > 300 or
                    not isinstance(claims.get('scope'), str) or
                    'agent.invoke' not in claims['scope'].split()):
                raise AccessDenied('invalid_token_scope_or_lifetime')
            return Principal.from_claims(claims), claims
        except (PyJWKClientConnectionError, PyJWKClientError) as exc:
            raise DependencyUnavailable('identity_provider_unavailable') from exc
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AccessDenied('invalid_token') from exc


def bearer(header):
    if not header or not header.startswith('Bearer ') or not header[7:].strip():
        raise AccessDenied('missing_bearer_token')
    return header[7:]
