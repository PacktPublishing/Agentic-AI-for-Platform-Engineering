# APP_NAME

APP_DESCRIPTION

## Deployment

Deployed via ArgoCD GitOps.

- **Namespace:** `APP_NAMESPACE`
- **Replicas:** MIN_REPLICAS - MAX_REPLICAS

## Access

```bash
kubectl port-forward -n APP_NAMESPACE svc/APP_NAME 8080:80
```

Open http://localhost:8080
