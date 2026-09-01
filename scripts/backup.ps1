# SSM Daily Backup Script (Docker Compose deployment)
# - MySQL full dump (utf8mb4 safe, container-side dump + docker cp)
# - uploads dir copy
# - Redis RDB (best effort)
# - Neo4j online backup (best effort; data is rebuildable from MySQL)
# Retention: keep latest KEEP_DAYS backups, remove older ones.
# Schedule: Windows Task Scheduler daily 02:30 (see register-backup-task below).

$ErrorActionPreference = "Continue"

$KEEP_DAYS = 2
$BASE     = "d:/Geology/GMI/runtime/backups"
$DATE     = Get-Date -Format "yyyyMMdd_HHmmss"
$DIR      = Join-Path $BASE $DATE

# --- 0. prepare ---
New-Item -ItemType Directory -Force -Path $DIR | Out-Null
Write-Output "[backup] target: $DIR"

# --- 1. MySQL full dump (container-side to keep utf8mb4 bytes intact) ---
try {
    Write-Output "[backup] dumping MySQL..."
    docker exec ssm-mysql sh -c "mysqldump -ussm_user -pssm_pass --single-transaction --routines --triggers ssm > /tmp/ssm_dump.sql" 2>&1 | Out-Null
    docker cp "ssm-mysql:/tmp/ssm_dump.sql" (Join-Path $DIR "ssm.sql")
    docker exec ssm-mysql rm -f /tmp/ssm_dump.sql
    $size = (Get-Item (Join-Path $DIR "ssm.sql")).Length
    Write-Output "[backup] MySQL done ($size bytes)"
} catch {
    Write-Output "[backup][WARN] MySQL backup failed: $($_.Exception.Message)"
}

# --- 2. uploads dir (user attachments) ---
try {
    Write-Output "[backup] copying uploads..."
    Copy-Item -Recurse -Force "d:/Geology/GMI/uploads" (Join-Path $DIR "uploads")
    Write-Output "[backup] uploads done"
} catch {
    Write-Output "[backup][WARN] uploads copy failed: $($_.Exception.Message)"
}

# --- 3. Redis RDB (cache, low priority) ---
try {
    docker exec ssm-redis redis-cli save 2>&1 | Out-Null
    docker cp "ssm-redis:/data/dump.rdb" (Join-Path $DIR "redis.rdb")
    Write-Output "[backup] Redis RDB done"
} catch {
    Write-Output "[backup][WARN] Redis backup skipped: $($_.Exception.Message)"
}

# --- 4. Neo4j online backup (best effort; rebuildable from MySQL) ---
try {
    Write-Output "[backup] Neo4j online backup..."
    docker exec ssm-neo4j sh -c "rm -rf /tmp/neo4j-backup && neo4j-admin database backup neo4j --to-path=/tmp/neo4j-backup" 2>&1 | Out-Null
    $probe = docker exec ssm-neo4j sh -c "test -d /tmp/neo4j-backup && echo YES" 2>&1
    if ($probe -match "YES") {
        docker cp "ssm-neo4j:/tmp/neo4j-backup" (Join-Path $DIR "neo4j")
        docker exec ssm-neo4j rm -rf /tmp/neo4j-backup
        Write-Output "[backup] Neo4j done"
    } else {
        Write-Output "[backup][WARN] Neo4j online backup unavailable (rebuild from MySQL instead)"
    }
} catch {
    Write-Output "[backup][WARN] Neo4j backup skipped (rebuild from MySQL instead): $($_.Exception.Message)"
}

# --- 5. retention cleanup ---
try {
    Get-ChildItem $BASE -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KEEP_DAYS) } |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName -ErrorAction SilentlyContinue }
    Write-Output "[backup] retention cleanup done (keep $KEEP_DAYS days)"
} catch {
    Write-Output "[backup][WARN] cleanup failed: $($_.Exception.Message)"
}

Write-Output "[backup] complete: $DIR"
