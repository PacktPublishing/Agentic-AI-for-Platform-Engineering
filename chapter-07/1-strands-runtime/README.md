# Lab 1: A Strands Agent as a Service

Build and deploy a Strands agent runtime through GitOps, then call its `/invoke` endpoint. You will configure its identity and verify that it saves memory across requests, establishing the service that will host the collaborating agents. Complete [the prerequisites](../0-prereqs/README.md) first.

The source is in `files/agent/`; GitOps manifests are in `files/components-repo/`. Reviewed identity files load from a ConfigMap; agent-written memory persists on a PVC.

## Build and load the runtime image

Build from the lab source. Use `linux/arm64` for Apple Silicon or `linux/amd64` for Intel/AMD; keep `KIND_PLATFORM` for the following labs:

```bash
export KIND_PLATFORM=linux/arm64
docker build --platform "$KIND_PLATFORM" -t agent-runtime:0.7.1 \
  "$BOOK_REPO/chapter-07/1-strands-runtime/files/agent/"
docker image save --platform "$KIND_PLATFORM" -o /tmp/agent-runtime.tar agent-runtime:0.7.1
kind load image-archive /tmp/agent-runtime.tar --name agentic-platform
rm /tmp/agent-runtime.tar
```

If your kind cluster has a different name, replace `--name agentic-platform`. If you are not using kind, push the image to a registry your cluster can pull from and update `image:` in [deployment.yaml](files/components-repo/agent-platform/k8s/deployment.yaml).

## Ship the manifests through GitOps

Copy the manifests into your components repository:

```bash
cp -r "$BOOK_REPO/chapter-07/1-strands-runtime/files/components-repo/agent-platform" "$COMPONENTS_REPO/"
```

Use the repository owner exported in the prerequisites:

```bash
: "${GITHUB_USERNAME:?Set GITHUB_USERNAME as shown in the prerequisites}"
sed -i.bak "s/YOUR_USERNAME/$GITHUB_USERNAME/g" \
  "$COMPONENTS_REPO/agent-platform/argocd/application.yaml"
rm "$COMPONENTS_REPO/agent-platform/argocd/application.yaml.bak"
```

Then commit and open a PR:

```bash
cd "$COMPONENTS_REPO"
git checkout -b agent-platform-initial
git add agent-platform/
git commit -m "chapter 7 lab 1: agent platform"
git push -u origin agent-platform-initial
gh pr create --fill
# Review the PR before merging.
gh pr merge --merge --delete-branch
```

After merging, request an [ApplicationSet refresh](https://argo-cd.readthedocs.io/en/stable/user-guide/annotations-and-labels/) to discover `agent-platform/` without waiting for the polling interval. The generated Application has automatic sync enabled.

The `-w` flag streams updates; press Ctrl-C when the application reaches Synced + Healthy and the pod reaches Running 1/1. Both can be in the same terminal, or you can split into two:

```bash
kubectl -n argocd annotate applicationset backstage-app-discovery \
  argocd.argoproj.io/application-set-refresh=true --overwrite
kubectl -n argocd get applications -l app=agent-platform -w
# Wait until SYNC STATUS is Synced and HEALTH STATUS is Healthy, then Ctrl-C.

kubectl -n agent-platform get pods -w
# agent-runtime-... should reach Running 1/1, then Ctrl-C.
```

If the pod is `ImagePullBackOff`, check the image name and confirm it was loaded into kind.

## Verify the endpoint and memory

This needs two terminals: one to hold the port-forward, one to run `curl`.

**Terminal A — port-forward (leave running):**
```bash
kubectl -n agent-platform port-forward svc/agent-runtime 18080:80
# Forwarding from 127.0.0.1:18080 -> 8080
# (this command does not exit; switch to another terminal)
```

**Terminal B — invoke:**
```bash
curl -s -X POST http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{"intent": "Tell me, in one sentence, who you are and what you cannot do."}' \
  | jq .
```

You should see a response that reflects the identity entries in [configmap-identity.yaml](files/components-repo/agent-platform/k8s/configmap-identity.yaml). Try a follow-up that triggers the `save_to_memory` tool:

```bash
curl -s -X POST http://localhost:18080/invoke \
  -H 'Content-Type: application/json' \
  -d '{"intent": "Remember for future sessions that this user prefers PR titles in lowercase."}' \
  | jq .

# Then inspect MEMORY.md:
kubectl -n agent-platform exec deploy/agent-runtime -- cat /state/memory/MEMORY.md
```

The next invocation loads the saved memory.

## Edit identity through GitOps

Open `$COMPONENTS_REPO/agent-platform/k8s/configmap-identity.yaml`. Change one rule in `SOUL.md` — for example, soften the tone instruction. Open a PR, merge it. ArgoCD updates the ConfigMap. After Kubernetes refreshes the mounted ConfigMap, the next `POST /invoke` reflects the change.

## Troubleshooting

**Pod CrashLoopBackOff with `botocore.exceptions.NoCredentialsError`** — the `agent-llm-credentials` Secret is empty or has the wrong keys. Re-create it with the correct env vars from the credentials section.

**Pod CrashLoopBackOff with `ImportError: ... strands ...`** — the image was built against a different `strands-agents` version. Rebuild with `docker build --no-cache` and reload into kind.

**ArgoCD shows the app as `OutOfSync` and won't auto-sync** — confirm your repo URL in [argocd/application.yaml](files/components-repo/agent-platform/argocd/application.yaml) has `YOUR_USERNAME` replaced. Check `kubectl -n argocd get app agent-platform -o yaml` for the actual error.

**`kubectl exec ... cat MEMORY.md` says `No such file or directory`** — the agent only creates the file the first time `save_to_memory` is invoked. Run an invocation that triggers it first.

Continue to [Lab 2](../2-cluster-diagnostics/README.md).
