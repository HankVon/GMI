"""文件上传安全工具 — 扩展名白名单 + 魔数校验。

防止: 伪造扩展名上传可执行文件/脚本, 或类型混淆攻击。
"""
from __future__ import annotations

# 扩展名 → 允许的文件头魔数(任一匹配即可)
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "xlsx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),  # zip 家族(OOXML)
    "xls": (b"\xd0\xcf\x11\xe0",),  # OLE2 复合文档
    "docx": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
    "doc": (b"\xd0\xcf\x11\xe0",),
    "pdf": (b"%PDF",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
}

# 导入类接口允许的文件类型
IMPORT_ALLOWED = ("xlsx", "xls")


def check_upload_file(file_bytes: bytes, filename: str,
                      allowed: tuple[str, ...] = IMPORT_ALLOWED) -> str | None:
    """校验扩展名与魔数。通过返回 None, 否则返回错误描述。

    Args:
        file_bytes: 文件内容
        filename: 原始文件名(仅取扩展名判断)
        allowed: 允许的扩展名集合
    """
    name = filename or ""
    ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if ext not in allowed:
        return f"不支持的文件类型: .{ext or '未知'}, 仅允许 {'/'.join(allowed)}"
    magic = _MAGIC.get(ext)
    if magic and not any(file_bytes.startswith(m) for m in magic):
        return f"文件内容与扩展名(.{ext})不符, 可能被篡改"
    return None
