#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_card_html.py — 把 sales-coach 作战卡 Markdown 编译成可视化 HTML。

用法:
    python3 gen_card_html.py <client.md>
产出:
    与输入同目录、同名的 `*_card.html`（原子写）。

设计原则:
- 仅用标准库，零依赖。
- META 块（<!-- META ... -->）由独立正则预扫描提取，不依赖 section 解析器；
  注释在 md 视图下也不渲染，安全无副作用。
- 所有可视化组件由 META / 模板固定结构驱动，对任意客户通用，不写死客户名。
- 缺 META / 缺字段 → 对应组件跳过，不崩溃（存量卡 100% 兼容）。
- 交互优先纯 CSS（折叠用 checkbox hack、TOC 用锚点），尽量零 JS，健壮且可打印。
"""
import sys
import re
import os
import json
import html as _html
from datetime import datetime
from pathlib import Path

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"
ACCENT = "#FF6A00"
ACCENT2 = "#FF8C3B"
STAGES = ["线索培育", "商机", "方案", "POC", "谈判", "落地"]

# 置信度映射：代号前缀 -> (css类, 字形)
CONF = {
    "public": ("tag-public", "✅"),
    "relation": ("tag-relation", "🔗"),
    "tech": ("tag-tech", "🔧"),
    "infer": ("tag-infer", "💡"),
    "neutral": ("tag-neutral", "❔"),
}
CONF_LABEL = {
    "public": "公开/财报",
    "relation": "关系/股东",
    "tech": "技术/产品",
    "infer": "推断",
    "neutral": "其他/未识别",
}
USED_TAGS = set()  # 真实出现过的置信类（用于图例）


# --------------------------------------------------------------------------- #
# 行内 Markdown -> HTML
# --------------------------------------------------------------------------- #
def tag_class(code: str) -> str:
    """返回置信度原始类名（public/relation/tech/infer/neutral），供汇总表分组用。"""
    c = code.lower()
    if c.startswith("s-ipo") or "ipo" in c or c.startswith("s-biz"):
        k = "public"
    elif c.startswith("s-ali") or "ali" in c or c.startswith("s-collab") or "collab" in c:
        k = "relation"
    elif (
        c.startswith("s-tech")
        or c.startswith("s-oss")
        or c.startswith("s-dots")
        or c.startswith("s-hibo")
        or c.startswith("s-hi")
        or c.startswith("s-sea")
        or "tech" in c
        or "oss" in c
    ):
        k = "tech"
    elif "推断" in code or c == "infer" or c.startswith("s-inf"):
        k = "infer"
    else:
        k = "neutral"
    USED_TAGS.add(k)
    return k


def is_source_code(code: str) -> bool:
    """只有「推断」或纯 ASCII 代号（如 S-ipo / qcc / tech.xxx）才算来源标签，
    避免把 [依据 stagePlaybooks 线索培育剧本] 这类中文说明性方括号误染。"""
    if code == "推断":
        return True
    return bool(re.match(r"^[A-Za-z0-9_.\-]+$", code))


# 来源追踪：正文不渲染标签，仅收集代号供底部汇总表使用
_SEEN_SOURCE_CODES: dict[str, set[str]] = {}  # class -> set of codes


def _collect_source_code(code: str) -> str:
    """记录出现过的来源代号，返回空串（正文不显示任何标签）。"""
    cls = tag_class(code)
    _SEEN_SOURCE_CODES.setdefault(cls, set()).add(code)
    return ""  # 正文干净，零痕迹


def inline(text: str) -> str:
    t = _html.escape(text, quote=False)
    # 来源标注 [代号] -> 正文隐藏（收集到底部汇总表），非代号方括号保留原文
    t = re.sub(
        r"\[([^\]]+?)\](?!\()",
        lambda m: (
            _collect_source_code(m.group(1))
            if is_source_code(m.group(1))
            else f"[{_html.escape(m.group(1))}]"
        ),
        t,
    )
    # 加粗
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    # 强调下划线占位 _xxx_ -> <em>
    t = re.sub(r"(?<!\*)\_([^_]+?)\_(?!\*)", r"<em>\1</em>", t)
    # 关键词高亮
    t = t.replace("⚠️", '<span class="warn">⚠️</span>')
    t = re.sub(r"(未采用|均未采用|红标|风险)", r'<span class="danger">\1</span>', t)
    return t


# --------------------------------------------------------------------------- #
# META 解析（独立预扫描）
# --------------------------------------------------------------------------- #
def _parse_kv(s: str):
    s = s.strip()
    if "=" in s:
        k, v = s.split("=", 1)
        return (k.strip(), v.strip())
    return (s, "")


def _norm_weight(w: str):
    if w in ("高", "High", "high"):
        return 100
    if w in ("中", "Mid", "mid"):
        return 66
    if w in ("低", "Low", "low"):
        return 33
    try:
        return int(re.sub(r"[^0-9]", "", w)) or None
    except Exception:
        return None


def _parse_role(s: str):
    s = s.strip()
    note = ""
    if "#" in s:
        s, note = s.split("#", 1)
    name, weight = _parse_kv(s)
    return {"name": name, "weight": _norm_weight(weight) if weight else None, "note": note.strip()}


def parse_meta(raw: str) -> dict:
    m = re.search(r"<!--\s*META([\s\S]*?)-->", raw)
    if not m:
        return {}
    flat = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, _, v = line.partition(":")
        flat[k.strip()] = v.strip()
    out = {}
    if "stance" in flat:
        out["stance"] = flat["stance"]
    if "collected" in flat:
        out["collected"] = flat["collected"]
    if "ecosystem" in flat:
        e = flat["ecosystem"]
        if "#" in e:
            sig, note = e.split("#", 1)
            out["eco"] = {"sig": sig.strip(), "note": note.strip()}
        else:
            out["eco"] = {"sig": e.strip(), "note": ""}
    if "metrics" in flat:
        out["metrics"] = [_parse_kv(x) for x in flat["metrics"].split("|") if x.strip()]
    if "stage" in flat:
        out["stage"] = flat["stage"]
    if "roles" in flat:
        out["roles"] = [_parse_role(x) for x in flat["roles"].split("|") if x.strip()]
    if "moves" in flat:
        out["moves"] = [_parse_kv(x) for x in flat["moves"].split("|") if x.strip()]
    return out


def days_since(d: str):
    try:
        dt = datetime.strptime(d[:10], "%Y-%m-%d")
        return (datetime.now() - dt).days
    except Exception:
        return None


def norm_stage(s: str):
    s = re.sub(r"[期中阶段]", "", s)
    for i, st in enumerate(STAGES):
        if st in s or s in st:
            return i
    return -1


# --------------------------------------------------------------------------- #
# section 解析
# --------------------------------------------------------------------------- #
def parse(md: str):
    lines = md.split("\n")
    title = None
    subtitle = None
    sections = []
    cur = None
    for ln in lines:
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()
            if level == 1 and title is None:
                title = heading
                continue
            cur = {"level": level, "heading": heading, "body": []}
            sections.append(cur)
        else:
            if cur is None:
                s = ln.strip()
                if s.startswith(">") and subtitle is None:
                    subtitle = s.lstrip(">").strip()
                continue
            cur["body"].append(ln)
    return title, subtitle, sections


# --------------------------------------------------------------------------- #
# 块渲染
# --------------------------------------------------------------------------- #
def render_body(body_lines, ctx="default"):
    out = []
    buf = []

    def flush_list():
        if not buf:
            return
        out.append('<ul class="body-list">')
        for text, is_html in buf:
            if is_html:
                out.append(f"<li>{text}</li>")
            else:
                out.append(f"<li>{inline(text)}</li>")
        out.append("</ul>")
        buf.clear()

    quote_buf = []

    def flush_quote():
        if not quote_buf:
            return
        joined = " ".join(quote_buf)
        out.append(f'<div class="note">{inline(joined)}</div>')
        quote_buf.clear()

    HL = {"最可能痛点": "hl-red", "我方价值主张": "hl-green", "对我方机会点": "hl-orange"}
    for raw in body_lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_list()
            flush_quote()
            continue
        if stripped.startswith(">"):
            flush_list()
            quote_buf.append(stripped.lstrip(">").strip())
            continue
        m = re.match(r"^\s*-\s+(.*)$", line)
        if m:
            flush_quote()
            item = m.group(1).strip()
            om = re.match(r'异议[：:]\s*"([^"]*)"\s*→\s*我方话术[：:]\s*(.*)', item)
            if om:
                buf.append(
                    (
                        f'<div class="objection"><div class="obj-q">❓ {_html.escape(om.group(1))}</div>'
                        f'<div class="obj-a">✅ {inline(om.group(2))}</div></div>',
                        True,
                    )
                )
                continue
            rm = re.match(r"\*\*(.+?)\*\*\s*[：:]\s*(.*)", item)
            if rm and ctx == "roles":
                buf.append(
                    (
                        f'<div class="role"><span class="role-name">{inline(rm.group(1))}</span>'
                        f'<span class="role-desc">{inline(rm.group(2))}</span></div>',
                        True,
                    )
                )
                continue
            hm = re.match(r"\*\*(最可能痛点|我方价值主张|对我方机会点)\*\*", item)
            if hm:
                buf.append((f'<div class="hl {HL[hm.group(1)]}">{inline(item)}</div>', True))
                continue
            buf.append((item, False))
            continue
        flush_list()
        flush_quote()
        out.append(f'<p>{inline(line.strip())}</p>')

    flush_list()
    flush_quote()
    return "\n".join(out)


def render_strategy(body_lines):
    """模块②：日期前缀 bullet -> 竖向时间线；无日期 -> 回退普通列表。"""
    items = []
    for ln in body_lines:
        m = re.match(r"^\s*-\s+(.*)$", ln)
        if not m:
            continue
        txt = m.group(1).strip()
        stripped = re.sub(r"^\*\*(.+?)\*\*\s*[：:]?\s*", "", txt).strip()
        if not stripped:
            continue
        dm = re.match(r"^(\d{4}(?:[-/年]\d{1,2}(?:[-/月]\d{1,2})?)?)", stripped)
        if dm and dm.group(1):
            date = dm.group(1)
            event = stripped[dm.end():].lstrip("：: ").strip()
            items.append(("dated", date, event))
        else:
            items.append(("plain", None, inline(stripped)))
    dated = [i for i in items if i[0] == "dated"]
    plain = [i for i in items if i[0] == "plain"]
    if not dated:
        return '<ul class="body-list">' + "".join(f"<li>{t}</li>" for _, _, t in plain) + "</ul>"
    out = ['<div class="timeline">']
    for _, date, event in dated:
        out.append(
            f'<div class="tl-node"><span class="tl-date">{_html.escape(date)}</span>'
            f'<span class="tl-dot"></span><div class="tl-event">{inline(event)}</div></div>'
        )
    out.append("</div>")
    if plain:
        out.append('<ul class="body-list tl-other">')
        for _, _, t in plain:
            out.append(f"<li>{t}</li>")
        out.append("</ul>")
    return "\n".join(out)


def render_tldr(body_lines):
    strategy = None
    questions = []
    meta = {}
    for ln in body_lines:
        s = ln.strip().lstrip(">").strip()
        if not s:
            continue
        s2 = re.sub(r"^\*\*(.+?)\*\*\s*", r"\1", s)
        for part in re.split(r"\s*｜\s*", s2):
            pm = re.match(r"^([^：:]+?)\s*[：:]\s*(.*)$", part)
            if not pm:
                continue
            key = pm.group(1).replace("**", "").strip()
            val = pm.group(2).strip()
            if "核心策略" in key:
                strategy = val.strip().strip("_").strip()
            elif "必聊" in key:
                questions = [
                    x.strip().strip("_").strip()
                    for x in re.split(r"[①②③④⑤]", val)
                    if x.strip()
                ]
            else:
                meta[key] = val.strip()
    chips = ""
    for k in ("当前阶段", "丰富度"):
        if k in meta:
            chips += f'<span class="chip">{k}：{inline(meta[k])}</span>'
    q_html = ""
    if questions:
        q_html = (
            '<div class="tldr-q"><div class="tldr-q-label">必聊 3 问</div>'
            + "".join(
                f"<div class='tldr-q-item'>{CIRCLED[i]} {inline(q)}</div>"
                for i, q in enumerate(questions)
            )
            + "</div>"
        )
    strat_html = f'<div class="tldr-strategy">{inline(strategy)}</div>' if strategy else ""
    # 兜底：非结构化 TL;DR（旧模板/自由格式，无 核心策略/必聊/阶段 键）→ 直接渲染原文段落
    if not (strategy or questions or chips):
        raw = "".join(
            f'<p>{inline(ln.strip().lstrip(">").strip())}</p>'
            for ln in body_lines
            if ln.strip().lstrip(">").strip()
        )
        return f"""
    <section class="card tldr-card" id="tldr">
      <input type="checkbox" class="col-toggle" id="tg-tldr" checked>
      <label class="card-head" for="tg-tldr"><span class="badge">⚡</span><h2>顶部 30 秒速读</h2><span class="col-ico">▾</span></label>
      <div class="card-body">
        <div class="tldr">
          {raw}
        </div>
      </div>
    </section>"""
    return f"""
    <section class="card tldr-card" id="tldr">
      <input type="checkbox" class="col-toggle" id="tg-tldr" checked>
      <label class="card-head" for="tg-tldr"><span class="badge">⚡</span><h2>顶部 30 秒速读</h2><span class="col-ico">▾</span></label>
      <div class="card-body">
        <div class="tldr">
          {strat_html}
          {q_html}
          <div class="tldr-chips">{chips}</div>
        </div>
      </div>
    </section>"""


def extract_next_action(sec):
    confirm = None
    remind = None
    for ln in sec["body"]:
        m = re.match(r"^\s*-\s+\*\*(离开前必须确认的一件事|下一步日历提醒)\*\*\s*[：:]\s*(.*)", ln.strip())
        if m:
            if "离开前" in m.group(1):
                confirm = m.group(2).strip()
            else:
                remind = m.group(2).strip()
    return confirm, remind


def render_roles_viz(roles):
    if not roles:
        return ""
    weights = [r["weight"] or 0 for r in roles]
    maxw = max(weights) if weights else 1
    out = ['<div class="roles-viz">']
    for r in roles:
        w = r["weight"] or 0
        top = "top" if (r["weight"] and r["weight"] == maxw and maxw > 0) else ""
        wpct = w if w <= 100 else 100
        out.append(
            f'<div class="rolebar {top}"><div class="rb-top"><span class="rb-name">{inline(r["name"])}</span>'
            f'<span class="rb-w">权重 {r["weight"] if r["weight"] is not None else "—"}</span></div>'
            f'<div class="rb-track"><div class="rb-fill" style="width: {wpct}%"></div></div>'
        )
        if r["note"]:
            out.append(f'<div class="rb-note">{inline(r["note"])}</div>')
        out.append("</div>")
    out.append("</div>")
    return "\n".join(out)


def render_dashboard(meta, next_action):
    parts = []
    # 状态条：立场 + 新鲜度 + 生态
    stance = meta.get("stance", "")
    fresh = ""
    if meta.get("collected"):
        d = days_since(meta["collected"])
        if d is not None:
            if d == 0:
                cls, lab = "green", "今日采集"
            elif d <= 30:
                cls, lab = "green", f"采集于 {d} 天前"
            elif d <= 60:
                cls, lab = "amber", f"采集于 {d} 天前"
            else:
                cls, lab = "red", f"采集于 {d} 天前（建议重验）"
            fresh = f'<span class="fresh {cls}">🕓 {lab}</span>'
    eco = ""
    if meta.get("eco"):
        eco = (
            f'<span class="eco">🔗 {inline(meta["eco"]["sig"])}'
            + (f'<span class="eco-note"> · {inline(meta["eco"]["note"])}</span>' if meta["eco"]["note"] else "")
            + "</span>"
        )
    if stance or fresh or eco:
        parts.append(
            '<div class="status">'
            + (f'<span class="chip-stance">{inline(stance)}</span>' if stance else "")
            + fresh
            + eco
            + "</div>"
        )
    # 指标瓷砖
    if meta.get("metrics"):
        tiles = "".join(
            f'<div class="metric"><div class="v">{inline(v)}</div><div class="l">{inline(l)}</div></div>'
            for l, v in meta["metrics"]
            if l != "丰富度"
        )
        parts.append(f'<div class="metrics">{tiles}</div>')
    # 阶段流水线
    if meta.get("stage"):
        idx = norm_stage(meta["stage"])
        steps = ""
        for i, st in enumerate(STAGES):
            cls = "todo"
            if idx >= 0:
                if i < idx:
                    cls = "done"
                elif i == idx:
                    cls = "active"
            line = '<span class="line"></span>' if i < len(STAGES) - 1 else ""
            steps += (
                f'<span class="step {cls}"><span class="dot">{i+1}</span>'
                f'<span class="lab">{st}</span></span>{line}'
            )
        parts.append(f'<div class="stepper">{steps}</div>')
    # 策略行动瓷砖
    if meta.get("moves"):
        mv = "".join(
            f'<div class="move"><div class="mt">{inline(t)}</div><div class="md">{inline(d)}</div></div>'
            for t, d in meta["moves"]
        )
        parts.append(f'<div class="moves">{mv}</div>')
    return "\n".join(parts)


def render_nextact(next_action):
    """下一步行动：作为整张卡的收尾 CTA（见客户前最后看一眼），
    避免与模块⑥的『离开前确认/日历提醒』逐字重复。"""
    if not next_action or not (next_action[0] or next_action[1]):
        return ""
    confirm, remind = next_action
    b = ""
    if confirm:
        b += f'<div><input type="checkbox" class="na-check"> <span class="na-label">离开前确认</span> {inline(confirm)}</div>'
    if remind:
        b += f'<div class="na-remind"><span class="na-label">日历提醒</span> {inline(remind)}</div>'
    return f'<div class="nextact"><div class="na-title">下一步行动（见客户前必看）</div>{b}</div>'


def _render_source_summary():
    """底部来源汇总表：正文不显示任何标签，所有来源代号在此集中列出。"""
    if not _SEEN_SOURCE_CODES:
        return ""

    # 前缀→可读含义（常见前缀，未命中则直接展示代号）
    HINTS = {
        "S-ipo": "IPO / 财报 / 估值",
        "S-biz": "商业新闻 / 合作公告",
        "S-sea": "出海 / 国际化 / 海外市场",
        "S-tech": "技术栈 / 招聘 / 工程体系",
        "S-ali": "阿里系 / 股东关系",
        "S-dots": "自研 AI 部门 Dots",
        "S-hibo": "内部协同平台 hi/hibo",
        "S-hi": "自研协同平台 hi",
        "S-collab": "协同工具采用情况",
    }

    rows = ""
    for cls in ("public", "relation", "tech", "infer"):
        codes = sorted(_SEEN_SOURCE_CODES.get(cls, set()))
        if not codes:
            continue
        lab = CONF_LABEL.get(cls, cls)
        for code in codes:
            hint = HINTS.get(code) or code
            rows += (
                f'<tr class="sr-{cls}">'
                f'<td class="sr-code">{_html.escape(code)}</td>'
                f'<td class="sr-hint">{hint}</td>'
                f'<td class="sr-cls">{lab}</td></tr>'
            )

    return (
        '<section class="card" id="sources">'
        '<input type="checkbox" class="col-toggle" id="tg-sources" checked>'
        '<label class="card-head" for="tg-sources"><span class="badge">📎</span>'
        '<h2>信息来源汇总</h2><span class="col-ico">▾</span></label>'
        f'<div class="card-body"><p class="src-note">以下代号出现在原文中，'
        '正文已隐去以保持阅读流畅。</p>'
        f'<table class="src-table"><thead><tr>'
        f'<th>代号</th><th>来源说明</th><th>置信类别</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div></section>'
    )


def card_html(tid, badge, label, body):
    return (
        f'<section class="card" id="{tid}"><input type="checkbox" class="col-toggle" id="tg-{tid}" checked>'
        f'<label class="card-head" for="tg-{tid}"><span class="badge">{badge}</span>'
        f'<h2>{inline(label)}</h2><span class="col-ico">▾</span></label>'
        f'<div class="card-body">{body}</div></section>'
    )


# --------------------------------------------------------------------------- #
# 我方立场面板（架构修复：立场库单源，改库即改卡）
# --------------------------------------------------------------------------- #
def load_stance_profile(meta: dict):
    """从立场库 companyMatrix.json 读取当前激活立场档案（myCompany.json.active 决定），
    作为渲染卡中『我方立场』面板的权威来源——立场库一改、重渲染即生效，无需改客户 .md。
    缺失文件 / 键 → 返回 None（降级为不渲染该面板，不影响其他组件，存量卡 100% 兼容）。"""
    here = Path(__file__).resolve().parent
    matrix_path = here / "companyMatrix.json"
    if not matrix_path.is_file():
        return None
    try:
        with open(matrix_path, encoding="utf-8") as f:
            matrix = json.load(f)
    except Exception:
        return None
    if not isinstance(matrix, dict):
        return None
    # 1) 优先 myCompany.json.active
    active = None
    mc_path = here.parent / "myCompany.json"
    if mc_path.is_file():
        try:
            with open(mc_path, encoding="utf-8") as f:
                active = json.load(f).get("active")
        except Exception:
            pass
    # 2) 回退：从 META stance 文本匹配公司名
    if not active and meta.get("stance"):
        for key, prof in matrix.items():
            if isinstance(prof, dict) and prof.get("companyName", "") and prof["companyName"] in meta["stance"]:
                active = key
                break
    if not active:
        active = "qianwen-office"
    prof = matrix.get(active)
    return prof if isinstance(prof, dict) else None


def render_stance_panel(profile: dict) -> str:
    """『我方立场』权威面板：直接来自 companyMatrix.json，渲染卡永远反映当前立场库立场，
    消除手誊散文与立场库的措辞漂移。"""
    if not profile:
        return ""
    name = profile.get("companyName", "")
    ba = profile.get("brandArchitecture", "")
    prods = profile.get("products", []) or []
    ba_html = f'<div class="sp-arch">{inline(ba)}</div>' if ba else ""
    prod_items = ""
    if prods:
        items = []
        for p in prods:
            if isinstance(p, dict):
                pn = p.get("name", "")
                pt = (
                    p.get("tagline")
                    or p.get("value")
                    or p.get("desc")
                    or p.get("positioning")
                    or ""
                )
                items.append(
                    f'<li><span class="sp-name">{inline(pn)}</span>'
                    f'<span class="sp-desc">{inline(str(pt))}</span></li>'
                )
            else:
                items.append(f"<li>{inline(str(p))}</li>")
        prod_items = '<ul class="sp-prods">' + "".join(items) + "</ul>"
    body = ba_html + prod_items
    return card_html("stance", "🏳", f"我方立场 · {name}", body)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def gen(md_path: str) -> str:
    with open(md_path, "r", encoding="utf-8") as f:
        raw = f.read()
    USED_TAGS.clear()
    _SEEN_SOURCE_CODES.clear()
    meta = parse_meta(raw)
    title, subtitle, sections = parse(raw)

    toc = []
    cards = []
    tldr_html = ""
    roles_html = ""
    checklist_html = ""
    dq_html = ""
    roles_viz = ""
    next_action = None
    sec_idx = 0

    for sec in sections:
        h = sec["heading"]
        badge = ""
        for ch in h:
            if ch in CIRCLED:
                badge = ch
                break
        label = re.sub(r"^[" + CIRCLED + r"]\s*", "", h).strip()
        label = re.sub(r"^▸\s*", "", label)

        if "TL;DR" in h or "速读" in h:
            toc.append(("速读", "tldr"))
            tldr_html = render_tldr(sec["body"])
            continue
        if "买家角色分支" in h or "角色分支" in h:
            tid = "roles"
            toc.append(("角色分支", tid))
            if meta.get("roles"):
                roles_viz = render_roles_viz(meta["roles"])
            roles_html = (
                f'<section class="card" id="{tid}"><input type="checkbox" class="col-toggle" id="tg-{tid}" checked>'
                f'<label class="card-head" for="tg-{tid}"><span class="badge">👥</span>'
                f'<h2>{inline(h)}</h2><span class="col-ico">▾</span></label>'
                f'<div class="card-body">{roles_viz}{render_body(sec["body"], ctx="roles")}</div></section>'
            )
            continue
        if "探测清单" in h:
            tid = "checklist"
            toc.append(("探测清单", tid))
            items = [
                f'<li>{inline(m.group(1).strip())}</li>'
                for ln in sec["body"]
                if (m := re.match(r"^\s*-\s+(.*)$", ln))
            ]
            checklist_html = (
                f'<section class="card" id="{tid}"><input type="checkbox" class="col-toggle" id="tg-{tid}" checked>'
                f'<label class="card-head" for="tg-{tid}"><span class="badge">🔍</span>'
                f'<h2>{inline(h)}</h2><span class="col-ico">▾</span></label>'
                f'<div class="card-body"><ul class="checklist">{"" .join(items)}</ul></div></section>'
            )
            continue
        if "数据质量声明" in h:
            tid = "dq"
            toc.append(("数据质量", tid))
            dq_html = (
                f'<section class="card dq" id="{tid}"><input type="checkbox" class="col-toggle" id="tg-{tid}" checked>'
                f'<label class="card-head" for="tg-{tid}"><span class="badge">📋</span>'
                f'<h2>{inline(h)}</h2><span class="col-ico">▾</span></label>'
                f'<div class="card-body">{render_body(sec["body"])}</div></section>'
            )
            continue
        if badge:
            sec_idx += 1
            tid = "sec" + str(CIRCLED.index(badge) + 1)
            toc.append((badge + " " + label, tid))
            if badge == "⑥":
                next_action = extract_next_action(sec)
                # 去除与速读/顶部 CTA 重复的 bullet（必聊3问已在速读、行动已在底部 CTA）
                filtered = [
                    ln
                    for ln in sec["body"]
                    if not re.match(
                        r"^\s*-\s+\*\*(离开前必须确认的一件事|下一步日历提醒|必聊\s*3\s*问)\*\*",
                        ln.strip(),
                    )
                ]
                body = render_body(filtered)
            elif badge == "②":
                body = render_strategy(sec["body"])
            else:
                body = render_body(sec["body"])
            cards.append(card_html(tid, badge, label, body))
        else:
            sec_idx += 1
            tid = "secx" + str(sec_idx)
            toc.append((label, tid))
            cards.append(card_html(tid, "▸", label, render_body(sec["body"])))

    cards_html = "".join(cards)

    # 来源汇总表（替代原来的 tag 色块图例——正文已不渲染标签）
    # 必须在 TOC 构建前渲染，才能据「有无来源」决定是否加 TOC 锚点
    source_html = _render_source_summary()
    if source_html:
        toc.append(("信息来源", "sources"))

    stance_profile = load_stance_profile(meta)
    stance_panel = render_stance_panel(stance_profile)
    if stance_panel:
        toc.append(("我方立场", "stance"))

    dashboard = render_dashboard(meta, next_action)

    toc_html = '<nav class="toc">' + "".join(
        f'<a href="#{tid}">{_html.escape(lab)}</a>' for lab, tid in toc
    ) + "</nav>"

    subtitle_html = f'<div class="subtitle">{inline(subtitle)}</div>' if subtitle else ""
    gen_time = _html.escape(datetime.now().strftime("%Y-%m-%d %H:%M"))
    footer_html = f'<div class="footer">由 sales-coach 技能自动生成 · {gen_time}</div>'
    nextact_html = render_nextact(next_action)

    body_html = (
        f'<h1 class="doc-title">{inline(title or "作战卡")}</h1>'
        + subtitle_html
        + toc_html
        + dashboard
        + stance_panel
        + tldr_html
        + cards_html
        + roles_html
        + checklist_html
        + dq_html
        + source_html
        + nextact_html
        + footer_html
    )

    html_doc = HTML_SCAFFOLD.replace("__TITLE__", _html.escape(title or "作战卡")).replace(
        "__CSS__", CSS
    ).replace("__BODY__", body_html)
    return html_doc


HTML_SCAFFOLD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<button class="export-btn" onclick="window.print()">🖨 打印 / 导出 PDF</button>
<div class="wrap">
__BODY__
</div>
</body>
</html>"""

CSS = """
:root {
  --accent: #FF6A00; --accent2: #FF8C3B;
  --ink: #1f2430; --muted: #6b7280; --line: #ececf1; --bg: #f7f8fa; --card: #ffffff;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.7; padding: 28px 18px 60px;
}
.wrap { max-width: 980px; margin: 0 auto; }
.doc-title { font-size: 26px; font-weight: 800; margin: 0 0 4px; }
.subtitle { color: var(--muted); font-size: 13px; margin-bottom: 14px; }

/* 导出按钮 */
.export-btn {
  position: fixed; top: 12px; right: 12px; z-index: 30;
  background: var(--accent); color: #fff; border: none; border-radius: 20px;
  padding: 7px 14px; font-size: 13px; font-weight: 700; cursor: pointer;
  box-shadow: 0 4px 14px rgba(255,106,0,.35);
}
.export-btn:hover { background: var(--accent2); }

/* 粘性目录 */
.toc {
  position: sticky; top: 0; z-index: 20; background: var(--bg);
  display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 0; margin-bottom: 14px;
  border-bottom: 1px solid var(--line);
}
.toc a {
  font-size: 12.5px; color: var(--muted); text-decoration: none;
  background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 4px 11px;
}
.toc a:hover { color: var(--accent); border-color: var(--accent); }

/* 状态条 */
.status { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 6px 0 12px; }
.chip-stance { background: var(--accent); color: #fff; border-radius: 20px; padding: 4px 14px; font-size: 13px; font-weight: 700; }
.fresh { display: inline-flex; align-items: center; gap: 5px; border-radius: 20px; padding: 4px 12px; font-size: 12px; font-weight: 600; }
.fresh.green { background: #e7f6ec; color: #1a7f37; }
.fresh.amber { background: #fff3e0; color: #b25e09; }
.fresh.red { background: #fde8e8; color: #c0362c; }
.eco { display: inline-flex; align-items: center; gap: 5px; border-radius: 20px; padding: 4px 12px; font-size: 12px; font-weight: 600; background: #e7f0ff; color: #1a56c4; }
.eco-note { font-weight: 400; color: #4b5563; }

/* 指标瓷砖 */
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin: 10px 0; }
.metric { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; text-align: center; }
.metric .v { font-size: 19px; font-weight: 800; color: var(--accent); line-height: 1.2; word-break: break-word; }
.metric .l { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* 阶段流水线 */
.stepper { display: flex; align-items: center; flex-wrap: wrap; gap: 0; margin: 6px 0 12px; }
.step { display: flex; align-items: center; gap: 6px; }
.step .dot { width: 22px; height: 22px; border-radius: 50%; background: #e5e7eb; color: #9aa3af; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.step .lab { font-size: 12.5px; color: var(--muted); }
.step.active .dot { background: var(--accent); color: #fff; }
.step.active .lab { color: var(--accent); font-weight: 700; }
.step.done .dot { background: #fff; color: var(--accent); border: 2px solid var(--accent); }
.step.done .lab { color: var(--accent); }
.step .line { width: 26px; height: 2px; background: #e5e7eb; margin: 0 6px; }
.step.active .line, .step.done .line { background: var(--accent); }

/* 策略行动瓷砖 */
.moves { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 10px; margin: 10px 0; }
.move { background: linear-gradient(135deg, #fff2e8, #ffe6d2); border: 1px solid #ffd2ad; border-radius: 12px; padding: 12px 14px; }
.move .mt { font-weight: 800; color: var(--accent); font-size: 15px; }
.move .md { font-size: 13px; color: #5a4632; margin-top: 4px; }

/* 下一步行动条 */
.nextact { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff; border-radius: 14px; padding: 14px 16px; margin: 12px 0; font-size: 14px; }
.na-title { font-weight: 800; font-size: 13px; opacity: .92; letter-spacing: 1px; margin-bottom: 6px; }
.na-label { font-weight: 700; opacity: .9; margin-right: 4px; }
.na-check { width: 16px; height: 16px; vertical-align: -3px; accent-color: #fff; }
.na-remind { margin-top: 6px; }

/* TL;DR */
.tldr-card { margin-bottom: 16px; }
.tldr { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff; border-radius: 14px; padding: 18px 20px; }
.tldr-strategy { font-size: 17px; font-weight: 700; margin-bottom: 12px; }
.tldr-q-label { font-size: 12px; opacity: .85; margin-bottom: 6px; letter-spacing: 1px; }
.tldr-q-item { background: rgba(255,255,255,.16); border-radius: 8px; padding: 7px 11px; margin-bottom: 6px; font-size: 14px; }
.tldr-chips { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px; }
.chip { background: rgba(255,255,255,.22); border-radius: 20px; padding: 4px 12px; font-size: 12px; }

/* 卡片网格 + 折叠 */
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; margin-bottom: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(20,20,40,.04); scroll-margin-top: 56px; }
.card-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; cursor: pointer; user-select: none; }
.card-head h2 { font-size: 17px; margin: 0; flex: 1; }
.badge { flex: none; width: 30px; height: 30px; border-radius: 8px; background: #fff2e8; color: var(--accent); display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; }
.col-ico { flex: none; color: var(--muted); font-size: 12px; transition: transform .15s; }
.col-toggle { position: absolute; opacity: 0; pointer-events: none; }
.col-toggle:not(:checked) ~ .card-body { display: none; }
.col-toggle:not(:checked) ~ .card-head .col-ico { transform: rotate(-90deg); }
.card-body p { margin: 6px 0; }
.body-list { margin: 6px 0; padding-left: 20px; }
.body-list li { margin: 4px 0; }
.note { background: #fff8f1; border-left: 3px solid var(--accent); border-radius: 6px; padding: 8px 12px; margin: 8px 0; font-size: 13.5px; color: #5a4632; }

/* 我方立场面板（来自立场库，权威单源，改库即改卡） */
.sp-arch { background: #fff8f1; border-left: 3px solid var(--accent); border-radius: 8px; padding: 10px 12px; margin-bottom: 10px; font-size: 13.5px; color: #5a4632; font-weight: 600; line-height: 1.65; }
.sp-prods { list-style: none; padding-left: 0; margin: 6px 0 0; }
.sp-prods li { display: flex; gap: 10px; padding: 6px 0; border-bottom: 1px dashed var(--line); align-items: baseline; }
.sp-prods li:last-child { border-bottom: none; }
.sp-name { flex: none; min-width: 134px; font-weight: 800; color: var(--accent); }
.sp-desc { color: var(--ink); font-size: 13.5px; }

/* 来源标签：正文不渲染（收集到底部汇总表）——保留 .tag 类定义以防遗漏 */
.tag { display: none; }

.warn { color: #d9480f; font-weight: 700; }
.danger { color: #d92d20; font-weight: 700; }

/* 异议 / 角色 */
.objection { background: #fafbff; border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin: 8px 0; }
.obj-q { color: #c2410c; font-weight: 600; font-size: 14px; margin-bottom: 4px; }
.obj-a { color: #15803d; font-size: 14px; }
.role { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px dashed var(--line); }
.role:last-child { border-bottom: none; }
.role-name { flex: none; min-width: 120px; font-weight: 700; color: var(--accent); }
.role-desc { color: var(--ink); }

/* 角色权重条形图 */
.roles-viz { margin: 4px 0 10px; }
.rolebar { margin: 8px 0; }
.rb-top { display: flex; justify-content: space-between; font-size: 13px; }
.rb-name { font-weight: 700; }
.rb-w { color: var(--muted); }
.rb-track { height: 10px; background: #eef0f4; border-radius: 6px; overflow: hidden; margin-top: 3px; }
.rb-fill { height: 100%; background: #cbd2dc; border-radius: 6px; }
.rolebar.top .rb-fill { background: var(--accent); }
.rolebar.top .rb-name { color: var(--accent); }
.rb-note { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* 战略时间线 */
.timeline { margin: 8px 0 4px; }
.tl-node { display: grid; grid-template-columns: 78px 16px 1fr; gap: 8px; align-items: start; padding: 6px 0 6px 14px; border-left: 2px solid var(--line); margin-left: 6px; position: relative; }
.tl-date { font-size: 12px; font-weight: 700; color: var(--accent); }
.tl-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--accent); margin-top: 5px; }
.tl-event { font-size: 13.5px; }
.tl-other { margin-top: 8px; }

/* 风险/机会色块 */
.hl { border-radius: 8px; padding: 8px 12px; margin: 6px 0; font-size: 13.5px; }
.hl-red { background: #fde8e8; border-left: 3px solid #d92d20; }
.hl-green { background: #e7f6ec; border-left: 3px solid #1a7f37; }
.hl-orange { background: #fff3e0; border-left: 3px solid #b25e09; }

/* 探测清单 / 数据质量 */
.checklist { list-style: none; padding-left: 4px; }
.checklist li { padding: 5px 0 5px 26px; position: relative; }
.checklist li::before { content: "☐"; position: absolute; left: 0; color: var(--accent); font-size: 16px; }
.card.dq .card-body { font-size: 13.5px; color: #4b5563; }

/* 来源汇总表 */
.src-note { font-size: 13px; color: var(--muted); margin-bottom: 10px; }
.src-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.src-table th { text-align: left; padding: 7px 12px; background: #f8f9fb; color: #4b5563; font-weight: 600; font-size: 12.5px; border-bottom: 2px solid #e5e7eb; }
.src-table td { padding: 6px 12px; border-bottom: 1px solid #f0f1f3; }
.sr-code { font-family: ui-monospace, monospace; font-weight: 700; font-size: 12px; }
.sr-hint { color: var(--ink); }
.sr-cls { font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.sr-public .sr-cls { color: #1a7f37; }
.sr-relation .sr-cls { color: #1a56c4; }
.sr-tech .sr-cls { color: #6b21c9; }
.sr-infer .sr-cls { color: #b25e09; }

.footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 24px; }

/* 窄屏 */
@media (max-width: 720px) {
  .grid2 { grid-template-columns: 1fr; }
  .role { flex-direction: column; gap: 2px; }
  .role-name { min-width: 0; }
  .tl-node { grid-template-columns: 64px 14px 1fr; }
  .toc { flex-wrap: nowrap; overflow-x: auto; }
  .toc a { white-space: nowrap; }
}

/* 深色模式 */
@media (prefers-color-scheme: dark) {
  :root { --ink: #e8eaed; --muted: #9aa3af; --line: #2a2f3a; --bg: #0f1216; --card: #171b21; }
  .metric, .card, .toc a, .src-table { background: var(--card); }
  .sp-arch { background: #2a2118; color: #e8d9c8; }
  .hl-red { background: #3a1d1d; } .hl-green { background: #16301f; } .hl-orange { background: #33260f; }
}

/* 打印 */
@media print {
  .export-btn, .toc { display: none !important; }
  .col-toggle:not(:checked) ~ .card-body { display: block !important; }
  .col-ico { display: none !important; }
  .card, .metric, .move, .src-table { break-inside: avoid; }
  .tl-node, .rolebar, .objection { break-inside: avoid; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  body { padding: 0; background: #fff; }
}
"""


def main():
    if len(sys.argv) < 2:
        print("usage: gen_card_html.py <client.md>", file=sys.stderr)
        sys.exit(1)
    md_path = sys.argv[1]
    if not os.path.isfile(md_path):
        print(f"file not found: {md_path}", file=sys.stderr)
        sys.exit(1)
    html_doc = gen(md_path)
    out_path = re.sub(r"\.md$", "_card.html", md_path)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html_doc)
    os.replace(tmp, out_path)  # 原子写
    print(f"OK -> {out_path} ({len(html_doc)} bytes)")


if __name__ == "__main__":
    main()
