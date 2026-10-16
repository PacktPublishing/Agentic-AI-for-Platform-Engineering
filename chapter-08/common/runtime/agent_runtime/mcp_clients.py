"""Start the two upstream MCP connections before the runtime becomes ready.

Connections use platform credentials. Each request's verified user is enforced
by PolicyValidationHook, not by sharing a user's bearer token with an MCP server.
"""
import logging
import os
import time
from contextlib import ExitStack

from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient

logger = logging.getLogger('agent.mcp')


class MCPConnections:
    def __init__(self):
        self.stack = ExitStack()
        self.gitops_tools = []
        self.cluster_tools = []

    def connect(self, name, endpoint, headers=None):
        for attempt in range(1, 16):
            client = MCPClient(lambda: streamablehttp_client(
                endpoint.rstrip('/') + '/mcp', headers=headers,
            ))
            started = False
            try:
                client.start()
                started = True
                tools = client.list_tools_sync()
                self.stack.callback(client.stop, None, None, None)
                return tools
            except Exception as error:
                # The SDK handles failed initialization; discovery needs cleanup here.
                if started:
                    try:
                        client.stop(None, None, None)
                    except Exception:
                        logger.warning('Could not close failed %s connection', name)
                if attempt == 15:
                    raise RuntimeError(f'{name} unavailable after 15 startup attempts') from error
                logger.warning('%s is not ready; retrying (%s/15)', name, attempt)
                time.sleep(2)

    def start(self, registry):
        try:
            servers = registry['mcp_servers']
            self.cluster_tools = self.connect('Kubernetes MCP', servers['kubernetes']['endpoint'])
            self.gitops_tools = self.connect('GitHub MCP', servers['github']['endpoint'],
                {'Authorization': 'Bearer ' + os.environ['GITHUB_PERSONAL_ACCESS_TOKEN']})
            self.cluster_tools = [t for t in self.cluster_tools
                                  if t.tool_name in servers['kubernetes']['allowed_tools']]
            self.gitops_tools = [t for t in self.gitops_tools
                                 if t.tool_name in servers['github']['allowed_tools']]
        except Exception:
            self.close()
            raise

    def close(self):
        self.gitops_tools, self.cluster_tools = [], []
        try:
            self.stack.close()
        except Exception:
            logger.warning('Error closing MCP connections')
