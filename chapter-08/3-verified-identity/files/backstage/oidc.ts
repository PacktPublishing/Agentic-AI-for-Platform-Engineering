import { OAuth2 } from '@backstage/core-app-api';
import {
  BackstageIdentityApi,
  configApiRef,
  createApiFactory,
  createApiRef,
  discoveryApiRef,
  oauthRequestApiRef,
  OAuthApi,
  OpenIdConnectApi,
  ProfileInfoApi,
  SessionApi,
} from '@backstage/core-plugin-api';

export const oidcAuthApiRef = createApiRef<
  OAuthApi & OpenIdConnectApi & ProfileInfoApi & BackstageIdentityApi & SessionApi
>({ id: 'auth.oidc' });

export const oidcApiFactory = createApiFactory({
  api: oidcAuthApiRef,
  deps: {
    configApi: configApiRef,
    discoveryApi: discoveryApiRef,
    oauthRequestApi: oauthRequestApiRef,
  },
  factory: ({ configApi, discoveryApi, oauthRequestApi }) =>
    OAuth2.create({
      configApi,
      discoveryApi,
      oauthRequestApi,
      provider: { id: 'oidc', title: 'Keycloak', icon: () => null },
    }),
});
