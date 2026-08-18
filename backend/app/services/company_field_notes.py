"""公司字段「不可探查说明」配置 — 对无法从公开渠道获取的字段给出原因 + 建议获取方式。

每个字段对应: {reason: 为什么当前无法探查, suggest: 建议的数据获取方式}
用于前端公司详情页在字段为空时展示说明文字, 避免用户误以为系统有缺陷。
"""
from typing import Optional

FIELD_NOTES: dict = {
    "credit_code": {
        "reason": "统一社会信用代码不对外公开完整信息",
        "suggest": "企查查/爱企查可查(需企业认证), 或由甲方提供营业执照副本",
    },
    "legal_rep": {
        "reason": "政府机关/事业单位无法定代表人概念(只有单位负责人)",
        "suggest": "政府机关查单位官网「领导分工」栏目; 企业查企查查/国家企业信用信息公示系统",
    },
    "econ_kind": {
        "reason": "政府机关/事业单位无企业类型概念",
        "suggest": "企业类查工商登记信息; 事业单位查机构编制网",
    },
    "registered_capital": {
        "reason": "政府机关/事业单位无注册资本概念",
        "suggest": "仅企业类适用, 查国家企业信用信息公示系统",
    },
    "belong_org": {
        "reason": "该单位未在公开渠道登记上级登记机关",
        "suggest": "企业查营业执照「登记机关」栏; 事业单位查机构编制批复文件",
    },
    "business_scope": {
        "reason": "政府机关/事业单位无经营范围概念",
        "suggest": "仅企业类适用, 查营业执照或国家企业信用信息公示系统",
    },
    "contact_person": {
        "reason": "具体经办人联系方式一般不对外公开",
        "suggest": "通过该单位近一年政府采购公告「项目联系人」字段获取; 或致电总机转接",
    },
    "contact_phone": {
        "reason": "该单位未公布对外联系电话(或公告未收录)",
        "suggest": "查单位官网「联系我们」页; 政府机关查本地区政府信息公开目录",
    },
    "contact": {
        "reason": "该单位未公布对外联系电话(或公告未收录)",
        "suggest": "查单位官网「联系我们」页; 政府采购公告的「采购人联系电话」字段",
    },
    "establish_date": {
        "reason": "政府机关/事业单位无成立日期(为组建时间, 不公开)",
        "suggest": "企业类查工商登记信息; 事业单位查机构编制沿革",
    },
    "oper_status": {
        "reason": "政府机关/事业单位无经营状态概念(始终存续)",
        "suggest": "仅企业类适用, 查国家企业信用信息公示系统",
    },
    "reg_no": {
        "reason": "该单位未公开注册号/统一社会信用代码",
        "suggest": "企查查/国家企业信用信息公示系统(企业); 事业单位查机构代码证",
    },
    "address": {
        "reason": "该单位未公布办公地址(或近期搬迁未更新)",
        "suggest": "政府机关查政府信息公开「机构职能/办公地址」; 企业查工商注册地址",
    },
    "province": {
        "reason": "单位登记信息未标注省份",
        "suggest": "根据单位名称行政区划或工商注册地人工补录",
    },
    "city": {
        "reason": "单位登记信息未标注城市",
        "suggest": "根据单位名称行政区划或工商注册地人工补录",
    },
    "website": {
        "reason": "该单位未公布官方网站",
        "suggest": "政府机关查政府门户网站集群; 企业查工商登记信息",
    },
    "email": {
        "reason": "该单位未公布对外邮箱",
        "suggest": "查单位官网「联系我们」; 政府采购公告的「采购人邮箱」字段",
    },
    "summary": {
        "reason": "公开资料中暂无该单位简介",
        "suggest": "政府机关查机构简介栏目; 企业查百科/官网企业介绍",
    },
    "company_type": {
        "reason": "公开资料未标注单位类型",
        "suggest": "根据单位名称后缀(有限公司/局/中心/合作社)人工判断",
    },
}


def get_field_note(field_key: str) -> Optional[dict]:
    """获取字段不可探查说明。字段别名归一化(兼容历史字段名)。"""
    alias = {
        "legal_person": "legal_rep",
        "founded_at": "establish_date",
        "business_status": "oper_status",
        "company_phone": "contact_phone",
        "phone": "contact_phone",
        "landline": "contact_phone",
        "reg_no": "reg_no",
        "org_code": "reg_no",
    }
    key = alias.get(field_key, field_key)
    return FIELD_NOTES.get(key)
