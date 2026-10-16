import { useState } from 'react';
import { Button, TextField, Typography } from '@material-ui/core';
import { Content, Header, Page } from '@backstage/core-components';
import { discoveryApiRef, fetchApiRef, useApi } from '@backstage/core-plugin-api';
import { oidcAuthApiRef } from '../../oidc';

export const SecureAgentPage = () => {
  const oidc = useApi(oidcAuthApiRef);
  const discovery = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const [intent, setIntent] = useState('');
  const [answer, setAnswer] = useState('');
  const [waiting, setWaiting] = useState(false);

  const invoke = async () => {
    setWaiting(true);
    setAnswer('');
    try {
      const accessToken = await oidc.getAccessToken();
      const baseUrl = await discovery.getBaseUrl('secure-agent-proxy');
      const response = await fetchApi.fetch(`${baseUrl}/invoke`, {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-keycloak-token': accessToken,
        },
        body: JSON.stringify({
          intent,
          session_id: `backstage-${crypto.randomUUID()}`,
        }),
      });
      const body = await response.text();
      if (!response.ok) throw new Error(`${response.status}: ${body}`);
      setAnswer((JSON.parse(body) as { response: string }).response);
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : String(error));
    } finally {
      setWaiting(false);
    }
  };

  return (
    <Page themeId="tool">
      <Header title="Verified platform assistant" />
      <Content>
        <Typography paragraph>
          This request carries your short-lived Keycloak access token to the secured agent runtime.
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={3}
          variant="outlined"
          placeholder="Ask the platform assistant"
          value={intent}
          onChange={event => setIntent(event.target.value)}
        />
        <Button
          color="primary"
          variant="contained"
          disabled={waiting || !intent.trim()}
          onClick={invoke}
          style={{ marginTop: 16 }}
        >
          {waiting ? 'Running…' : 'Ask the agent'}
        </Button>
        {answer && <Typography component="pre" style={{ whiteSpace: 'pre-wrap', marginTop: 24 }}>{answer}</Typography>}
      </Content>
    </Page>
  );
};
