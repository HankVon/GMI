# 数据备份与恢复手册

> 适用部署：Docker Compose（`ssm-mysql` / `ssm-redis` / `ssm-neo4j` / `ssm-backend` / `ssm-frontend`）
> 备份目录：`d:/Geology/GMI/runtime/backups/<yyyyMMdd_HHmmss>/`
> 保留策略：最近 7 天（可改脚本 `KEEP_DAYS`）

## 一、备份内容

| 项 | 说明 | 恢复优先级 |
|---|---|---|
| `ssm.sql` | MySQL 全量 dump（utf8mb4，含存储过程/触发器） | 最高 |
| `uploads/` | 用户上传附件（合同/图片/导入文件） | 高 |
| `redis.rdb` | 缓存数据（丢失可自动重建，仅供参考） | 低 |
| `neo4j/` | 知识图谱在线备份（丢失可经流水线/同步从 MySQL 重建） | 低 |

## 二、备份方式

### 自动（推荐）
已注册 Windows 任务计划「SSM每日备份」，每天 02:30 自动执行：

```powershell
schtasks /query /tn "SSM每日备份"   # 查看任务
schtasks /run /tn "SSM每日备份"     # 立即手动触发一次
```

### 手动
```powershell
powershell -ExecutionPolicy Bypass -File d:\Geology\GMI\scripts\backup.ps1
```

### 重注册任务（迁移/重装后）
```powershell
schtasks /create /tn "SSM每日备份" /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File d:\Geology\GMI\scripts\backup.ps1" /sc daily /st 02:30 /f
```

## 三、恢复步骤

> **恢复前务必先备份当前状态**（防止误操作覆盖）。

### 1) 恢复 MySQL（核心数据）

```powershell
# 停止后端写入（避免恢复期间写入）
docker stop ssm-backend

# 恢复（注意：会覆盖现有库）
docker exec -i ssm-mysql sh -c "mysql -uroot -proot_password ssm" < runtime/backups/<日期>/ssm.sql

# 恢复后启动后端
docker start ssm-backend
```

验证：登录系统确认项目/人员/单位/账号数据完整。

### 2) 恢复 uploads（附件）

```powershell
# 备份当前目录后覆盖
Move-Item d:/Geology/GMI/uploads d:/Geology/GMI/uploads.bak
Copy-Item -Recurse runtime/backups/<日期>/uploads d:/Geology/GMI/uploads
# 确认无误后删除 .bak
```

### 3) 恢复 Redis（缓存，可选）
```powershell
docker cp runtime/backups/<日期>/redis.rdb ssm-redis:/data/dump.rdb
docker restart ssm-redis
```
> 缓存丢失无需恢复，服务自动重建，属可选项。

### 4) 恢复 Neo4j（知识图谱，可选）
方式 A：从备份恢复（先停库）
```powershell
docker stop ssm-neo4j
docker cp runtime/backups/<日期>/neo4j ssm-neo4j:/tmp/neo4j-backup
docker start ssm-neo4j
# 在 Neo4j 内执行: neo4j-admin database restore neo4j --from-path=/tmp/neo4j-backup --overwrite-destination=true
docker exec ssm-neo4j sh -c "neo4j-admin database restore neo4j --from-path=/tmp/neo4j-backup --overwrite-destination=true"
```
方式 B：从 MySQL 重建（更简单，推荐）
```powershell
# 通过数据流水线「图谱」阶段或业务网络重建脚本重新生成节点与关系
# 见 docs/business-network-guide.md
```

## 四、恢复演练（上线前必做一次）

1. 手动执行一次备份脚本，确认 `runtime/backups/` 出现新目录且 `ssm.sql` 非空
2. 在测试库上执行一次「恢复 MySQL」步骤，确认能正常登录与查数
3. 记录恢复耗时与步骤，更新本手册的「实际恢复记录」一节

## 五、故障排查

| 现象 | 处理 |
|---|---|
| 备份目录无新文件 | 手动跑一次脚本看报错；检查容器名是否为 `ssm-mysql` 等 |
| `ssm.sql` 为空或很小 | 检查 MySQL 用户权限（需 SELECT/LOCK TABLES）；尝试 `-uroot -proot_password` |
| 任务计划没跑 | `schtasks /run /tn "SSM每日备份"` 手动触发，看输出；确认 PowerShell 执行策略 |
| 恢复后中文乱码 | 恢复命令必须 `--default-character-set=utf8mb4`，见上文 |
