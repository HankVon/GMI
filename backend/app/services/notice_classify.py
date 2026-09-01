"""公告类型识别 — 从公告标题推断 notice_type。

与前端筛选档位(招标/中标/成交/变更/终止/其他)及后台 bid_notice_type option-set 对齐:
命中标准关键词即归入对应档; 均不命中归为「其他」(后端取反匹配档)。

用于:
  - 爬虫写入 web_clue.meta.notice_type 时(不再硬编码「中标（成交）公告」)
  - 解析器 parse_bid_clues 写 bid_notice.notice_type 时(以标题为准)
"""
import re

# 6 档(与前端 filters / 后台 option-set 一致)
NOTICE_TYPES = ("招标", "中标", "成交", "变更", "终止", "其他")

# 各档命中关键词(优先级从高到低)
_TERMINATE = re.compile(r"废标|流标|终止|中止")
_WIN = re.compile(r"中标|结果公告|评审结果|中标候选人")
_DEAL = re.compile(r"成交")
_CHANGE = re.compile(r"变更|更正")
# 采购公告/采购方式类(均属「招标」档); 注意不含「采购意向」(归其他)
_TENDER = re.compile(r"招标|采购公告|竞争性磋商|竞争性谈判|询价|单一来源|资格预审|邀请招标")


def classify_notice_type(title: str) -> str:
    """从公告标题推断 notice_type, 返回 招标/中标/成交/变更/终止/其他。

    优先级: 终止/废标 > 中标 > 成交 > 变更/更正 > 招标/采购公告 > 其他。
    """
    t = (title or "").strip()
    if not t:
        return ""
    if _TERMINATE.search(t):
        return "终止"
    if _WIN.search(t):
        return "中标"
    if _DEAL.search(t) and "中标" not in t:
        return "成交"
    if _CHANGE.search(t):
        return "变更"
    if _TENDER.search(t):
        return "招标"
    return "其他"
