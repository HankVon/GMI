# 项目服务器部署文档（鲲鹏 920s + Atlas 300I Duo 国产硬件架构 · Ubuntu 版）

> 适用项目：**GMI / SSM 地质营销情报数据平台**（FastAPI 后端 + Vue/TS 前端 + MySQL/Redis/Neo4j + Crawl4AI 抓取服务 + 图检索生成 qwen-graphrag）
> 目标服务器：**国产 ARM64（aarch64）架构** —— 鲲鹏 920s + 华为昇腾 Atlas 300I Duo 推理卡
> 操作系统：**Ubuntu Server 22.04 / 24.04 LTS（aarch64）**
> 文档定位：从裸机到全栈上线 + 故障排查，所有步骤按国产硬件（aarch64 + 昇腾 CANN）与 Ubuntu 适配。

---

## 0. 目标硬件与架构适配要点

### 0.1 硬件配置（部署目标机）

| 部件 | 规格 | 部署影响 |
|---|---|---|
| CPU | 鲲鹏 920s ×2（共 64 核 / aarch64） | 全部软件必须 **arm64/aarch64** 版本；Docker 镜像须含 `linux/arm64` manifest |
| 内存 | 128 GB DDR4 ECC | 可大幅上调 MySQL/Neo4j 缓冲；NPU 推理不占系统内存（卡显存独立 96G×4） |
| 硬盘 | 1 × 1.92 TB SSD（单盘，无 RAID） | 系统 + Docker + 模型权重 + 业务数据同盘，需合理分区；重要数据另做异地备份 |
| AI 加速卡 | 4 × Atlas 300I Duo（每卡双芯 Ascend 310P3，96 GB 卡显存） | 共 **8 个 NPU 设备**（`/dev/davinci0`~`/dev/davinci7`）；需昇腾驱动 + CANN；推理服务用 MindIE |
| 电源 | 1250 W 80 Plus | 64 核 CPU（≈180W）+ 4 卡（单卡峰值≈150W，合计≈600W）余量充足；建议接 UPS |

### 0.2 软件栈与容器编排总览

```
                           ┌──────────────────────────────────────────┐
   浏览器 / 远程访问 ──────▶│  前端 (nginx, :8080)  → 反代 /api 到 backend │
                           └───────────────┬──────────────────────────┘
                                            │  /api
                           ┌───────────────▼──────────────────────────┐
                           │  backend (FastAPI, :8100→8000)            │
                           │   ├─ MySQL 3306   ├─ Redis 6379           │
                           │   ├─ Neo4j 7687   ├─ Crawl4AI :11235      │
                           │   └─ LLM 推理(MindIE, :1025 OpenAI兼容)   │
                           └───────────────────────────────────────────┘
                                            │
              ┌─────────────────────────────┼──────────────────────────────┐
              ▼                             ▼                              ▼
        [MySQL 容器]                [Neo4j 容器]              [MindIE 容器 /dev/davinci0-7]
        [Redis 容器]                [Crawl4AI 容器]          (4×Atlas 300I Duo, 8 芯)
```

### 0.3 国产架构适配要点（必读）

1. **操作系统选 arm64 发行版**：推荐 **Ubuntu Server 22.04 LTS 或 24.04 LTS（aarch64）**——鲲鹏 920 官方支持 Ubuntu Server arm64，社区与文档丰富、Docker/容器生态完整；可选 openEuler 22.03/24.03 LTS、麒麟 V10 SP3。本文档按 **Ubuntu** 编写。
2. **所有容器镜像必须为 aarch64**：本项目现有 `mysql:8.0`、`redis:7-alpine`、`neo4j:*`、`python:3.12-slim`、`node:20-alpine`、`nginx:1.27-alpine` 均为多架构镜像，鲲鹏上自动拉 `arm64`，无需改动；唯 **Neo4j 需确认所用 tag 含 `linux/arm64`**（5.x 起官方支持，推荐 `neo4j:5.23.0+`）。
3. **AI 加速卡走昇腾 CANN 软件栈**：Atlas 300I Duo = 双芯 Ascend 310P3，驱动包名为 `Ascend-hdk-310p-npu-*`，推理用 **MindIE**（提供 OpenAI 兼容接口），替代原 Windows 上的 Ollama/qwen-graphrag。MindIE 推理**容器**的底层镜像（如 openEuler 24.03）与宿主机 Ubuntu **相互独立**，不影响宿主机。
4. **内核版本锁定**：昇腾驱动按当前内核头文件编译内核模块，系统自动升级内核会导致驱动失效 → 必须锁内核（见 §2.1）。

---

## 1. 环境准备

### 1.1 操作系统安装（Ubuntu Server 22.04/24.04 LTS aarch64）

- 镜像：`ubuntu-22.04.5-live-server-arm64.iso` 或 `ubuntu-24.04-live-server-arm64.iso`（从 ubuntu.com 或清华/中科大镜像站下载）。
- 安装模式：**Minimal（最小化）** 即可，后续用 `apt` 补包。
- 分区建议（单 1.92T SSD，无硬件 RAID；Ubuntu 默认 ext4，xfs 可选）：

| 挂载点 | 大小 | 文件系统 | 说明 |
|---|---|---|---|
| `/` | 100 GB | ext4 | 系统根 |
| `/var/lib/docker` | 400 GB | ext4/xfs | Docker 镜像/卷（业务容器全在此） |
| `/data` | 剩余 ≈ 1.3 TB | ext4/xfs | 模型权重、上传文件、数据库备份、项目代码 |
| `swap` | 8 GB | swap | 128G 物理内存可不设，留 8G 防极端 OOM |

> 对 `/var/lib/docker`、`/data` 启用 `noatime` 挂载选项，减少 SSD 写放大。
> 安装时在 "Storage configuration" 里把 `/var/lib/docker`、`/data` 单独建为逻辑挂载点（或装完后用 `mkdir` + 改 `/etc/fstab` 迁移）。

- BIOS/UEFI：开启 **Above 4G Decoding / PCIe 64-bit BAR**（Atlas 卡需要足够 BAR 空间，否则可能掉卡）；关闭 Secure Boot（昇腾驱动 ko 未签名）。

### 1.2 基础系统配置

```bash
# 主机名与 hosts
sudo hostnamectl set-hostname gmi-server
echo "127.0.0.1 gmi-server" | sudo tee -a /etc/hosts

# 时区 + 时间同步（数据库/日志一致性必须）
sudo timedatectl set-timezone Asia/Shanghai
sudo apt-get install -y chrony
sudo systemctl enable --now chrony

# 字符集（中文）
sudo apt-get install -y locales
sudo locale-gen zh_CN.UTF-8
sudo update-locale LANG=zh_CN.UTF-8

# 防火墙：Ubuntu 用 ufw（生产建议开启，按需放行端口，见 §3.2）
sudo apt-get install -y ufw
sudo ufw --force enable

# AppArmor：Ubuntu 默认启用，但 Docker 与昇腾驱动在 AppArmor 下无已知冲突，
# 无需禁用；如确需排查，可临时 setenforce 类操作不适用（Ubuntu 无 SELinux）。
```

### 1.3 创建运行用户与组

```bash
# 部署用户（执行 docker、放代码）
sudo useradd -m -s /bin/bash deploy
sudo usermod -aG docker deploy

# 昇腾 NPU 运行用户/组（驱动与推理服务默认运行用户，必须创建）
sudo groupadd HwHiAiUser
sudo useradd -g HwHiAiUser -d /home/HwHiAiUser -m HwHiAiUser -s /bin/bash
```

---

## 2. 依赖安装

### 2.1 基础工具与编译依赖（驱动/CANN 前置）

```bash
sudo apt-get update
sudo apt-get install -y vim wget curl git build-essential \
  linux-headers-$(uname -r) linux-generic \
  dkms elfutils-libelf-dev libssl-dev tar bzip2 \
  python3 python3-venv python3-pip   # 系统 Python 仅用于运维脚本；业务走容器

# 锁内核版本（关键！防止后续升级内核导致 NPU 驱动失效）
sudo apt-mark hold linux-image-$(uname -r) linux-headers-$(uname -r) linux-generic
# 校验：apt-mark showhold   应列出上述包
```

### 2.2 Docker CE（aarch64 / Ubuntu）

**方式 A（推荐，apt 官方源）：**

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

**方式 B（便捷脚本，离线/快速）：**

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh    # 自动识别 aarch64，安装 docker-ce + compose-plugin
```

完成后：

```bash
sudo systemctl enable --now docker
docker version   # 确认 Server.Architecture = aarch64
docker compose version   # 确认 v2 插件可用
```

> 备选（纯离线二进制）：从 `https://download.docker.com/linux/static/stable/aarch64/` 下载 `docker-<ver>.tgz` 解压到 `/usr/bin`，并下载 `docker-compose-linux-aarch64` 到 `/usr/local/bin/docker-compose`。

### 2.3 配置 Docker（镜像加速 + 日志 + 存储路径）

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://hub-mirror.c.163.com"
  ],
  "exec-opts": ["native.cgroupdriver=systemd"],
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "3" },
  "data-root": "/var/lib/docker"
}
EOF
sudo systemctl daemon-reload && sudo systemctl restart docker
```

### 2.4 确认 arm64 镜像可拉取

```bash
docker run --rm hello-world     # 自动拉 linux/arm64
docker pull --platform=linux/arm64 mysql:8.0
docker pull --platform=linux/arm64 redis:7-alpine
docker pull --platform=linux/arm64 neo4j:5.23.0
```

### 2.5 Python 依赖（宿主机运维用，可选装 venv）

```bash
python3 -m venv /opt/venv
source /opt/venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pymysql
```

---

## 3. 系统配置

### 3.1 内核与资源参数

```bash
# 进程数/线程数上限（昇腾与多 worker 后端需要）
cat >> /etc/profile <<'EOF'
ulimit -u unlimited
ulimit -n 65535
EOF
source /etc/profile

# 系统级
sudo tee -a /etc/security/limits.conf > /dev/null <<'EOF'
* soft nofile 65535
* hard nofile 65535
* soft nproc  unlimited
* hard nproc  unlimited
EOF

# 共享内存（Crawl4AI/Playwright 与部分推理组件用到 /dev/shm）
sudo mount -o remount,size=4G /dev/shm
echo "tmpfs /dev/shm tmpfs defaults,size=4G 0 0" | sudo tee -a /etc/fstab
```

> **NPU 大页内存**：Atlas 300I Duo 推理通常不需要手动配 hugepages（`npu-smi info` 中的 Hugepages-Usage 由驱动自动管理）；若 MindIE 启动报 contiguous memory 不足，再按昇腾文档配置 2MB/1GB 大页。

### 3.2 防火墙端口规划（ufw）

| 端口 | 服务 | 对外 | 说明 |
|---|---|---|---|
| 22 | SSH | 是 | 运维；建议改非默认端口 + 密钥登录 |
| 8080 | 前端（nginx） | 是 | 用户访问入口，建议前置 Nginx/反代 + HTTPS |
| 8100 | backend | 否（容器映射） | 仅前端容器访问；如直连需放行 |
| 3306 | MySQL | 否 | 仅容器网络 |
| 6379 | Redis | 否 | 仅容器网络 |
| 7474 / 7687 | Neo4j | 否 | 仅容器网络（7687 为 bolt） |
| 11235 | Crawl4AI | 否 | 仅 backend 容器访问 |
| 1025 | MindIE（LLM） | 否 | 仅 backend 容器访问（OpenAI 兼容） |

```bash
sudo ufw allow 22/tcp
sudo ufw allow 8080/tcp
sudo ufw status    # 确认规则已加载
# 注意：容器间通信走 docker0 桥，ufw 默认不阻断；容器内端口无需逐个放行
```

### 3.3 目录规划

```bash
sudo mkdir -p /data/gmi /data/gmi/uploads /data/gmi/runtime/logs \
         /data/models /data/backups
sudo chown -R deploy:deploy /data/gmi
# 项目代码放置：/data/gmi/GMI
```

---

## 4. 项目部署步骤

### 4.1 获取代码

```bash
su - deploy
cd /data/gmi
git clone https://github.com/HankVon/GMI.git GMI
cd GMI && git log --oneline -1   # 确认分支与版本
```

### 4.2 凭据与 `.env`（跨机一致性铁律）

本项目 SECRET_KEY、MySQL/Neo4j 口令在双机间必须一致（否则登录态/加解密不互通）。沿用既有值（见 `docs/unit-machine-setup.md` 铁律表），**不要重新生成 SECRET_KEY**。

```bash
# compose 同级 .env（docker compose 读取）
cat > /data/gmi/GMI/.env <<'EOF'
SECRET_KEY=<沿用既有 SECRET_KEY>
EOF

# backend/.env
cat > /data/gmi/GMI/backend/.env <<'EOF'
SECRET_KEY=<沿用既有 SECRET_KEY>
NEO4J_PASSWORD=ssm_neo4j_2026
EOF
```

> 生产建议：口令改为强随机值，并与家里机同步；本文件已 gitignore，勿提交。

### 4.3 适配后的 `docker-compose.yml`

以下为国产服务器用的编排（相对原 Windows 版主要改动：AI 推理改为 MindIE 容器；Crawl4AI 容器化；Ollama 环境变量改为 LLM OpenAI 兼容端点）。保存为 `docker-compose.server.yml`：

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: ssm-mysql
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: root_password
      MYSQL_DATABASE: ssm
      MYSQL_USER: ssm_user
      MYSQL_PASSWORD: ssm_pass
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --default-authentication-plugin=mysql_native_password
      - --innodb_buffer_pool_size=12G        # 128G 内存上调
    ports: ["3306:3306"]
    volumes: ["mysql_data:/var/lib/mysql", "./sql:/docker-entrypoint-initdb.d"]
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s; timeout: 5s; retries: 5

  redis:
    image: redis:7-alpine
    container_name: ssm-redis
    restart: unless-stopped
    command: ["redis-server", "--maxmemory", "4gb", "--maxmemory-policy", "allkeys-lru"]
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]; interval: 5s; timeout: 3s; retries: 5

  neo4j:
    image: neo4j:5.23.0            # 确认含 linux/arm64 manifest
    container_name: ssm-neo4j
    restart: unless-stopped
    environment:
      NEO4J_AUTH: neo4j/ssm_neo4j_2026
      NEO4J_dbms_memory_heap_initial__size: "4g"
      NEO4J_dbms_memory_heap_max__size: "4g"
      NEO4J_dbms_memory_pagecache_size: "8g"
      NEO4J_dbms_memory_transaction_total_max: "4g"
    ports: ["7474:7474", "7687:7687"]
    volumes: ["neo4j_data:/data", "neo4j_logs:/logs"]
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:7474"]
      interval: 10s; timeout: 5s; retries: 10

  backend:
    build: { context: ./backend, dockerfile: Dockerfile }
    container_name: ssm-backend
    restart: unless-stopped
    environment:
      DATABASE_URL: mysql+pymysql://ssm_user:ssm_pass@mysql:3306/ssm?charset=utf8mb4
      REDIS_URL: redis://redis:6379/0
      NEO4J_URI: neo4j://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: ssm_neo4j_2026
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: "false"
      PORT: "8000"
      CORS_ORIGINS: "http://localhost:8080,http://<服务器IP>:8080"
      # ↓↓↓ 关键改造：由 Ollama 改为 MindIE OpenAI 兼容端点（见 §5.7 / §5.8）
      LLM_PROVIDER: openai
      OPENAI_BASE_URL: http://llm:1025/v1
      OPENAI_API_KEY: "EMPTY"
      OPENAI_MODEL: "qwen-graphrag"
      CRAWL4AI_API_URL: "http://crawl4ai:11235"
    extra_hosts: ["host.docker.internal:host-gateway"]
    ports: ["8100:8000"]
    volumes: ["./sql:/sql:ro", "./uploads:/app/uploads", "./runtime/logs:/app/logs"]
    depends_on:
      mysql: { condition: service_healthy }
      redis: { condition: service_healthy }
      neo4j: { condition: service_healthy }

  frontend:
    build: { context: ./frontend, dockerfile: Dockerfile }   # nginx 版，生产推荐
    container_name: ssm-frontend
    restart: unless-stopped
    ports: ["8080:80"]
    depends_on: [backend]

  crawl4ai:
    build: { context: ./crawl4ai-server, dockerfile: Dockerfile }   # 见 §4.5
    container_name: ssm-crawl4ai
    restart: unless-stopped
    environment:
      CRAWL4AI_PORT: "11235"
    ports: ["11235:11235"]
    # Playwright 无头浏览器需要 --no-sandbox（代码已设）；共享内存上调
    shm_size: "2gb"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11235/health"]
      interval: 15s; timeout: 5s; retries: 5

  llm:
    # 推理容器底层镜像为 openEuler 24.03 —— 与宿主机 Ubuntu 相互独立，不影响系统
    image: swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:3.0.0-300I-Duo-py311-openeuler24.03-lts
    container_name: ssm-mindie
    restart: unless-stopped
    network_mode: "host"            # MindIE 官方镜像用 host 网络最简
    # ↓↓↓ 4 卡 = 8 个 NPU 设备全部透传 ↓↓↓
    devices:
      - /dev/davinci0
      - /dev/davinci1
      - /dev/davinci2
      - /dev/davinci3
      - /dev/davinci4
      - /dev/davinci5
      - /dev/davinci6
      - /dev/davinci7
      - /dev/davinci_manager
      - /dev/devmm_svm
      - /dev/hisi_hdc
    volumes:
      - /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro
      - /usr/local/dcmi:/usr/local/dcmi:ro
      - /usr/local/bin/npu-smi:/usr/local/bin/npu-smi:ro
      - /data/models:/data/models:ro
    # 启动命令在镜像内默认拉起 mindieservice；配置见 §5.7
    healthcheck:
      test: ["CMD", "curl", "-f", "http://127.0.0.1:1025/v1/models"]
      interval: 30s; timeout: 5s; retries: 10

volumes:
  mysql_data:
  redis_data:
  neo4j_data:
  neo4j_logs:
```

> **注**：`llm` 服务用 `network_mode: host`，故 backend 通过 `http://llm:1025` 解析需在 host 网络下可用；若 backend 在 bridge 网络无法直接解析 host 名，可将 backend 的 `OPENAI_BASE_URL` 改为 `http://host.docker.internal:1025/v1`（已配 `extra_hosts`）。两种写法二选一。

### 4.4 后端/前端镜像适配（arm64）

- `backend/Dockerfile` 用 `python:3.12-slim`（多架构，自动 arm64），无需改；构建时确认 `pip` 走国内源（已写清华源）。
- `frontend/Dockerfile` 用 `node:20-alpine` + `nginx:1.27-alpine`（多架构），无需改。
- 后端资源：64 核机器建议 uvicorn 多 worker。在 `backend/Dockerfile` 的 CMD 改为：
  ```
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "8"]
  ```

### 4.5 Crawl4AI 服务容器化（`crawl4ai-server/Dockerfile`）

在 `crawl4ai-server/` 下新建 `Dockerfile`（CPU 推理，aarch64 上 Playwright Chromium 与 onnxruntime 均有 arm64 支持）：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ffmpeg fonts-liberation libnss3 libatk-bridge2.0-0 \
    libgtk-3-0 libgbm1 libasound2 && rm -rf /var/lib/apt/lists/*
# Playwright 浏览器（arm64 chromium）
RUN pip install --no-cache-dir playwright -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    playwright install chromium && playwright install-deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
EXPOSE 11235
CMD ["uvicorn", "crawl4ai_server:app", "--host", "0.0.0.0", "--port", "11235"]
```

`crawl4ai-server/requirements.txt` 内容：
```
fastapi
uvicorn[standard]
crawl4ai
playwright
ddddocr
httpx
```

### 4.6 启动与初始化

```bash
cd /data/gmi/GMI
docker compose -f docker-compose.server.yml up -d --build
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f backend   # 看 Application startup complete
```

- 后端启动会自动跑迁移（建表补列），无需手动 alembic。
- 首次导入业务字典：`docker compose exec backend python -m alembic upgrade head`（如项目用 alembic；否则依赖启动自动迁移）。

### 4.7 数据迁移（已有数据，一次性）

```bash
# MySQL
docker compose -f docker-compose.server.yml exec -T mysql \
  mysql -ussm_user -pssm_pass ssm < migrate_in/ssm_mysql.sql

# Neo4j（先 docker cp 把 dump 放进容器 /import，再 load）
docker cp migrate_in/neo4j.dump ssm-neo4j:/import/neo4j.dump
docker compose -f docker-compose.server.yml exec neo4j \
  neo4j-admin database load neo4j --from=/import/neo4j.dump --overwrite-destination
docker compose -f docker-compose.server.yml restart neo4j
```

---

## 5. AI 加速卡驱动与环境配置（Atlas 300I Duo ×4）

> 本节是国产硬件核心。Atlas 300I Duo = 双芯 **Ascend 310P3**，4 张卡共 **8 个 NPU**。本节除 MindIE 推理容器（其内部为 openEuler 基础镜像）外，全部运行于 Ubuntu 宿主机。

### 5.1 硬件识别

```bash
lspci -nn | grep -i "19e5"        # 华为昇腾 PCIe 设备，应看到 4 张卡（每张双芯）
ls /dev/davinci*                  # 装驱动后才出现；预期 davinci0~7 + davinci_manager 等
```

### 5.2 下载软件包（华为昇腾社区，选 AArch64 / run 格式）

从 https://www.hiascend.com/hardware/firmware-drivers 选择：
- 产品系列：加速卡 → 产品型号：**Atlas 300I Duo 推理卡**
- CPU 架构：**AArch64**；软件包格式：**run**

所需包（版本以官网当期为准，示例 25.5.2 / 7.8.0.7.220）：

| 包 | 作用 |
|---|---|
| `Ascend-hdk-310p-npu-driver_<ver>_linux-aarch64.run` | NPU 驱动（必须） |
| `Ascend-hdk-310p-npu-firmware_<ver>.run` | 固件（必须） |
| `Ascend-cann-toolkit_<ver>_linux-aarch64.run` | CANN 开发套件（模型转换/编译） |
| `Ascend-cann-kernels-310P_<ver>_linux-aarch64.run` | 310P 算子内核库 |
| `Ascend-cann-nnal_<ver>_linux-aarch64.run` | 神经网络加速库（ATB，大模型推理加速） |

### 5.3 安装驱动与固件（安装顺序：先驱动后固件）

```bash
# 前置（§2.1 已装 kernel-headers/dkms/gcc）
chmod +x Ascend-hdk-310p-npu-driver_25.5.2_linux-aarch64.run
chmod +x Ascend-hdk-310p-npu-firmware_7.8.0.7.220.run
sudo ./Ascend-hdk-310p-npu-driver_25.5.2_linux-aarch64.run --full --install-for-all
sudo ./Ascend-hdk-310p-npu-firmware_7.8.0.7.220.run --full
sudo reboot     # 固件升级后必须重启生效
```

> ⚠️ **安装过程中绝对禁止对主机或设备复位/下电**，否则设备可能变砖（官方警告）。
> 覆盖升级顺序相反（先固件后驱动）。

### 5.4 安装 CANN 软件栈

```bash
chmod +x Ascend-cann-toolkit_8.0.0_linux-aarch64.run
chmod +x Ascend-cann-kernels-310P_8.0.0_linux-aarch64.run
chmod +x Ascend-cann-nnal_8.0.0_linux-aarch64.run
sudo ./Ascend-cann-toolkit_8.0.0_linux-aarch64.run --upgrade
sudo ./Ascend-cann-kernels-310P_8.0.0_linux-aarch64.run --upgrade
sudo ./Ascend-cann-nnal_8.0.0_linux-aarch64.run --upgrade
```

### 5.5 环境变量（写入 `/etc/profile.d/ascend.sh`）

```bash
sudo tee /etc/profile.d/ascend.sh > /dev/null <<'EOF'
export ASCEND_HOME=/usr/local/Ascend
export LD_LIBRARY_PATH=${ASCEND_HOME}/driver/lib64:${ASCEND_HOME}/ascend-toolkit/latest/lib64:${LD_LIBRARY_PATH}
export PYTHONPATH=${ASCEND_HOME}/ascend-toolkit/latest/python/site-packages:${PYTHONPATH}
export PATH=${ASCEND_HOME}/bin:${ASCEND_HOME}/ascend-toolkit/latest/bin:${PATH}
EOF
source /etc/profile.d/ascend.sh
```

> 若用 MindIE 容器（§5.7），容器内已自带 toolkit/nnal 环境，只需把宿主机 `/usr/local/Ascend/driver` 挂进容器（compose `llm` 服务已配）。

### 5.6 验证驱动与设备

```bash
npu-smi info
# 应显示 8 个 Chip（Device 0~7），Health = OK，Memory-Usage 正常
# 若为升级，另用 upgrade-tool 核对 6 个组件版本一致
ascend-dmi -i          # 设备与接口检查（可选）
```

### 5.7 大模型推理服务部署（MindIE，4 卡 8 芯）

使用华为云 SWR 提供的 300I-Duo 专用镜像（已内置 toolkit/nnal/atb-models；其基础镜像为 openEuler 24.03，与宿主机 Ubuntu 互不干扰）：

```bash
docker pull --platform=linux/arm64 \
  swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:3.0.0-300I-Duo-py311-openeuler24.03-lts
```

该服务由 `docker-compose.server.yml` 的 `llm` 服务拉起（已透传 8 张 NPU + driver 卷）。进入容器配置：

```bash
docker exec -it ssm-mindie bash
cd /usr/local/Ascend/mindie/latest/mindie-service/conf
vi config.json
```

关键参数（4 卡 = 8 芯，`worldSize` 与 `npuDeviceIds` 数量对应）：

```json
{
  "ServerConfig": {
    "ipAddress": "0.0.0.0",
    "port": 1025,
    "managementIpAddress": "127.0.0.2",
    "managementPort": 1026,
    "metricsPort": 1027,
    "httpsEnabled": false,
    "openAiSupport": "vllm"
  },
  "BackendConfig": {
    "npuDeviceIds": [[0,1,2,3,4,5,6,7]],
    "ModelDeployConfig": {
      "ModelConfig": [
        {
          "modelName": "qwen-graphrag",
          "modelWeightPath": "/data/models/qwen-graphrag",
          "worldSize": 8,
          "trustRemoteCode": false
        }
      ]
    }
  }
}
```

权限修正后启动：

```bash
cd /usr/local/Ascend/mindie/latest/mindie-service
chmod 750 mindie-service && chmod -R 550 mindie-service/bin mindie-service/lib
nohup ./bin/mindieservice_daemon > output.log 2>&1 &
# 看到 "Daemon start success!" 即成功；OpenAI 兼容端点 http://<host>:1025/v1
```

### 5.8 与后端集成（替代 Ollama/qwen-graphrag）

原 Windows 版 backend 通过 `OLLAMA_BASE_URL` + `OLLAMA_MODEL=qwen-graphrag:latest` 调用图检索生成。在国产服务器改为：

1. 在 `docker-compose.server.yml` 的 `backend` 环境中设置：
   - `LLM_PROVIDER=openai`
   - `OPENAI_BASE_URL=http://llm:1025/v1`（或 `host.docker.internal:1025/v1`）
   - `OPENAI_API_KEY=EMPTY`
   - `OPENAI_MODEL=qwen-graphrag`
2. **后端代码改动点**（唯一必需代码适配）：将 graphrag 调用从 Ollama 客户端改为 OpenAI 兼容客户端（如 `openai` Python SDK 或 LangChain `ChatOpenAI`），`base_url` 读取上述环境变量。MindIE 的 `/v1/chat/completions` 与 `/v1/embeddings` 兼容 OpenAI 协议，前端无感。
3. 模型权重：将 `qwen-graphrag` 权重放到宿主机 `/data/models/qwen-graphrag`，并把 `config.json` 的 `torch_dtype` 设为 `float16`（310P 推荐）。权限 `chmod -R 755 /data/models/qwen-graphrag`。

> **性能要点**：310P 上 vLLM/MindIE 的 `max-model-len` 必须显式限制（如 16384），否则自动检测偏大导致 OOM；多芯用张量并行 `worldSize` 对齐芯片数（此处 8）。

---

## 6. 服务启动与验证

### 6.1 启动全部

```bash
cd /data/gmi/GMI
docker compose -f docker-compose.server.yml up -d
docker compose -f docker-compose.server.yml ps
```

### 6.2 健康检查清单

| 组件 | 验证命令 | 期望 |
|---|---|---|
| 后端 | `curl http://localhost:8100/api/v1/health` | `{"status":"ok",...}` |
| 前端 | 浏览器开 `http://<IP>:8080` | 加载登录页 |
| MySQL | `docker exec ssm-mysql mysqladmin ping` | `mysqld is alive` |
| Redis | `docker exec ssm-redis redis-cli ping` | `PONG` |
| Neo4j | 浏览器 `http://<IP>:7474` | 登录页 |
| Crawl4AI | `curl http://localhost:11235/health` | `{"status":"ok"}` |
| MindIE(NPU) | `curl http://localhost:1025/v1/models` | 返回模型列表；`npu-smi info` 8 芯 OK |
| 磁盘 | `df -h /data /var/lib/docker` | 使用率正常 |

### 6.3 端到端验证

```bash
# 登录
curl -X POST http://localhost:8100/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
# 用返回 token 调业务接口；另触发一次图检索生成，确认走 MindIE(:1025) 而非 Ollama
```

### 6.4 前端访问与 HTTPS（生产）

- 生产建议在宿主机前置 Nginx（或 Traefik）做 80→443 跳转 + TLS，反向代理到 `localhost:8080`。
- 前端容器内部 nginx 已配置 `/api` 反代到 backend（同源，无 CORS）。

### 6.5 开机自启

各服务 `restart: unless-stopped` 已覆盖容器自启；宿主机需确保 Docker 自启：

```bash
sudo systemctl enable --now docker
```

如需在 Docker 启动后自动拉起 compose，推荐写 systemd unit（Ubuntu 下比 `rc.local` 更可靠）：

```bash
sudo tee /etc/systemd/system/gmi-compose.service > /dev/null <<'EOF'
[Unit]
Description=GMI docker compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/data/gmi/GMI
ExecStart=/usr/bin/docker compose -f docker-compose.server.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.server.yml down

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable gmi-compose.service
```

---

## 7. 常见故障排查

### 7.1 NPU / 昇腾

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `lspci` 找不到 `19e5` 设备 | PCIe 未识别 / BIOS 未开 64-bit BAR | 检查卡槽与 BIOS Above 4G Decoding；重插 |
| `npu-smi info` 无输出 / 报错 | 驱动未装或内核升级后 ko 失效 | 重装驱动；确认内核被锁定（§2.1）；`sudo reboot` |
| 驱动编译报 `rebuild ko has something wrong` | 未装 `linux-headers`/`dkms` | 装好后重跑 `--full`；或安装时输入内核源码绝对路径 |
| HwHiAiUser 无权访问 NPU（容器以普通用户跑） | 容器运行用户非 root 且无权限 | 容器以 root 运行，或设运行 UID=0（如 GPUStack `GPUSTACK_MODEL_RUNTIME_UID=0`） |
| MindIE 启动 `Illegal instruction (core dumped)` | 镜像二进制用了新 CPU 指令集（多见于 x86 老 CPU 跑错镜像） | 用 300I-Duo 专用镜像（arm64），不要混用 x86 镜像 |
| 推理 OOM | `max-model-len` 自动检测偏大 | 显式设 `--max-model-len 16384`；`npuMemSize: -1` 自动 |
| 内核升级后驱动失效 | 自动更新内核 | §2.1 锁内核（`apt-mark hold`）；或重装驱动 |
| 固件升级后未生效 | 没重启 | 重启后 `npu-smi info` 复核 6 组件版本 |

### 7.2 容器 / arm64 / Ubuntu

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `no matching manifest for linux/arm64` | 镜像无 arm64 版本 | 换多架构镜像或指定 `--platform=linux/arm64`；Neo4j 换 5.23.0+ |
| compose 拉镜像慢 | 境外源 | 配 `registry-mirrors`（§2.3） |
| Playwright 在容器内崩 | 缺系统库 / 未 `--no-sandbox` | `playwright install-deps`；代码已 `--no-sandbox`；`shm_size` 上调 |
| 后端连不上 `llm` / `crawl4ai` | 服务名解析 / host 网络 | `llm` 用 host 网络时 backend 改用 `host.docker.internal:1025` |
| ufw 误拦容器流量 | 规则过严 | 容器走 docker0 桥，默认不在 ufw 管控；仅放行业务暴露端口（22/8080） |
| `apt upgrade` 想升级内核被阻止 | 已 `apt-mark hold` | 正常；如需升级先 `apt-mark unhold` 再升级并重装驱动 |

### 7.3 数据库 / 后端

| 现象 | 可能原因 | 处理 |
|---|---|---|
| backend 起不来 / `SECRET_KEY` 空 | compose 同级 `.env` 缺 `SECRET_KEY` | 补 `docker-compose.server.yml` 同级 `.env` |
| 接口报缺表/缺列 | 迁移未跑 | 后端启动自动迁移；或 `alembic upgrade head` |
| 家里机连 CORS 报错 | `CORS_ORIGINS` 不含前端地址 | backend 环境加 `http://<IP>:8080` 后重启 |
| 端口被占用 | 旧进程 / 系统保留 | `ss -ltnp | grep 8100`；停旧进程 |

### 7.4 性能调优提示

- MySQL `innodb_buffer_pool_size=12G`（128G 内存下）；Neo4j heap 4G + pagecache 8G。
- backend uvicorn `--workers 8`（64 核，留余量给 DB/推理）。
- MindIE `worldSize=8` 全卡并行；`npuMemSize=-1` 让驱动自动管理卡显存。
- SSD 单盘：Docker 与数据分卷，定期 `docker system prune` 回收，业务备份到异地（参考 `scripts/backup.ps1` 思路改为 rsync/cron）。

---

## 8. 附录

### 8.1 端口速查
22(SSH) / 8080(前端) / 8100(backend) / 3306(MySQL) / 6379(Redis) / 7474+7687(Neo4j) / 11235(Crawl4AI) / 1025(MindIE)

### 8.2 关键路径
- 项目：`/data/gmi/GMI`
- 模型权重：`/data/models`
- 数据库备份：`/data/backups`
- 昇腾驱动：`/usr/local/Ascend`
- Docker 数据：`/var/lib/docker`

### 8.3 镜像清单（需含 linux/arm64）
`mysql:8.0` · `redis:7-alpine` · `neo4j:5.23.0` · `python:3.12-slim` · `node:20-alpine` · `nginx:1.27-alpine` · `swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:3.0.0-300I-Duo-py311-openeuler24.03-lts`

### 8.4 版本与资源推荐
- OS：**Ubuntu Server 22.04 LTS 或 24.04 LTS（aarch64）**
- Docker CE：最新稳定（aarch64），含 docker-compose-plugin
- 昇腾驱动/固件：Atlas 300I Duo 当期 HDK（25.5.2 示例）
- CANN：8.0.0+（toolkit + kernels-310P + nnal）
- 推理引擎：MindIE 3.0.0（300I-Duo 镜像，容器底层 openEuler 24.03，与宿主机 Ubuntu 独立）
- 单卡显存 96G×4 足够容纳 qwen-graphrag 等大模型 + Embedding/Reranker 多服务并行。

---

> 文档维护：本部署面向鲲鹏 920s + Atlas 300I Duo 国产服务器（Ubuntu 操作系统）；后续若升级 CANN/MindIE 或切换 Ubuntu 24.04，请同步更新 §5 版本号与镜像 tag。与既有部署凭据一致性见 `docs/unit-machine-setup.md`。
