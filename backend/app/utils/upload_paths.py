"""附件存储根目录解析 —— 统一「容器」与「本机裸跑」两种运行环境。

背景（为什么不能用 Path(__file__).parent.parent... 的层级魔法）:
    容器内 backend 代码位于 /app/app/...，本机裸跑位于 <repo>/backend/app/...，
    层级不同导致同一行代码在两种环境下解析出**不同的目录**。历史后果：
      - 后台上传的附件被写进容器可写层 /uploads，容器重启即丢失；
      - 部分附件落在 backend/uploads，而该目录未挂载进容器 → 下载 404。

统一规则（优先级从高到低）:
    1. 环境变量 UPLOAD_DIR        —— 显式指定，最可靠
    2. /app/uploads               —— 容器内由 docker-compose 挂载（./uploads:/app/uploads）
    3. <仓库根>/uploads           —— 本机裸跑（本文件往上 3 级即仓库根）

注意:
    数据库中 intent_attachment.local_path / bid_attachment.local_path 存的都是
    **相对于 uploads 根目录的相对路径**（如 intent_attachments/97/xxx.docx），
    因此迁移/合并附件目录时无需改动数据库。
"""
import os
from pathlib import Path

# 容器内挂载点，对应 docker-compose.yml 的 volumes: ./uploads:/app/uploads
_CONTAINER_UPLOADS = Path("/app/uploads")


def upload_root() -> Path:
    """返回统一的附件根目录（唯一真源：仓库根 uploads/）。

    容器内返回 /app/uploads（即宿主机仓库根 uploads/），
    本机裸跑返回 <repo>/uploads，两者指向同一份数据。
    """
    env = os.getenv("UPLOAD_DIR", "").strip()
    if env:
        return Path(env)

    try:
        if _CONTAINER_UPLOADS.is_dir():
            return _CONTAINER_UPLOADS
    except OSError:
        pass

    # 本机裸跑: backend/app/utils/upload_paths.py -> parents[3] = 仓库根
    return Path(__file__).resolve().parents[3] / "uploads"
