# 系统运维手册（Ops Runbook）

> 适用：Docker Compose 部署（ssm-mysql / ssm-redis / ssm-neo4j / ssm-backend / ssm-frontend）
> 配套：启动部署见 `STARTUP.md`；数据备份恢复见 `backup-restore.md`

---

## 一、日常运维清单

| 频率 | 动作 | 命令/说明 |
|---|---|---|
| 每日 | 检查健康 | `curl http://localhost:8100/api/v1/health`，`dependencies` 三项应全 `ok` |
| 每日 | 检查备份 | `Get-ChildItem d:\Geology\GMI\runtime\backups`，确认今天有新目录且 `ssm.sql` 非空 |
| 每日 | 抽查日志 | `Get-Content d:\Geology\GMI\runtime\logs\app.log -Tail 50`，关注 ERROR |
| 每周 | 容器状态 | `docker compose ps`（应全部 running/healthy） |
| 每周 | 磁盘占用 | 检查 `runtime/backups`、`uploads`、`mysql_data` 卷大小 |
| 每月 | 恢复演练 | 按 `backup-restore.md` 第四节的演练清单执行一次 |

---

## 二、日志

- **位置**：宿主机 `d:\Geology\GMI\runtime\logs\app.log`（容器内 `/app/logs`）
- **轮转**：10MB × 5（`app.log`、`app.log.1`~`app.log.5`）
- **查看**：
  ```powershell
  Get-Content runtime\logs\app.log -Tail 100              # 尾部
  Select-String -Path runtime\logs\app.log -Pattern "ERROR"  # 过滤错误
  docker compose logs -f backend                            # 实时控制台
  ```
- **关键日志分类**：`startup`（启动/迁移）、`scheduler`（定时任务）、`cache`（Redis 降级）、
  `neo4j_sync`（图谱熔断）、`ratelimit`（限流）、`notify`（告警）、`app.error`（未捕获异常）

---

## 三、告警配置

定时任务（意向抓取/人脉重建/GEO 监测等）失败会推送告警。配置 `NOTIFY_WEBHOOK_URL` 环境变量：

**企业微信机器人**：群 → 添加机器人 → 复制 webhook
```
NOTIFY_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
```

**钉钉机器人**：群 → 智能群助手 → 自定义机器人
```
NOTIFY_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxxx
```

**验证**：
```powershell
docker exec ssm-backend python -c "from app.services.notify import send_alert; print(send_alert('测试告警','运维手册验证'))"
```

---

## 四、安全基线

| 项 | 要求 | 检查方式 |
|---|---|---|
| `DEBUG` | 生产必须 `false` | `docker inspect ssm-backend --format '{{range .Config.Env}}{{println .}}{{end}}' \| findstr DEBUG` |
| `SECRET_KEY` | ≥16 位随机串 | 根目录 `.env`，勿提交 git |
| CORS | 仅前端来源 | `docker-compose.yml` 的 `CORS_ORIGINS` |
| 密码策略 | 登录 5 次失败锁 5 分钟；注册密码 ≥8 位 | 内置逻辑 |
| API 限流 | 300 次/分/IP（可调） | `RATE_LIMIT_PER_MINUTE` |
| 上传限制 | 200MB，扩展名+魔数校验 | `MAX_UPLOAD_MB` + `app/utils/upload_security.py` |
| 授权审计 | 权限变更写入审计日志 | 管理后台 → 审计日志页 |

---

## 五、故障排查

| 现象 | 排查步骤 |
|---|---|
| 健康接口 `degraded` | 看 `dependencies` 哪项 down → `docker compose ps` 该容器状态 → `docker compose logs` 对应容器 |
| 后端重启后 404 | 代码改动未 build（后端代码在镜像里）→ 执行发布流程 |
| 页面登录后无菜单 | 用户角色未分配页面权限（`menu_*`）→ 管理后台"配置页面" |
| 导入任务一直"解析中" | 项目导入含单位补全（AI+爬虫，慢）→ 用"快速导入"模式 |
| Redis 不可用 | 系统自动降级（缓存失效、限流放行），日志见 `cache` 分类 |
| Neo4j 不可用 | 图谱同步静默降级（60s 熔断），主流程不受影响 |
| 限流误伤(429) | 局域网多人共用出口 IP → 调高 `RATE_LIMIT_PER_MINUTE` 或按用户限流 |
| 定时任务未执行 | `docker logs ssm-backend \| findstr scheduler`；检查容器时间时区 |

---

## 六、发布检查清单（每次上线）

1. 后端：`docker compose build backend` → `up -d backend` → 日志无 ERROR
2. 前端：`npm run build` → `docker restart ssm-frontend`
3. 健康检查：`/api/v1/health` 全 ok
4. 冒烟：登录 → 列表页 → 详情页 → 图谱
5. 变更含 SQL：确认启动日志中 `migrate` 已执行，或手动执行并验证
6. 更新版本号：`docker-compose.yml` / `config.py` 的 `APP_VERSION`
