> **适用场景**：构建脚本、Docker 镜像、docker-compose、K8s 部署相关任务时

# 构建与部署指南

## 1. 脚本总览

所有操作脚本按用途分三个目录：

```
scripts/
├── local/              # 本地开发环境
│   ├── env-setup.sh    # 环境初始化（一次性）
│   ├── build.sh        # Lint + 生产构建
│   ├── dev.sh          # 启动开发服务器
│   ├── test.sh         # 运行全部测试
│   └── ingest.sh       # 知识库入库
├── docker/             # Docker 镜像与容器编排
│   ├── build.sh        # 构建 CentOS Stream 9 镜像
│   ├── push.sh         # 推送镜像到镜像仓库
│   ├── deploy-compose.sh  # docker-compose 生产部署
│   └── deploy-k8s.sh   # Kubernetes 部署
└── k8s/                # K8s 资源清单（kustomize base）
    ├── 00-namespace.yaml
    ├── 01-configmap.yaml
    ├── 02-secret-template.yaml
    ├── 03-qdrant.yaml
    ├── 04-backend.yaml
    ├── 05-frontend.yaml
    ├── 06-ingress.yaml
    └── kustomization.yaml
```

---

## 2. 本地开发

### 2.1 环境初始化

**前提条件**：Python 3.11、uv、Node.js 20、npm、git

```bash
bash scripts/local/env-setup.sh
```

脚本行为：
1. 检查所有前提条件（`python3.11`、`uv`、`node`、`npm`、`git`）
2. 若 `.env` 不存在，从 `.env.example` 复制创建
3. 执行 `uv sync`（后端依赖）
4. 执行 `npm install`（前端依赖）

> **完成后必须**：编辑 `.env`，填入真实的 `ANTHROPIC_API_KEY`。

### 2.2 知识库入库

```bash
bash scripts/local/ingest.sh                  # 默认 KB 目录（读 .env 中的 KB_DOCS_DIR）
bash scripts/local/ingest.sh --reset          # 清空后重建
bash scripts/local/ingest.sh --kb-dir <路径>  # 指定 KB 目录
```

脚本会自动加载 `.env`，将环境变量传递给 `scripts/ingest_kb.py`。入库结果写入 `knowledge_base/vector_store/`（ChromaDB）和 `*.pkl` 文件（BM25）。

### 2.3 启动开发服务器

```bash
bash scripts/local/dev.sh                # 同时启动后端 + 前端
bash scripts/local/dev.sh --backend-only
bash scripts/local/dev.sh --frontend-only
```

| 服务 | 地址 | 特性 |
|------|------|------|
| 后端 | http://localhost:8000 | `uvicorn --reload`，修改 `app/` 自动重启 |
| 前端 | http://localhost:5173 | Vite HMR，修改 `src/` 即时刷新 |
| API 文档 | http://localhost:8000/docs | FastAPI SwaggerUI |

`CTRL-C` 同时终止两个进程。

### 2.4 Lint 与生产构建

```bash
bash scripts/local/build.sh                    # 全量：lint + type-check + vite build
bash scripts/local/build.sh --skip-lint        # 仅 vite build
bash scripts/local/build.sh --frontend-only    # 跳过后端 ruff
```

构建步骤：
1. `uv tool run ruff check backend/`（后端 lint）
2. `npm run type-check`（TypeScript `tsc --noEmit`）
3. `npm run lint`（ESLint）
4. `npm run build`（Vite 打包 → `frontend/dist/`）

任意步骤失败则以非零退出码退出，适合在 CI 中使用。

### 2.5 运行测试

```bash
bash scripts/local/test.sh                     # 全部测试
bash scripts/local/test.sh --backend-only      # 仅 pytest
bash scripts/local/test.sh --frontend-only     # 仅 tsc + ESLint
bash scripts/local/test.sh -v                  # pytest verbose
```

---

## 3. Docker 镜像（CentOS Stream 9）

### 3.1 镜像设计原则

两个镜像均以 `quay.io/centos/centos:stream9` 为基础：

| 镜像 | Dockerfile | 运行时 |
|------|-----------|--------|
| `hydro-om-backend` | `backend/Dockerfile.centos` | Python 3.11 + Tesseract OCR（中文 + 英文，via EPEL）|
| `hydro-om-frontend` | `frontend/Dockerfile.centos` | CentOS Stream 9 + nginx + gettext（envsubst）|

**多阶段构建**：
- 后端：`builder`（Python 3.11 + gcc）→ `runtime`（无编译工具，减小镜像体积）
- 前端：`builder`（NodeSource Node.js 20）→ `runtime`（仅 nginx + 静态资源）

**安全设计**：
- 所有容器以非 root 用户运行（UID 1001 / GID 0）
- GID 0（root 组）兼容 OpenShift 任意 UID 策略
- 后端设置 `HF_HOME=/app/models`，模型缓存通过 PVC 持久化

### 3.2 前端 nginx 运行时配置

前端镜像使用 `envsubst` 在容器启动时替换 nginx 配置中的 `${BACKEND_URL}`：

```bash
# docker-compose.prod.yml 中
BACKEND_URL=http://backend:8000

# K8s Deployment 中
BACKEND_URL=http://hydro-om-backend:8000
```

`docker-entrypoint.sh` 在 `exec nginx` 前完成替换，无需重新构建镜像即可切换后端地址。

nginx 代理配置要点（`frontend/nginx.conf`）：
- `/` → SPA fallback（`try_files $uri $uri/ /index.html`）
- `/diagnosis/` → 后端 SSE 代理（`proxy_buffering off`，`proxy_read_timeout 300s`）
- `/health` → 后端健康检查代理
- 静态资源：`/assets/` 缓存 1 年（Vite 内容哈希保证唯一性）

---

## 4. Docker 镜像构建

### 4.1 构建

```bash
# 构建全部镜像（后端 + 前端）
bash scripts/docker/build.sh

# 仅构建后端 / 前端
bash scripts/docker/build.sh --backend
bash scripts/docker/build.sh --frontend

# 构建并指定镜像仓库前缀
REGISTRY=registry.example.com/hydro bash scripts/docker/build.sh
```

每次构建自动打三个 tag：

| Tag | 说明 |
|-----|------|
| `<git-sha>` | 不可变 tag，K8s GitOps 首选 |
| `<semver>` | 读自 `backend/pyproject.toml` 的 `version` 字段 |
| `latest` | 可变 tag，docker-compose 开发便捷使用 |

支持 `--cache-from` 加速构建：首次拉取 `latest` 作为构建缓存层。

### 4.2 推送到镜像仓库

```bash
# 推送全部 tag
REGISTRY=registry.example.com/hydro bash scripts/docker/push.sh

# 推送指定 tag
REGISTRY=registry.example.com/hydro IMAGE_TAG=v0.1.0 bash scripts/docker/push.sh
```

脚本会先验证本地镜像是否存在，再执行推送，避免推送到空 tag。

推送前需完成 `docker login <registry>`。

---

## 5. Docker Compose 生产部署

使用 `docker-compose.prod.yml`（与开发用 `docker-compose.yml` 的主要区别见下表）：

| 差异点 | `docker-compose.yml`（开发）| `docker-compose.prod.yml`（生产）|
|--------|--------------------------|--------------------------------|
| 镜像来源 | 本地 `build:` 构建 | 预构建镜像（`image:`）|
| 源码挂载 | 有（热重载）| 无 |
| API_RELOAD | true | false |
| 向量存储 | ChromaDB（本地文件）| Qdrant（独立服务）|
| 端口绑定 | `0.0.0.0` | `127.0.0.1`（仅回环）|
| 模型缓存 | 无 | `models_cache` 命名卷 |
| Qdrant 版本 | `latest` | `v1.11.0`（固定版本）|

```bash
# 启动生产栈
bash scripts/docker/deploy-compose.sh up

# 其他子命令
bash scripts/docker/deploy-compose.sh down
bash scripts/docker/deploy-compose.sh restart
bash scripts/docker/deploy-compose.sh logs
bash scripts/docker/deploy-compose.sh status
bash scripts/docker/deploy-compose.sh ingest   # 在 backend 容器内运行 ingest_kb.py
```

**环境变量**：

```bash
REGISTRY=registry.example.com/hydro   # 镜像仓库前缀
IMAGE_TAG=v0.1.0                       # 部署的镜像 tag（默认 latest）
```

**首次启动顺序**：
1. Qdrant 健康检查通过（15s 内）
2. Backend 启动（含模型下载，首次约 2-10 分钟，后续缓存于 `models_cache` 卷）
3. Frontend 启动（依赖 backend 健康检查通过）

> 后端首次启动会下载约 4GB 的嵌入模型（bge-large-zh-v1.5 + bge-reranker-v2-m3）。
> 下载完成后模型缓存至 `models_cache` 卷，容器重启不需重新下载。

---

## 6. Kubernetes 部署

### 6.1 资源清单结构

```
scripts/k8s/
├── 00-namespace.yaml        namespace: hydro-om
├── 01-configmap.yaml        非敏感运行时配置
├── 02-secret-template.yaml  Secret 模板（不含真实值）
├── 03-qdrant.yaml           StatefulSet + PVC(20Gi) + Service
├── 04-backend.yaml          Deployment(2副本) + PVC×2 + Service
├── 05-frontend.yaml         Deployment(2副本) + Service
├── 06-ingress.yaml          nginx Ingress（分路径路由）
└── kustomization.yaml       Kustomize base
```

### 6.2 首次部署准备

**Step 1**：推送镜像到 Registry（见第 4 节）

**Step 2**：创建 Secret（**不要**提交真实 key 到 Git）

```bash
kubectl create secret generic hydro-om-secrets \
  --namespace hydro-om \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --dry-run=client -o yaml | kubectl apply -f -
```

**Step 3**：（可选）修改 `scripts/k8s/01-configmap.yaml` 中的 `CORS_ORIGINS` 和其他配置。

**Step 4**：（可选）修改 `scripts/k8s/06-ingress.yaml` 中的域名。

### 6.3 执行部署

```bash
REGISTRY=registry.example.com/hydro \
IMAGE_TAG=<git-sha> \
bash scripts/docker/deploy-k8s.sh apply
```

`deploy-k8s.sh` 优先使用 kustomize（若已安装），否则回退到 `envsubst + kubectl apply`，自动替换清单中的 `${REGISTRY}` 和 `${IMAGE_TAG}` 占位符。

### 6.4 常用运维命令

```bash
# 查看所有资源状态
bash scripts/docker/deploy-k8s.sh status

# 等待 Deployment 滚动更新完成
bash scripts/docker/deploy-k8s.sh rollout-status

# 运行知识库入库 Job
bash scripts/docker/deploy-k8s.sh ingest

# 查看后端 Pod 日志
bash scripts/docker/deploy-k8s.sh logs
bash scripts/docker/deploy-k8s.sh logs <pod-name>

# 销毁所有资源（有确认提示）
bash scripts/docker/deploy-k8s.sh delete
```

### 6.5 K8s 架构设计要点

#### 分路径 Ingress 路由

```
客户端请求
  /diagnosis/*  ──→  hydro-om-backend:8000   (SSE 诊断 API)
  /health       ──→  hydro-om-backend:8000   (健康检查)
  /*            ──→  hydro-om-frontend:80    (React SPA)
```

Ingress 注解配置了 `proxy-buffering: off` 和 `proxy-read-timeout: 300`，保证 SSE 长连接正常工作。

#### PVC 策略

| PVC | 挂载路径 | 大小 | 用途 |
|-----|---------|------|------|
| `hydro-om-knowledge-base` | `/app/knowledge_base` | 5Gi | KB 文档 + ChromaDB 索引备份 |
| `hydro-om-models-cache` | `/app/models` | 10Gi | HuggingFace 模型（约 4GB）|
| `qdrant-storage` | `/qdrant/storage` | 20Gi | Qdrant 向量数据 |

`HF_HOME=/app/models` 和 `SENTENCE_TRANSFORMERS_HOME=/app/models` 确保模型权重写入 PVC，避免 Pod 重启后重新下载。

#### 启动探针（startupProbe）

后端首次启动需下载约 4GB 模型，`startupProbe` 配置了 `failureThreshold: 60`（间隔 10s）= 最长 10 分钟启动窗口，后续重启使用缓存，无需等待。

#### 高可用配置

- 后端和前端各 2 副本
- `topologySpreadConstraints` 确保副本分布在不同节点
- 滚动更新：`maxSurge: 1, maxUnavailable: 0`（零停机发布）

#### Kustomize 集成

`scripts/k8s/kustomization.yaml` 定义了 `images:` 块，支持 GitOps 工作流：

```bash
# CI/CD 中更新镜像 tag
kustomize edit set image \
  hydro-om-backend=registry.example.com/hydro/hydro-om-backend:${GIT_SHA} \
  hydro-om-frontend=registry.example.com/hydro/hydro-om-frontend:${GIT_SHA}

# 应用到集群
kustomize build scripts/k8s | kubectl apply -f -
```

---

## 7. 多环境支持（Kustomize Overlay）

当需要 dev / staging / prod 三套配置时，基于 base 创建 overlay：

```
scripts/k8s/
├── base/              # 将现有 *.yaml 移入此目录
│   └── kustomization.yaml
└── overlays/
    ├── staging/
    │   └── kustomization.yaml  # 覆盖副本数、镜像 tag、ConfigMap 差异值
    └── prod/
        └── kustomization.yaml
```

`overlays/prod/kustomization.yaml` 示例：

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- ../../base
namespace: hydro-om-prod
images:
- name: hydro-om-backend
  newName: registry.example.com/hydro/hydro-om-backend
  newTag: "v1.0.0"
- name: hydro-om-frontend
  newName: registry.example.com/hydro/hydro-om-frontend
  newTag: "v1.0.0"
patches:
- target:
    kind: Deployment
    name: hydro-om-backend
  patch: |-
    - op: replace
      path: /spec/replicas
      value: 3
```

---

## 8. CI/CD 集成参考

典型 GitHub Actions 流程（`.github/workflows/build-deploy.yml`，待实现）：

```
push to main
  → test.sh (backend + frontend)
  → build.sh (lint + type-check + vite build)
  → scripts/docker/build.sh (构建镜像，tag = git sha)
  → scripts/docker/push.sh  (推送到 registry)
  → scripts/docker/deploy-k8s.sh apply (部署到 staging)
  → 人工审批
  → scripts/docker/deploy-k8s.sh apply (部署到 prod)
```

环境变量在 CI 中通过 Secrets 注入：
- `REGISTRY`：镜像仓库地址
- `ANTHROPIC_API_KEY`：通过 `kubectl create secret` 预先配置，CI 不需要感知
- `KUBE_CONTEXT`：目标集群的 kubeconfig context

---

## 9. 常见问题

**Q: 后端容器启动超时（健康检查失败）**

首次启动需下载约 4GB 模型权重。docker-compose 的 `start_period: 120s` 和 K8s 的 `startupProbe.failureThreshold: 60` 提供了最长等待窗口。若网络较慢，可增大这两个值。

挂载 `models_cache`/`hydro-om-models-cache` PVC 后，后续重启秒级完成（模型已缓存）。

**Q: SSE 流在生产环境中断**

检查反向代理配置：
- nginx Ingress：确认 `nginx.ingress.kubernetes.io/proxy-buffering: "off"` 和 `proxy-read-timeout: "300"`
- 前端 nginx：`proxy_buffering off` + `proxy_read_timeout 300s` 已包含在 `frontend/nginx.conf`

**Q: 镜像 pull 失败（K8s）**

确认 `imagePullSecrets` 或节点的 registry 认证配置。若使用私有 registry：

```bash
kubectl create secret docker-registry registry-creds \
  --docker-server=registry.example.com \
  --docker-username=<user> \
  --docker-password=<token> \
  --namespace hydro-om
```

并在 `04-backend.yaml` / `05-frontend.yaml` 的 `spec.template.spec` 中添加：

```yaml
imagePullSecrets:
- name: registry-creds
```

**Q: Qdrant 数据在 Pod 重启后丢失**

确认 PVC `qdrant-storage` 已绑定到一个支持持久化的 StorageClass。若使用 HostPath（仅单节点测试），Pod 调度到其他节点后数据不可访问。生产环境使用支持 RWO 的网络存储（Ceph RBD、AWS EBS 等）。

**Q: 知识库入库 Job 失败**

```bash
# 查看 Job 日志
kubectl get pods -n hydro-om -l app.kubernetes.io/component=ingest
kubectl logs -n hydro-om <ingest-pod-name>
```

常见原因：Qdrant 未就绪、`ANTHROPIC_API_KEY` 未配置（入库不调用 LLM，此项不影响入库）、`KB_DOCS_DIR` 路径错误（确认 PVC 已挂载且目录存在）。
