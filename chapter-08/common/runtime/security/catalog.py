"""Resolve reviewed Backstage entities; catalog text is never model-provided policy."""
import os
import hashlib
import json
import re
from urllib.parse import quote

import httpx

from .identity import AccessDenied, DependencyUnavailable


class BackstageCatalog:
    def __init__(self, client=None):
        self.client = client or httpx.Client(
            base_url=os.environ['BACKSTAGE_URL'].rstrip('/'), timeout=5, trust_env=False,
            headers={'Authorization': 'Bearer ' + os.environ['BACKSTAGE_SERVICE_TOKEN']},
        )
        self.repo_url = ('https://github.com/' + os.environ['GITHUB_REPO_OWNER'] + '/' +
                         os.environ['GITHUB_REPO_NAME'] + '/blob/' +
                         os.getenv('GITHUB_DEFAULT_BRANCH', 'main') + '/')
        self.governance_location = 'url:' + self.repo_url + 'platform-security.yaml'

    def get(self, path, params=None):
        try:
            response = self.client.get(path, params=params)
            if response.status_code == 404:
                raise AccessDenied('catalog_entity_not_found')
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise DependencyUnavailable('catalog_unavailable') from exc

    def entity(self, ref):
        if not isinstance(ref, str) or not re.fullmatch(r'(resource|component):default/[a-z0-9-]+', ref):
            raise AccessDenied('invalid_catalog_reference')
        kind, rest = ref.split(':')
        namespace, name = rest.split('/')
        entity = self.get(f'/api/catalog/entities/by-name/{kind}/{namespace}/{quote(name, safe="")}')
        if (not isinstance(entity, dict) or entity.get('kind', '').lower() != kind or
                entity.get('metadata', {}).get('name') != name or
                entity.get('metadata', {}).get('namespace', 'default') != namespace):
            raise AccessDenied('invalid_catalog_entity')
        return entity

    @staticmethod
    def require_location(entity, expected):
        annotations = entity.get('metadata', {}).get('annotations', {})
        location = annotations.get('backstage.io/managed-by-location', '')
        # GitHub discovery and scaffolder registrations may use tree or blob URLs.
        if not isinstance(location, str) or location.replace('/tree/', '/blob/', 1) != expected:
            raise AccessDenied('untrusted_catalog_location')

    def governance(self, ref, type):
        entity = self.entity(ref)
        self.require_location(entity, self.governance_location)
        if entity.get('spec', {}).get('type') != type:
            raise AccessDenied('invalid_governance_entity')
        return entity['spec']

    def guardrails(self):
        """Load a fresh, consistent profile snapshot for startup or one invocation."""
        result = {'revision': 'chapter08-v6', 'agent_permissions': {}, 'mcp_servers': {}}
        for actor in ('coordinator', 'diagnostics', 'gitops'):
            agent = self.governance(f'resource:default/{actor}-agent', 'ai-agent')
            ref = f'resource:default/{actor}-guardrails'
            if agent.get('guardrailProfile') != ref:
                raise AccessDenied('mandatory_profile_missing')
            profile = self.governance(ref, 'guardrail-profile')
            if (profile.get('agent') != actor or profile.get('revision') != result['revision'] or
                    profile.get('rules') != {'applicationScope': 'dedicated-namespace',
                                            'pullRequestsOnly': True, 'readOnlyCluster': True}):
                raise AccessDenied('invalid_guardrail_profile')
            allowed = profile.get('allowedTools')
            if not isinstance(allowed, list) or not allowed or not all(isinstance(t, str) for t in allowed):
                raise AccessDenied('invalid_guardrail_tools')
            key = {'diagnostics': 'kubernetes', 'gitops': 'github'}.get(actor)
            expected = [f'resource:default/{key}-mcp'] if key else []
            if profile.get('mcpServers') != expected:
                raise AccessDenied('mcp_server_not_approved')
            result['agent_permissions'][actor] = allowed
            if not key:
                continue
            server = self.governance(expected[0], 'mcp-server')
            # Bootstrap pins prevent a catalog edit redirecting the PAT elsewhere.
            endpoint = os.environ['MCP_CLUSTER_URL' if key == 'kubernetes' else 'MCP_GITOPS_URL']
            image = {'kubernetes': 'quay.io/containers/kubernetes_mcp_server:v0.0.66',
                     'github': 'ghcr.io/github/github-mcp-server:v1.12.1'}[key]
            if (server.get('endpoint') != endpoint or server.get('transport') != 'streamable-http' or
                    server.get('image') != image):
                raise AccessDenied('mcp_connection_not_approved')
            result['mcp_servers'][key] = {'endpoint': endpoint, 'implementation': image,
                                        'allowed_agents': [actor], 'allowed_tools': allowed}
        result['catalog_digest'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        return result

    def target(self, application):
        entity = self.entity(f'component:default/{application}')
        self.require_location(entity, 'url:' + self.repo_url + application + '/catalog-info.yaml')
        annotations = entity.get('metadata', {}).get('annotations', {})
        fields = {'namespace': 'backstage.io/kubernetes-namespace',
                  'name': 'platform.example.com/workload-name',
                  'environment': 'platform.example.com/environment',
                  'tenant_id': 'platform.example.com/tenant',
                  'path': 'platform.example.com/manifest-path'}
        target = {key: annotations.get(value) for key, value in fields.items()}
        if not all(isinstance(v, str) and v for v in target.values()):
            raise AccessDenied('application_security_metadata_missing')
        if any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', target[k])
               for k in ('namespace', 'name', 'tenant_id')):
            raise AccessDenied('invalid_application_metadata')
        path = target['path']
        if (not re.fullmatch(r'[a-zA-Z0-9_./-]+', path) or path.startswith('/') or
                any(part in {'', '.', '..'} for part in path.split('/')) or
                not path.startswith(application + '/') or path == application + '/catalog-info.yaml' or
                not path.endswith(('.yaml', '.yml'))):
            raise AccessDenied('invalid_manifest_path')
        if (target['environment'] not in {'dev', 'staging', 'production'} or
                annotations.get('platform.example.com/namespace-scope') != 'dedicated'):
            raise AccessDenied('unsupported_application_scope')
        return {'component': application, **target}

    def components(self):
        """Searchable applications, discovered from Backstage rather than a local list."""
        response = self.get('/api/catalog/entities', {'filter': 'kind=component,metadata.namespace=default'})
        if not isinstance(response, list):
            raise DependencyUnavailable('invalid_catalog_response')
        return response
