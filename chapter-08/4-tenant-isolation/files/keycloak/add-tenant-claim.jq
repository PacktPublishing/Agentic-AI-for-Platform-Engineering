(.clientScopes[] | select(.name == "agent.invoke") | .protocolMappers) += [
  {
    "name": "tenant-id",
    "protocol": "openid-connect",
    "protocolMapper": "oidc-usermodel-attribute-mapper",
    "consentRequired": false,
    "config": {
      "user.attribute": "tenant_id",
      "claim.name": "tenant_id",
      "jsonType.label": "String",
      "multivalued": "false",
      "access.token.claim": "true",
      "id.token.claim": "false",
      "userinfo.token.claim": "false"
    }
  }
]
| (.users[] | select(.username == "alice") | .attributes.tenant_id) = ["tenant-a"]
| (.users[] | select(.username == "bob") | .attributes.tenant_id) = ["tenant-b"]
