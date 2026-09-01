"""管道级筛选规则与质量检查。

从 data_pipeline.py 拆出: FilterRules + check_quality + 相关辅助函数,
完全自包含, 仅依赖外部 china_regions。
"""
from datetime import datetime
from typing import Optional

from app.services.china_regions import extract_target_province, is_target_province

# 主题关键词: 命中任意即视为「行业相关」, 空=全部接受
# 用户确认六大方向: 地质 / 地灾 / 矿业 / 水文 / 规划 / 生态
TOPIC_KEYWORDS = [
    # 地质
    "地质", "勘察", "勘查", "测绘", "岩土", "探矿", "钻探", "地勘",
    # 地灾
    "地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "地面沉降",
    # 矿业
    "矿业权", "采矿", "矿产", "矿山", "资源储量", "矿权",
    # 水文
    "水文", "水资源", "水利", "水库", "堤防", "防洪",
    # 规划
    "规划", "国土空间", "土地利用", "用途管制", "总体规划", "专项规划",
    # 生态
    "生态修复", "环境治理", "矿山修复", "土壤修复", "水污染治理", "生态保护",
]
# 排除关键词: 命中任意即丢弃(非项目/废数据)
EXCLUDE_KEYWORDS = ["招聘", "办公设备", "复印机", "打印机", "电脑耗材", "办公用品",
                    "会议通知", "培训通知", "征求意见稿", "中标结果公告（废标）", "废标公告",
                    "食材", "食堂", "食品", "家具", "空调", "物业"]
# 目标省份: 只保留 四川/西藏/新疆(严格限定)
TARGET_PROVINCES = ["四川", "西藏", "新疆"]
# 时效窗口: 公告实际发布时间距今超过该天数不入库(用户确认 180 天)
MAX_AGE_DAYS = 180
# 最小正文长度(字符), 太短视为废数据
MIN_CONTENT_LEN = 50


class FilterRules:
    """管道级筛选规则。字段均可按需覆盖。"""

    def __init__(self, topic_keywords=None, exclude_keywords=None, target_provinces=None,
                 max_age_days=None, min_content_len=None):
        self.topic_keywords = topic_keywords or TOPIC_KEYWORDS
        self.exclude_keywords = exclude_keywords or EXCLUDE_KEYWORDS
        self.target_provinces = target_provinces or TARGET_PROVINCES
        self.max_age_days = max_age_days if max_age_days is not None else MAX_AGE_DAYS
        self.min_content_len = min_content_len if min_content_len is not None else MIN_CONTENT_LEN

    def to_dict(self) -> dict:
        return {
            "topic_keywords": self.topic_keywords,
            "exclude_keywords": self.exclude_keywords,
            "target_provinces": self.target_provinces,
            "max_age_days": self.max_age_days,
            "min_content_len": self.min_content_len,
        }


def _published_dt(published_at) -> Optional[datetime]:
    if isinstance(published_at, datetime):
        return published_at
    if isinstance(published_at, str) and published_at:
        try:
            return datetime.fromisoformat(published_at.replace("Z", ""))
        except ValueError:
            pass
    return None


def _content_of(clue) -> str:
    meta = clue.meta if isinstance(clue.meta, dict) else {}
    return " ".join(filter(None, [
        clue.title or "", clue.summary or "", clue.content or "",
        meta.get("overview") or "", meta.get("qualification") or "",
    ]))


def check_quality(clue, rules: Optional[FilterRules] = None) -> tuple[bool, str]:
    """管道级质量检查: (是否通过, 未通过原因)。

    规则(全部满足才通过):
      1. 主题相关: 标题/正文命中 TOPIC_KEYWORDS 任一(命中排除词则直接丢弃)
      2. 地域过滤: 标题 + region 命中 川藏新 任一省市县词
         (正文不参与地域判定 — 公告正文常含"四川省"等无关提及, 会误匹配非川藏新公告)
      3. 时效: 实际发布时间距今 <= max_age_days(无时间则通过)
      4. 非废数据: 正文长度 >= min_content_len
    """
    rules = rules or FilterRules()
    content = _content_of(clue)
    # 标题 + region(不含正文) 用于地域/主题判定
    head_pool = f"{clue.title or ''} {clue.region or ''}"
    full_pool = f"{head_pool} {content}"

    # 1) 排除词优先(全文)
    for kw in rules.exclude_keywords:
        if kw and kw in full_pool:
            return False, f"命中排除词「{kw}」"
    # 2) 主题相关(标题优先, 正文兜底)
    if rules.topic_keywords:
        head_hit = any(k in head_pool for k in rules.topic_keywords if k)
        full_hit = any(k in full_pool for k in rules.topic_keywords if k)
        if not (head_hit or full_hit):
            return False, "未命中主题关键词(非地质/招标/采购相关)"
    # 3) 地域过滤(川藏新): 仅标题 + region 判定, 防正文误匹配
    prov = extract_target_province(head_pool)
    if not prov or not is_target_province(prov):
        return False, "非目标省份(标题/地域无川藏新, 仅四川/西藏/新疆)"
    # 4) 时效
    published = _published_dt(clue.published_at)
    if published and (datetime.now() - published).days > rules.max_age_days:
        return False, f"发布时间超期({(datetime.now() - published).days}天 > {rules.max_age_days}天)"
    # 5) 非废数据
    if len(content.strip()) < rules.min_content_len:
        return False, "正文过短(疑似废数据)"
    return True, ""
