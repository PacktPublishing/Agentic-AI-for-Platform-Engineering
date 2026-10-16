import express from 'express';
import {
  coreServices,
  createBackendPlugin,
} from '@backstage/backend-plugin-api';

export default createBackendPlugin({
  pluginId: 'secure-agent-proxy',
  register(env) {
    env.registerInit({
      deps: {
        config: coreServices.rootConfig,
        httpRouter: coreServices.httpRouter,
        logger: coreServices.logger,
      },
      async init({ config, httpRouter, logger }) {
        const router = express.Router();
        router.use(express.json());
        const runtimeUrl = config.getString('chapter08.agentRuntimeUrl');

        router.post('/invoke', async (req, res) => {
          const accessToken = req.header('x-keycloak-token');
          if (!accessToken) {
            res.status(401).json({ error: 'Missing Keycloak access token' });
            return;
          }

          const upstream = await fetch(`${runtimeUrl}/invoke`, {
            method: 'POST',
            signal: AbortSignal.timeout(120000),
            headers: {
              authorization: `Bearer ${accessToken}`,
              'content-type': 'application/json',
            },
            body: JSON.stringify(req.body),
          });
          const body = await upstream.text();
          logger.info(`secure agent request completed status=${upstream.status}`);
          res.status(upstream.status).type(upstream.headers.get('content-type') ?? 'application/json').send(body);
        });

        httpRouter.use(router);
      },
    });
  },
});
