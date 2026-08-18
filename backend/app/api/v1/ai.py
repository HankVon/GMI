"""AI 能力: 接入本地 Ollama(qwen) 提供人脉智能分析。

设计:
  - 模型列表代理: GET /ai/ollama/models — 拉取 Ollama /api/tags 供前端下拉选择。
  - 人脉分析: POST /ai/network/analyze — 将路径数据打包为 prompt, 调用 Ollama
    /api/chat(format=json) 生成结构化分析(桥接人/单位/项目/公关建议/合作机会)。
  - 流式对话: POST /ai/network/chat/stream — SSE 流式输出, AI 分析师以对话形式
    输出分析, 支持基于聊天内容的多轮互动(携带历史 messages)。
  - Ollama 不可用时抛 502, 由前端回退到本地规则分析。
"""
import json
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.middleware.auth import get_current_user

logger = logging.getLogger("ai")

router = APIRouter(prefix="/ai", tags=["AI"])

# 注意: 使用占位符 __ME__/__TARGET__/__PAYLOAD__/__DATA_NOTE__ 占位, 避免与 JSON 花括号冲突

# ── 数据上下文说明(动态注入): 区分「真实人脉路径」与「实体上下文列表」两种模式 ──
# 路径模式: nodes 是后端 Neo4j 最短路径查询的真实结果, 首节点为「我」。
PATH_MODE_NOTE = """已知的人脉路径（nodes 为从「__ME__」到目标实体的【真实知识图谱最短路径】，节点按顺序排列。每个节点含 type: Person/Company/Project, name, position, company_name, category, status。

★★ 关系归属规则(务必严格遵守，这是分析正确性的关键) ★★
- 路径是一条「链」：节点1 —关系1→ 节点2 —关系2→ 节点3 —关系3→ …。
- 节点 i 上的 rel_via_project / rel_company / rel_role / relation_label，只描述【节点(i-1) 到 节点 i】这一步的关系（即"节点(i-1) 与 节点 i 之间"）。
- 特别地：关系永远不会"越级"。例如 节点2 上标注的 rel_via_project（如某项目），属于「节点1 与 节点2」之间的共同项目；若它在 节点3 上，则属于「节点2 与 节点3」之间，与节点1（包括「我」）完全无关。
- 首节点「__ME__」只与第二个节点有直接关系（即 关系1）。路径中后续所有节点之间标注的项目/单位/角色，都【不是】「__ME__」的参与、任职或共同经历。
- 只有当「我」节点自身（第1个节点）或它的下一条关系（关系1）明确带有 rel_via_project 时，才代表「我」参与过某项目。除此之外，绝不要声称「我」参与过、合作过、任职过任何项目或单位。

节点列表：
__PAYLOAD__"""

# 上下文模式: nodes 是目标实体及其关联信息的列表, 首节点不是「我」, 不构成人脉路径。
CONTEXT_MODE_NOTE = """以下 nodes 是目标实体及其关联上下文的列表（每个节点含 type: Person/Company/Project, name, position, company_name, category, status；节点的 rel_via_project / rel_company / rel_role 只描述【该节点与其前一个节点之间】的关系）。

★★ 上下文模式边界（务必严格遵守，防止把「我」与目标实体误关联）★★
- 这【不是】从「__ME__」出发的人脉路径，首节点不是「__ME__」，nodes 中【没有任何节点】代表「__ME__」与目标实体之间存在直接关系。
- 特别地：即使 nodes 中出现名为「__ME__」/与「__ME__」同名/相似的 Person 节点，也【不代表】「__ME__」本人参与过任何项目、与任何人合作过、或与目标实体有关联——那是另一个同名者或历史残留信息，一律忽略，不要把它写成「__ME__」的经历。
- 任何项目、单位、人员都只属于目标实体及其关联人，与「__ME__」无关。严禁声称「__ME__」参与/合作/共同经历任何项目或单位。
- 请将列表仅当作目标实体的主题分析参考资料。

节点列表：
__PAYLOAD__"""

ANALYZE_PROMPT = """你是资深的人脉关系与商务拓展分析师。用户正在通过人脉知识图谱进行关系与商务分析，请基于以下信息给出专业、具体、可操作的分析。

我的姓名：__ME__
目标实体：__TARGET__

__DATA_NOTE__

请严格只输出 JSON（不要任何其他文字、不要 markdown 代码块标记），格式如下：
{
  "summary": "一句话总结：本次分析的核心要点",
  "bridges": [{"name": "桥接人姓名", "tip": "为什么他是关键节点，以及如何接触他"}],
  "companies": [{"name": "单位名", "tip": "这个单位为什么关键，如何作为切入点"}],
  "projects": [{"name": "项目名", "tip": "这个项目如何作为共同话题"}],
  "advice": ["具体可执行的建议1（要具体到某个人/项目/单位）", "建议2", "建议3"],
  "opportunities": ["潜在的合作机会1", "合作机会2"]
}

要求：
- 若本次是【人脉路径分析】（nodes 为从「我」到目标的真实路径）：bridges 只列路径中间的关键人员（不含我本人，也不含目标本人），没有则给空数组；summary 侧重解读触达效率与关键特点。
- 若本次是【主题/上下文分析】（nodes 为实体上下文列表，首节点不是「我」）：bridges 应为空数组；summary 侧重主题结论；companies/projects 从列表中提取与主题相关的实体；advice 围绕主题给出可操作建议；禁止虚构「我」与列表中任何实体的关联，禁止以「我」为第一视角叙述。
- companies/projects 没有则给空数组
- advice 至少 3 条，要具体、可操作，不要空话
- ★★ 严禁把桥接人之间的共同项目说成「我」的共同经历：只有当「我」节点自身或「我→第二节点」那一步关系（关系1）明确标注 rel_via_project 时，才认为「我」参与过该项目。否则，即使路径中张三与李四共同参与了某项目（该项目标在张三节点上），也只能写「张三与李四共同参与该项目、张三认识我」，绝不能写「我与张三共同参与」「我和张三的共同项目」「通过我们共同经历的项目破冰」。
- 严格区分关系归属：每个节点的 rel_via_project / rel_company 只属于该节点与其前一个节点之间，绝不能外推到「我」或列表中其他节点
- 只引用 nodes 中真实存在的实体名/项目名/单位名，不要虚构列表之外的实体
- 全程使用简体中文
"""

# 聊天模式系统提示词: AI 分析师以对话形式流式输出, 支持多轮追问互动。
# 同样使用占位符 __ME__/__TARGET__/__PAYLOAD__/__DATA_NOTE__, 避免与 JSON 花括号冲突。
# 首轮强制按固定 Markdown 分节输出, 保证前端可渲染出清晰的分析结构。
CHAT_SYSTEM_PROMPT = """你是资深的人脉关系与商务拓展分析师「SSM AI 分析师」。用户可能向你请教人脉路径、单位背景、项目机会、公关建议等话题，你可以与用户对话，给出专业、具体、可操作的分析与建议。

我的姓名：__ME__
目标实体：__TARGET__

__DATA_NOTE__

首轮输出规则（二级标题用 ##，列表用 - 或 1.，分节清晰）：
- 若本次是【人脉路径分析】（数据为从「我」到目标实体的真实路径，用户问题聚焦触达/关系链/如何建立联系），请严格使用以下结构输出：

## 触达路径解读
（一段话说明：这条路径多少步、是否可靠、关键特点是什么）

## 关键桥接人
- **姓名**（单位 · 职位）：他为什么是关键节点，如何接触他
（路径中间的所有关键人员逐条列出；若没有中间人则写「路径中无中间桥接人」）

## 相关单位
- **单位名**：这个单位为什么关键、如何作为切入点

## 可切入的合作项目
- **项目名**：如何作为共同话题/破冰切入点
（仅列「我」实际参与、或「我→第二节点」那一步明确标注 rel_via_project 的项目；若「我」没有参与任何项目，则写「路径中无「我」直接参与的项目」，并如实说明桥接人之间的项目只是他们之间的共同经历，可作为了解目标/拉近距离的谈资，而非「我和他共同的项目」）

## 公关建议
1. 建议一（要具体到路径中的某个人/单位/项目）
2. 建议二
3. 建议三

## 潜在合作机会
- 机会一
- 机会二

- 若本次是【主题/上下文分析】（数据为实体上下文列表，首节点不是「我」，用户问题聚焦某一具体主题如"合作建议""沟通策略""公司背景""项目采购机会""风险点""成本控制""决策链"等），请直接围绕该主题组织输出，可用 ## 自行分节；【不要】输出「触达路径解读」「关键桥接人」等路径分节，也不要假定用户与该实体或其关联人员相识/共事/有共同项目。

要求：
- 只引用 nodes 中真实存在的人名/单位名/项目名，不要虚构列表之外的实体；小节没有内容时也要给出该小节标题并简要说明。
- ★★ 严禁把桥接人之间的共同项目说成「我」的共同经历：只有当「我」节点自身或「我→第二节点」那一步关系明确标注 rel_via_project 时，才认为「我」参与过某项目。否则，即使路径中张三与李四共同参与了某项目（项目标在张三节点上），也只能写「张三与李四共同参与该项目、张三认识我」，绝不能写「我与张三共同参与」「我和张三的共同项目」。
- 严格区分关系归属：每个节点的 rel_via_project / rel_company / rel_role 只描述该节点与其前一个节点之间的那一步关系；若首节点是「我」，则「我」只与第二个节点直接关联，后续节点之间的合作项目/单位绝不是「我」的关联；若首节点不是「我」（上下文模式），不要以「我」为第一视角叙述，改用客观分析视角。
- 后续对话中，针对用户的追问深入解答（如：如何联系某个中间人、对方可能关注什么、如何开场破冰、风险评估等），不要重复首轮已给出的完整清单，可适当使用小标题或列表。
- 全程使用简体中文，语气专业、务实、直接。"""


_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _ollama_base_url(base_url: Optional[str]) -> str:
    """解析 Ollama base_url 并做 SSRF 防护。

    - 未传时使用服务端配置 OLLAMA_BASE_URL;
    - 客户端传入时仅允许「回环地址」或与服务端配置一致的地址,
      阻止认证用户借此探测内网(如 169.254.169.254 云元数据)。
    """
    url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        host = ""
    if host not in _LOOPBACK_HOSTS and url != settings.OLLAMA_BASE_URL.rstrip("/"):
        raise HTTPException(
            status_code=400,
            detail="base_url 仅允许本机回环地址(localhost/127.0.0.1)或服务端配置的 Ollama 地址",
        )
    return url


def _build_path_payload(me_name: str, target_name: str, steps: list) -> dict:
    """路径模式的 payload: 在原节点数组基础上, 附加一段逐跳关系归属清单,
    让模型完全不需要自行推断每个 rel_* 属于哪两个实体之间, 杜绝张冠李戴。"""
    payload = {"me": me_name, "target": target_name, "nodes": steps}
    # 逐跳关系链: 第 i 跳 = 节点(i-1) → 节点(i)
    chain = []
    for i in range(1, len(steps)):
        a = steps[i - 1].get("name") or f"节点{i}"
        b = steps[i].get("name") or f"节点{i + 1}"
        rel = steps[i].get("relation_label") or steps[i].get("relation") or ""
        parts = [f"{a} —({rel})→ {b}"]
        if steps[i].get("rel_via_project"):
            parts.append(f"共同项目: {steps[i]['rel_via_project']}")
        if steps[i].get("rel_company"):
            parts.append(f"涉及单位: {steps[i]['rel_company']}")
        if steps[i].get("rel_role"):
            parts.append(f"角色: {steps[i]['rel_role']}")
        chain.append("  • " + "；".join(parts))
    payload["relationship_chain"] = [
        "按「上一步 → 当前步」逐跳列出的关系归属(只属于相邻两个节点之间, 绝不越级):",
        *chain,
        "注意: 除第1跳(「我」→第二节点)外, 其余任何一跳中出现的项目/单位都与「我」无关, 除非第1跳自身明确带 rel_via_project。",
    ]
    return payload


def _resolve_data_note(me_name: str, target_name: str, steps: list, is_path: Optional[bool]) -> str:
    """根据 is_path 选择路径/上下文说明; 未显式传时按首节点是否为「我」兜底判断。"""
    if is_path is None:
        is_path = bool(steps) and steps[0].get("type") == "Person" and steps[0].get("name") == me_name
    # 上下文模式(非路径): me_name 可能为空, 此时用中性称呼, 不给模型注入「我」的概念,
    # 防止模型把目标人员的单位/同事误说成「我」的(如"我与王五同事/同公司")。
    me_label = (me_name or "").strip() or ("我" if is_path else "查询者")
    if is_path:
        payload = json.dumps(_build_path_payload(me_label, target_name, steps), ensure_ascii=False, indent=2)
        return PATH_MODE_NOTE.replace("__ME__", me_label).replace("__PAYLOAD__", payload)
    payload = json.dumps({"me": me_label, "target": target_name, "nodes": steps}, ensure_ascii=False, indent=2)
    return CONTEXT_MODE_NOTE.replace("__ME__", me_label).replace("__PAYLOAD__", payload)


@router.get("/ollama/models")
async def ollama_models(
    base_url: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """代理拉取 Ollama 模型列表(供前端下拉选择)。"""
    url = _ollama_base_url(base_url) + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        names = [m["name"] for m in data.get("models", [])]
        return {"ok": True, "models": names}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": str(e)}


@router.post("/network/analyze")
async def network_analyze(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """调用 Ollama qwen 生成人脉路径分析(结构化 JSON)。"""
    base_url = _ollama_base_url(body.get("base_url"))
    model = body.get("model") or settings.OLLAMA_MODEL
    me_name = body.get("me_name") or ""
    target_name = body.get("target_name") or ""
    steps = body.get("steps") or []
    if not steps:
        raise HTTPException(status_code=400, detail="缺少路径数据")

    is_path = body.get("is_path")
    if is_path is None:
        is_path = bool(steps) and steps[0].get("type") == "Person" and steps[0].get("name") == (me_name or "我")
    me_label = (me_name or "").strip() or ("我" if is_path else "查询者")
    data_note = _resolve_data_note(me_name, target_name, steps, is_path)
    prompt = (
        ANALYZE_PROMPT
        .replace("__DATA_NOTE__", data_note)
        .replace("__ME__", me_label)
        .replace("__TARGET__", target_name)
    )

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.4},
                },
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
    except Exception as e:  # noqa: BLE001
        logger.warning("Ollama analyze failed(base=%s model=%s): %s", base_url, model, e)
        raise HTTPException(status_code=502, detail=f"Ollama 调用失败: {e}")

    # 解析模型输出为 JSON(优先 format=json, 失败再尝试提取代码块)
    try:
        result = json.loads(content)
    except Exception:  # noqa: BLE001
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, re.S)
        if m:
            try:
                result = json.loads(m.group(1))
            except Exception:  # noqa: BLE001
                return {"ok": True, "raw": content, "model": model}
        else:
            return {"ok": True, "raw": content, "model": model}

    return {"ok": True, "result": result, "model": model}


@router.post("/network/chat/stream")
async def network_chat_stream(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """SSE 流式对话: AI 人脉分析师以聊天形式输出分析, 支持多轮互动。

    请求体:
      base_url / model: Ollama 地址与模型
      me_name / target_name: 起始人与目标人
      steps: 路径节点数组(非空)
      is_path: 可选, 数据是否为人脉路径(true)或实体上下文列表(false); 缺省自动判断
      messages: 历史对话 [{role: user|assistant, content}], 首轮可为空数组
    返回: text/event-stream, 每事件为 data: {"content": "..."}, 结束为 data: [DONE]
    """
    base_url = _ollama_base_url(body.get("base_url"))
    model = body.get("model") or settings.OLLAMA_MODEL
    me_name = body.get("me_name") or ""
    target_name = body.get("target_name") or ""
    steps = body.get("steps") or []
    messages = body.get("messages") or []
    if not steps:
        raise HTTPException(status_code=400, detail="缺少路径数据")

    is_path = body.get("is_path")
    if is_path is None:
        is_path = bool(steps) and steps[0].get("type") == "Person" and steps[0].get("name") == (me_name or "我")
    me_label = (me_name or "").strip() or ("我" if is_path else "查询者")
    data_note = _resolve_data_note(me_name, target_name, steps, is_path)
    system_prompt = (
        CHAT_SYSTEM_PROMPT
        .replace("__DATA_NOTE__", data_note)
        .replace("__ME__", me_label)
        .replace("__TARGET__", target_name)
    )
    # 仅保留最近 20 条历史, 避免上下文过长
    chat_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in messages[-20:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            chat_messages.append({"role": m["role"], "content": str(m["content"])})

    async def gen():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": chat_messages,
                        "stream": True,
                        "options": {"temperature": 0.6},
                    },
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except Exception:  # noqa: BLE001
                            continue
                        content = chunk.get("message", {}).get("content")
                        if content:
                            yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                        if chunk.get("done"):
                            break
            yield "data: [DONE]\n\n"
        except Exception as e:  # noqa: BLE001
            logger.warning("Ollama chat stream failed(base=%s model=%s): %s", base_url, model, e)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            # 禁用代理/浏览器缓冲, 保证逐 token 及时到达前端
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
