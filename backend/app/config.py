"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "SSM平台")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # 后端 HTTP 端口: 统一固定 8200(与 start_all.ps1 / vite 代理 / docker 映射一致)。
    # 已加入 Windows 管理员端口排除(permanent 固定, 不再被系统动态保留抢占)。
    PORT: int = int(os.getenv("PORT", "8200"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", "mysql+pymysql://ssm_user:ssm_pass@localhost:3307/ssm_db?charset=utf8mb4")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Neo4j 知识图谱(实时同步; 连接失败自动降级不影响主流程)
    # 注意: 口令不设源码默认值, 必须通过环境变量/.env 提供, 避免凭据泄露。
    NEO4J_URI: str = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # JWT 签名密钥: 不设源码默认值。生产环境缺失时启动即失败, 防止用公开密钥伪造 token。
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    CACHE_FIELD_META_TTL: int = int(os.getenv("CACHE_FIELD_META_TTL", "3600"))
    CACHE_OPTION_SET_TTL: int = int(os.getenv("CACHE_OPTION_SET_TTL", "7200"))
    CACHE_USER_PERM_TTL: int = int(os.getenv("CACHE_USER_PERM_TTL", "1800"))

    # Redis 缓存熔断参数(连续失败达阈值 → 冷却期内不再访问 Redis, 自动降级)
    CIRCUIT_MAX_FAILURES: int = int(os.getenv("CIRCUIT_MAX_FAILURES", "3"))
    CIRCUIT_TIMEOUT_SECONDS: int = int(os.getenv("CIRCUIT_TIMEOUT_SECONDS", "60"))

    # 登录防暴力破解(进程内滑动窗口, 单实例部署)
    LOGIN_MAX_FAILURES: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    LOGIN_WINDOW_SECONDS: int = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))

    # API 通用限流(Redis 分布式计数, 按客户端 IP; 局域网共用出口可放宽)
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "300"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    # 文件上传大小上限(MB), 超限请求直接 413 拒绝
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "200"))

    # 运维告警 webhook(企业微信/钉钉/通用), 为空则不发送
    NOTIFY_WEBHOOK_URL: str = os.getenv("NOTIFY_WEBHOOK_URL", "")

    # 企查查开放平台
    QCC_APP_KEY: str = os.getenv("QCC_APP_KEY", "")
    QCC_APP_SECRET: str = os.getenv("QCC_APP_SECRET", "")
    QCC_API_URL: str = os.getenv("QCC_API_URL", "https://api.qichacha.com/ECIV4/GetBasicDetailsByName")

    # 本地 Ollama 大模型(人脉 AI 分析)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen-graphrag:latest")

    # Crawl4AI 本地服务(网页爬取, 独立进程监听 11235)
    CRAWL4AI_API_URL: str = os.getenv("CRAWL4AI_API_URL", "http://127.0.0.1:11235")
    CRAWL4AI_API_KEY: str = os.getenv("CRAWL4AI_API_KEY", "")


settings = Settings()


def validate_secret_keys(debug: bool = False) -> None:
    """启动时校验关键密钥: 生产环境(非 DEBUG)缺失 SECRET_KEY 直接抛错。

    Neo4j 口令缺失不阻断启动(图谱降级不影响主流程), 仅打印告警。
    """
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 16:
        if debug:
            import secrets
            settings.SECRET_KEY = secrets.token_urlsafe(48)
            print("[config] DEBUG 模式: 自动生成本次运行临时 SECRET_KEY")
        else:
            raise RuntimeError(
                "SECRET_KEY 未配置或长度不足(>=16字符)。"
                "请在环境变量或 .env 中设置强随机密钥后再启动生产服务。"
            )
    if not settings.NEO4J_PASSWORD:
        print("[config] 警告: NEO4J_PASSWORD 未配置, 知识图谱功能将降级(不影响主业务)")


validate_secret_keys(debug=settings.DEBUG)
