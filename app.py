import os
import re
import json
import time
import base64
import random
from datetime import datetime
from io import BytesIO
from typing import Dict, Any, Optional, List, Tuple

import streamlit as st
import yaml
import pandas as pd
import altair as alt
from pypdf import PdfReader

try:
    from docx import Document  # python-docx
except ImportError:
    Document = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    canvas = None
    letter = None

from openai import OpenAI
import google.generativeai as genai
from anthropic import Anthropic
import httpx


# =============================================================================
# Configuration: models, localization, WOW styles
# =============================================================================

ALL_MODELS = [
    # OpenAI
    "gpt-4o-mini",
    "gpt-4.1-mini",
    # Gemini
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    # Anthropic (examples; can be expanded via agents.yaml and/or future config)
    "claude-3-5-sonnet-2024-10",
    "claude-3-5-haiku-20241022",
    # Grok
    "grok-4-fast-reasoning",
    "grok-3-mini",
]

OPENAI_MODELS = {"gpt-4o-mini", "gpt-4.1-mini"}
GEMINI_MODELS = {"gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"}
ANTHROPIC_MODELS = {"claude-3-5-sonnet-2024-10", "claude-3-5-haiku-20241022"}
GROK_MODELS = {"grok-4-fast-reasoning", "grok-3-mini"}

PAINTER_STYLES = [
    "Van Gogh", "Monet", "Picasso", "Da Vinci", "Rembrandt",
    "Matisse", "Kandinsky", "Hokusai", "Yayoi Kusama", "Frida Kahlo",
    "Salvador Dali", "Rothko", "Pollock", "Chagall", "Basquiat",
    "Haring", "Georgia O'Keeffe", "Turner", "Seurat", "Escher",
]

LABELS = {
    "app_title": {"English": "Agentic Medical Device Reviewer", "繁體中文": "智慧醫材審查工作台"},
    "Dashboard": {"English": "Dashboard", "繁體中文": "儀表板"},
    "TW Premarket": {"English": "TW Premarket Application", "繁體中文": "第二、三等級醫療器材查驗登記"},
    "510k_tab": {"English": "510(k) Intelligence", "繁體中文": "510(k) 智能分析"},
    "PDF → Markdown": {"English": "PDF → Markdown", "繁體中文": "PDF → Markdown"},
    "Checklist & Report": {"English": "510(k) Review Pipeline", "繁體中文": "510(k) 審查全流程"},
    "510k Report Generator": {"English": "510(k) Report Generator", "繁體中文": "510(k) 審查報告產生器"},
    "Note Keeper & Magics": {"English": "Note Keeper & Magics", "繁體中文": "筆記助手與魔法"},
    "Agents Config": {"English": "Agents Config Studio", "繁體中文": "代理設定工作室"},
    "Live Log": {"English": "Live Log", "繁體中文": "即時紀錄"},
    "Global Settings": {"English": "Global Settings", "繁體中文": "全域設定"},
    "Theme": {"English": "Theme", "繁體中文": "主題"},
    "Language": {"English": "Language", "繁體中文": "語言"},
    "Painter Style": {"English": "Painter Style", "繁體中文": "畫家風格"},
    "Jackpot!": {"English": "Jackpot!", "繁體中文": "抽一個！"},
    "Default Model": {"English": "Default Model", "繁體中文": "預設模型"},
    "Default max_tokens": {"English": "Default max_tokens", "繁體中文": "預設 max_tokens"},
    "Temperature": {"English": "Temperature", "繁體中文": "溫度"},
    "API Keys": {"English": "API Keys", "繁體中文": "API 金鑰"},
    "Agents Catalog (agents.yaml)": {"English": "Agents Catalog (agents.yaml)", "繁體中文": "代理目錄 (agents.yaml)"},
    "Upload custom agents.yaml": {"English": "Upload custom agents.yaml", "繁體中文": "上傳自訂 agents.yaml"},
    "Run Agent": {"English": "Run Agent", "繁體中文": "執行代理"},
    "Prompt": {"English": "Prompt", "繁體中文": "提示詞"},
    "Model": {"English": "Model", "繁體中文": "模型"},
    "Input Text / Markdown": {"English": "Input Text / Markdown", "繁體中文": "輸入文字 / Markdown"},
    "View mode": {"English": "View mode", "繁體中文": "檢視模式"},
    "Markdown": {"English": "Markdown", "繁體中文": "Markdown"},
    "Plain text": {"English": "Plain text", "繁體中文": "純文字"},
    "Output (editable)": {"English": "Output (editable)", "繁體中文": "輸出（可編輯）"},
    "Download .md": {"English": "Download .md", "繁體中文": "下載 .md"},
    "Download .txt": {"English": "Download .txt", "繁體中文": "下載 .txt"},
    "Output language": {"English": "Output language", "繁體中文": "輸出語言"},
    "English": {"English": "English", "繁體中文": "英文"},
    "繁體中文": {"English": "Traditional Chinese", "繁體中文": "繁體中文"},
}

STYLE_CSS = {
    "Van Gogh": "body { background: radial-gradient(circle at top left, #243B55, #141E30); }",
    "Monet": "body { background: linear-gradient(120deg, #a1c4fd, #c2e9fb); }",
    "Picasso": "body { background: linear-gradient(135deg, #ff9a9e, #fecfef); }",
    "Da Vinci": "body { background: radial-gradient(circle, #f9f1c6, #c9a66b); }",
    "Rembrandt": "body { background: radial-gradient(circle, #2c1810, #0b090a); }",
    "Matisse": "body { background: linear-gradient(135deg, #ffecd2, #fcb69f); }",
    "Kandinsky": "body { background: linear-gradient(135deg, #00c6ff, #0072ff); }",
    "Hokusai": "body { background: linear-gradient(135deg, #2b5876, #4e4376); }",
    "Yayoi Kusama": "body { background: radial-gradient(circle, #ffdd00, #ff6a00); }",
    "Frida Kahlo": "body { background: linear-gradient(135deg, #f8b195, #f67280, #c06c84); }",
    "Salvador Dali": "body { background: linear-gradient(135deg, #1a2a6c, #b21f1f, #fdbb2d); }",
    "Rothko": "body { background: linear-gradient(135deg, #141E30, #243B55); }",
    "Pollock": "body { background: repeating-linear-gradient(45deg,#222,#222 10px,#333 10px,#333 20px); }",
    "Chagall": "body { background: linear-gradient(135deg, #a18cd1, #fbc2eb); }",
    "Basquiat": "body { background: linear-gradient(135deg, #f7971e, #ffd200); }",
    "Haring": "body { background: linear-gradient(135deg, #ff512f, #dd2476); }",
    "Georgia O'Keeffe": "body { background: linear-gradient(135deg, #ffefba, #ffffff); }",
    "Turner": "body { background: linear-gradient(135deg, #f8ffae, #43c6ac); }",
    "Seurat": "body { background: radial-gradient(circle, #e0eafc, #cfdef3); }",
    "Escher": "body { background: linear-gradient(135deg, #232526, #414345); }",
}

DEFAULT_510K_REPORT_TEMPLATE_EN = """# 510(k) Review Report (Template)

## 1. Executive Summary
- Review scope
- Key findings
- Recommendation

## 2. Device Overview
- Device name, sponsor, submission type
- Intended use / indications for use
- Technology summary

## 3. Predicate / Comparator Summary
- Predicate device(s)
- Substantial equivalence rationale
- Key differences table

## 4. Performance Testing Review
- Bench testing
- Software verification/validation (if applicable)
- EMC / electrical safety (if applicable)
- Biocompatibility / sterilization / shelf-life (if applicable)
- Cybersecurity (if applicable)

## 5. Risk Management & Labeling
- Key hazards and controls
- Labeling adequacy and limitations

## 6. Open Issues / Information Requests
- Missing data list
- Clarification questions

## 7. Conclusion

## Appendix A. Entities Table (20)
## Appendix B. Tables Index
"""

DEFAULT_510K_REPORT_TEMPLATE_ZH = """# 510(k) 審查報告（模板）

## 1. 摘要（Executive Summary）
- 審查範圍
- 主要發現
- 建議結論

## 2. 器材概述
- 器材名稱、廠商、送件類型
- 預期用途 / 適應症
- 技術與工作原理摘要

## 3. Predicate / Comparator 概述
- 對比器材
- 實質等同性論述
- 主要差異比較表

## 4. 性能與測試審查
- Bench 測試
- 軟體 V&V（如適用）
- EMC / 電性安全（如適用）
- 生物相容性 / 滅菌 / 保存期限（如適用）
- 資安（如適用）

## 5. 風險管理與標示
- 主要危害與控制
- 標示充分性與限制

## 6. 待補件 / 待釐清事項（Information Requests）
- 缺漏資料清單
- 需要澄清的問題

## 7. 結論

## 附錄A：Entities（20筆）
## 附錄B：表格索引
"""


# =============================================================================
# Localization + Style application
# =============================================================================

def t(key: str) -> str:
    lang = st.session_state.settings.get("language", "English")
    return LABELS.get(key, {}).get(lang, key)


def apply_style(theme: str, painter_style: str):
    css = STYLE_CSS.get(painter_style, "")

    if theme == "Dark":
        css += """
        body { color: #e5e7eb; }
        [data-testid="stAppViewContainer"] { background-color: rgba(0,0,0,0.12); }
        .stButton>button { background-color: #1f2937; color: #f9fafb; border-radius: 999px; }
        .stTextInput>div>div>input, .stTextArea textarea, .stSelectbox>div>div, .stDateInput>div>div>input {
            background-color: #111827; color: #e5e7eb; border-radius: 0.6rem;
        }
        .stTabs [data-baseweb="tab"] { color: #e5e7eb; }
        """
    else:
        css += """
        body { color: #111827; }
        [data-testid="stAppViewContainer"] { background-color: rgba(255,255,255,0.55); }
        .stButton>button { background-color: #2563eb; color: white; border-radius: 999px; }
        .stTextInput>div>div>input, .stTextArea textarea, .stSelectbox>div>div, .stDateInput>div>div>input {
            background-color: #ffffff; color: #111827; border-radius: 0.6rem;
        }
        """

    # WOW cards + badges + log panel
    css += """
    .wow-card {
        border-radius: 18px;
        padding: 14px 18px;
        margin-bottom: 0.75rem;
        box-shadow: 0 14px 35px rgba(15,23,42,0.35);
        border: 1px solid rgba(148,163,184,0.35);
        backdrop-filter: blur(10px);
    }
    .wow-card-title {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        opacity: 0.9;
    }
    .wow-card-main {
        font-size: 1.35rem;
        font-weight: 800;
        margin-top: 4px;
        line-height: 1.2;
    }
    .wow-badge {
        display:inline-flex;
        align-items:center;
        padding:2px 10px;
        border-radius:999px;
        font-size:0.75rem;
        font-weight:700;
        background:rgba(15,23,42,0.12);
        border:1px solid rgba(148,163,184,0.5);
        margin-right:6px;
        margin-top:6px;
    }
    .wow-log {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        font-size: 0.82rem;
        line-height: 1.35;
        padding: 10px 12px;
        border-radius: 12px;
        border: 1px solid rgba(148,163,184,0.35);
        background: rgba(2,6,23,0.12);
        max-height: 320px;
        overflow-y: auto;
        white-space: pre-wrap;
    }
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =============================================================================
# Live log + status + metrics helpers
# =============================================================================

def utc_ts() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def approx_tokens(text: str) -> int:
    # rough estimate: 4 chars/token (English-ish); for CJK may differ, but good enough for WOW indicator
    return max(1, int(len(text) / 4))


def log_live(event: Dict[str, Any]):
    if "live_log" not in st.session_state:
        st.session_state["live_log"] = []
    st.session_state["live_log"].append(event)
    # also keep a simplified run history for dashboard analytics
    if "history" not in st.session_state:
        st.session_state["history"] = []
    if event.get("event_type") == "run_complete":
        st.session_state["history"].append({
            "tab": event.get("tab", ""),
            "agent": event.get("agent", ""),
            "model": event.get("model", ""),
            "provider": event.get("provider", ""),
            "tokens_est": event.get("tokens_est", 0),
            "duration_ms": event.get("duration_ms", None),
            "status": event.get("status", ""),
            "ts": event.get("ts", utc_ts()),
        })


def show_status_line(step_name: str, status: str, extra: str = ""):
    color = {
        "pending": "#94a3b8",
        "running": "#f59e0b",
        "done": "#10b981",
        "error": "#ef4444",
    }.get(status, "#94a3b8")

    extra_html = f'<span style="opacity:0.85;margin-left:8px;">{extra}</span>' if extra else ""
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;margin-bottom:0.25rem;">
          <div style="width:10px;height:10px;border-radius:50%;background:{color};
                      margin-right:8px;border:1px solid rgba(255,255,255,0.35);"></div>
          <span style="font-size:0.95rem;"><b>{step_name}</b> — {status}{extra_html}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def provider_readiness() -> Dict[str, str]:
    # returns provider -> "env" / "session" / "missing"
    keys = st.session_state.get("api_keys", {}) or {}
    status = {}
    status["openai"] = "env" if os.getenv("OPENAI_API_KEY") else ("session" if keys.get("openai") else "missing")
    status["gemini"] = "env" if os.getenv("GEMINI_API_KEY") else ("session" if keys.get("gemini") else "missing")
    status["anthropic"] = "env" if os.getenv("ANTHROPIC_API_KEY") else ("session" if keys.get("anthropic") else "missing")
    status["grok"] = "env" if os.getenv("GROK_API_KEY") else ("session" if keys.get("grok") else "missing")
    return status


def render_live_log_panel(filter_tab: Optional[str] = None, height: int = 280, limit: int = 200):
    logs = st.session_state.get("live_log", [])
    if filter_tab:
        logs = [e for e in logs if e.get("tab") == filter_tab]
    logs = logs[-limit:]

    if not logs:
        st.info(t("Live Log") + ": (empty)")
        return

    # render as compact text
    lines = []
    for e in logs:
        ts = e.get("ts", "")
        et = e.get("event_type", "")
        tab = e.get("tab", "")
        agent = e.get("agent", "")
        status = e.get("status", "")
        model = e.get("model", "")
        msg = e.get("message", "")
        dur = e.get("duration_ms", None)
        tok = e.get("tokens_est", None)
        dur_s = f"{dur/1000:.1f}s" if isinstance(dur, (int, float)) else ""
        tok_s = f"tok≈{tok}" if isinstance(tok, int) else ""
        tail = " ".join([x for x in [dur_s, tok_s] if x]).strip()
        if tail:
            tail = " | " + tail
        lines.append(f"{ts} | {tab} | {agent} | {et}/{status} | {model}{tail}\n{msg}".strip())

    # fixed height via css container
    st.markdown(f"<div class='wow-log' style='max-height:{height}px;'>{'<br><br>'.join([st._escape_html(x) for x in lines])}</div>", unsafe_allow_html=True)


# =============================================================================
# LLM routing
# =============================================================================

def get_provider(model: str) -> str:
    if model in OPENAI_MODELS:
        return "openai"
    if model in GEMINI_MODELS:
        return "gemini"
    if model in ANTHROPIC_MODELS:
        return "anthropic"
    if model in GROK_MODELS:
        return "grok"
    # allow models not in sets if user configured in agents.yaml; attempt inference by prefix
    if model.startswith("gpt-"):
        return "openai"
    if model.startswith("gemini-"):
        return "gemini"
    if model.startswith("claude-"):
        return "anthropic"
    if model.startswith("grok-"):
        return "grok"
    raise ValueError(f"Unknown model: {model}")


def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 12000,
    temperature: float = 0.2,
    api_keys: Optional[dict] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Returns (text, meta)
    meta includes: provider, duration_ms, tokens_est (approx), error (optional)
    """
    provider = get_provider(model)
    api_keys = api_keys or {}

    def get_key(name: str, env_var: str) -> str:
        return api_keys.get(name) or os.getenv(env_var) or ""

    start = time.perf_counter()
    tokens_est_in = approx_tokens(system_prompt + "\n" + user_prompt)

    if provider == "openai":
        key = get_key("openai", "OPENAI_API_KEY")
        if not key:
            raise RuntimeError("Missing OpenAI API key.")
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = resp.choices[0].message.content or ""

    elif provider == "gemini":
        key = get_key("gemini", "GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Missing Gemini API key.")
        genai.configure(api_key=key)
        llm = genai.GenerativeModel(model)
        resp = llm.generate_content(
            system_prompt + "\n\n" + user_prompt,
            generation_config={"max_output_tokens": max_tokens, "temperature": temperature},
        )
        text = getattr(resp, "text", "") or ""

    elif provider == "anthropic":
        key = get_key("anthropic", "ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Missing Anthropic API key.")
        client = Anthropic(api_key=key)
        resp = client.messages.create(
            model=model,
            system=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # anthropic python SDK returns list of content blocks
        text = resp.content[0].text if resp.content else ""

    elif provider == "grok":
        key = get_key("grok", "GROK_API_KEY")
        if not key:
            raise RuntimeError("Missing Grok (xAI) API key.")
        with httpx.Client(base_url="https://api.x.ai/v1", timeout=90) as client:
            resp = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"] or ""

    else:
        raise RuntimeError(f"Unsupported provider for model {model}")

    duration_ms = int((time.perf_counter() - start) * 1000)
    tokens_est_out = approx_tokens(text)
    meta = {
        "provider": provider,
        "duration_ms": duration_ms,
        "tokens_est_in": tokens_est_in,
        "tokens_est_out": tokens_est_out,
        "tokens_est_total": tokens_est_in + tokens_est_out,
    }
    return text, meta


# =============================================================================
# Document helpers
# =============================================================================

def extract_pdf_pages_to_text(file, start_page: int, end_page: int) -> str:
    reader = PdfReader(file)
    n = len(reader.pages)
    start = max(0, start_page - 1)
    end = min(n, end_page)
    texts = []
    for i in range(start, end):
        try:
            texts.append(reader.pages[i].extract_text() or "")
        except Exception:
            texts.append("")
    return "\n\n".join(texts).strip()


def extract_docx_to_text(file) -> str:
    if Document is None:
        return ""
    try:
        bio = BytesIO(file.read())
        doc = Document(bio)
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception:
        return ""


def create_pdf_from_text(text: str) -> bytes:
    if canvas is None or letter is None:
        raise RuntimeError("PDF generation library 'reportlab' is not installed.")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    margin = 72
    line_height = 14
    y = height - margin
    for line in text.splitlines():
        if y < margin:
            c.showPage()
            y = height - margin
        c.drawString(margin, y, line[:2000])
        y -= line_height
    c.save()
    buf.seek(0)
    return buf.getvalue()


def show_pdf(pdf_bytes: bytes, height: int = 600):
    if not pdf_bytes:
        return
    b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    pdf_html = f"""
    <iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" type="application/pdf"></iframe>
    """
    st.markdown(pdf_html, unsafe_allow_html=True)


# =============================================================================
# Markdown quality gates (for WOW + 510k report generator)
# =============================================================================

_TABLE_SEP_RE = re.compile(r"^\s*\|?.+\|.+\|?\s*$")
_TABLE_DIV_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def estimate_word_count(md: str) -> int:
    # Count "words" roughly; includes CJK segments as tokens too, but consistent enough for gating
    if not md:
        return 0
    # Collapse code blocks to avoid inflating
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    # Words: sequences of letters/numbers; CJK: count each CJK char as 1
    latin_words = re.findall(r"[A-Za-z0-9]+", md)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", md)
    return len(latin_words) + len(cjk_chars)


def count_markdown_tables(md: str) -> int:
    if not md:
        return 0
    lines = md.splitlines()
    tables = 0
    i = 0
    while i < len(lines) - 1:
        if _TABLE_SEP_RE.match(lines[i]) and _TABLE_DIV_RE.match(lines[i + 1]):
            tables += 1
            # skip until blank line or non-table-ish line
            i += 2
            while i < len(lines) and ("|" in lines[i]):
                i += 1
        else:
            i += 1
    return tables


def count_entities_rows(md: str) -> int:
    # Heuristic: find a table that looks like entities; count body rows.
    if not md:
        return 0
    # Look for a section heading containing "Entities" or "實體"
    # then find first markdown table after it and count rows excluding header/divider
    lines = md.splitlines()
    idxs = [i for i, ln in enumerate(lines) if re.search(r"(entities|實體|实体)", ln, re.I)]
    start = idxs[0] if idxs else 0
    # find table header
    for i in range(start, len(lines) - 1):
        if _TABLE_SEP_RE.match(lines[i]) and _TABLE_DIV_RE.match(lines[i + 1]):
            # count body rows
            body = 0
            j = i + 2
            while j < len(lines) and ("|" in lines[j]) and lines[j].strip():
                # ignore purely divider lines if any
                if not _TABLE_DIV_RE.match(lines[j]):
                    body += 1
                j += 1
            return max(0, body)
    return 0


def render_quality_gate_card(
    md: str,
    gate_name: str,
    word_range: Optional[Tuple[int, int]] = None,
    min_tables: Optional[int] = None,
    entities_target: Optional[int] = None,
):
    wc = estimate_word_count(md)
    tc = count_markdown_tables(md)
    ec = count_entities_rows(md)

    # compute pass/fail
    pass_wc = True
    if word_range:
        pass_wc = (word_range[0] <= wc <= word_range[1])

    pass_tc = True
    if min_tables is not None:
        pass_tc = (tc >= min_tables)

    pass_ec = True
    if entities_target is not None:
        pass_ec = (ec >= entities_target)

    all_pass = pass_wc and pass_tc and pass_ec

    grad = "linear-gradient(135deg,#22c55e,#16a34a)" if all_pass else "linear-gradient(135deg,#f97316,#ea580c)"
    if not all_pass and ((word_range and wc < word_range[0]) or (min_tables and tc < min_tables) or (entities_target and ec < entities_target)):
        grad = "linear-gradient(135deg,#ef4444,#b91c1c)"

    badges = []
    if word_range:
        badges.append(f"Words: {wc} (target {word_range[0]}–{word_range[1]}) {'✅' if pass_wc else '❌'}")
    else:
        badges.append(f"Words: {wc}")
    if min_tables is not None:
        badges.append(f"Tables: {tc} (min {min_tables}) {'✅' if pass_tc else '❌'}")
    else:
        badges.append(f"Tables: {tc}")
    if entities_target is not None:
        badges.append(f"Entities rows: {ec} (min {entities_target}) {'✅' if pass_ec else '❌'}")
    else:
        badges.append(f"Entities rows: {ec}")

    st.markdown(
        f"""
        <div class="wow-card" style="background:{grad};color:#f8fafc;">
          <div class="wow-card-title">{gate_name}</div>
          <div class="wow-card-main">{'PASS' if all_pass else 'CHECK'}</div>
          <div style="margin-top:6px;">
            {''.join([f'<span class="wow-badge">{st._escape_html(b)}</span>' for b in badges])}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =============================================================================
# Unified agent runner UI (prompt/model overrides + editable output)
# =============================================================================

def agent_run_ui(
    *,
    agent_id: str,
    tab_key: str,
    default_prompt: str,
    default_input_text: str = "",
    allow_model_override: bool = True,
    tab_label_for_history: Optional[str] = None,
    language_hint: Optional[str] = None,
):
    """
    A reusable runner:
    - loads agent default from agents.yaml if present
    - allows prompt/model/max_tokens overrides
    - runs LLM call, logs events, shows editable output (md/plain)
    """
    agents_cfg = st.session_state.get("agents_cfg", {})
    agents_dict = agents_cfg.get("agents", {})

    agent_cfg = agents_dict.get(agent_id, {
        "name": agent_id,
        "model": st.session_state.settings["model"],
        "system_prompt": "",
        "max_tokens": st.session_state.settings["max_tokens"],
        "category": "Custom",
    })

    if f"{tab_key}_status" not in st.session_state:
        st.session_state[f"{tab_key}_status"] = "pending"

    agent_name = agent_cfg.get("name", agent_id)
    status = st.session_state[f"{tab_key}_status"]
    show_status_line(agent_name, status)

    # controls
    col1, col2, col3 = st.columns([2.2, 1.0, 1.0])
    with col1:
        prompt_value = st.session_state.get(f"{tab_key}_prompt", default_prompt)
        user_prompt = st.text_area(
            t("Prompt"),
            value=prompt_value,
            height=170,
            key=f"{tab_key}_prompt",
        )
        if language_hint:
            st.caption(language_hint)

    with col2:
        base_model = agent_cfg.get("model", st.session_state.settings["model"])
        model_list = list(dict.fromkeys(ALL_MODELS + [base_model]))  # ensure base_model appears
        model_index = model_list.index(base_model) if base_model in model_list else 0
        model = st.selectbox(
            t("Model"),
            model_list,
            index=model_index,
            disabled=not allow_model_override,
            key=f"{tab_key}_model",
        )

    with col3:
        max_tokens_default = int(agent_cfg.get("max_tokens", st.session_state.settings["max_tokens"]))
        max_tokens = st.number_input(
            "max_tokens",
            min_value=1000,
            max_value=120000,
            value=int(st.session_state.get(f"{tab_key}_max_tokens", max_tokens_default)),
            step=1000,
            key=f"{tab_key}_max_tokens",
        )

    input_text = st.text_area(
        t("Input Text / Markdown"),
        value=st.session_state.get(f"{tab_key}_input", default_input_text),
        height=240,
        key=f"{tab_key}_input",
    )

    run = st.button(t("Run Agent"), key=f"{tab_key}_run")
    if run:
        st.session_state[f"{tab_key}_status"] = "running"
        show_status_line(agent_name, "running")

        api_keys = st.session_state.get("api_keys", {})
        system_prompt = agent_cfg.get("system_prompt", "") or ""
        user_full = f"{user_prompt}\n\n---\n\n{input_text}".strip()
        tokens_est = approx_tokens(system_prompt + "\n" + user_full)

        log_live({
            "ts": utc_ts(),
            "event_type": "run_start",
            "tab": tab_label_for_history or tab_key,
            "agent": agent_name,
            "model": model,
            "provider": get_provider(model),
            "status": "running",
            "tokens_est": tokens_est,
            "message": "Started run.",
        })

        with st.spinner("Running agent..."):
            try:
                out, meta = call_llm(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_full,
                    max_tokens=int(max_tokens),
                    temperature=float(st.session_state.settings["temperature"]),
                    api_keys=api_keys,
                )
                st.session_state[f"{tab_key}_output"] = out
                st.session_state[f"{tab_key}_status"] = "done"

                log_live({
                    "ts": utc_ts(),
                    "event_type": "run_complete",
                    "tab": tab_label_for_history or tab_key,
                    "agent": agent_name,
                    "model": model,
                    "provider": meta.get("provider"),
                    "status": "done",
                    "tokens_est": meta.get("tokens_est_total", approx_tokens(user_full + out)),
                    "duration_ms": meta.get("duration_ms"),
                    "message": "Completed run.",
                })
            except Exception as e:
                st.session_state[f"{tab_key}_status"] = "error"
                err = str(e)
                st.error(f"Agent error: {err}")
                log_live({
                    "ts": utc_ts(),
                    "event_type": "run_complete",
                    "tab": tab_label_for_history or tab_key,
                    "agent": agent_name,
                    "model": model,
                    "provider": get_provider(model),
                    "status": "error",
                    "tokens_est": tokens_est,
                    "duration_ms": None,
                    "message": f"Error: {err}",
                })

    output = st.session_state.get(f"{tab_key}_output", "")
    view_mode = st.radio(
        t("View mode"),
        [t("Markdown"), t("Plain text")],
        horizontal=True,
        key=f"{tab_key}_viewmode",
    )

    # editable output
    edited = st.text_area(
        t("Output (editable)"),
        value=output,
        height=320,
        key=f"{tab_key}_output_edited",
    )
    st.session_state[f"{tab_key}_effective_output"] = edited

    # downloads
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            t("Download .md"),
            data=(edited or "").encode("utf-8"),
            file_name=f"{tab_key}_output.md",
            mime="text/markdown",
            key=f"{tab_key}_dl_md",
        )
    with col_dl2:
        st.download_button(
            t("Download .txt"),
            data=(edited or "").encode("utf-8"),
            file_name=f"{tab_key}_output.txt",
            mime="text/plain",
            key=f"{tab_key}_dl_txt",
        )


# =============================================================================
# Sidebar
# =============================================================================

def render_sidebar():
    with st.sidebar:
        st.markdown(f"### {t('Global Settings')}")

        st.session_state.settings["theme"] = st.radio(
            t("Theme"),
            ["Light", "Dark"],
            index=0 if st.session_state.settings["theme"] == "Light" else 1,
        )

        st.session_state.settings["language"] = st.radio(
            t("Language"),
            ["English", "繁體中文"],
            index=0 if st.session_state.settings["language"] == "English" else 1,
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            style = st.selectbox(
                t("Painter Style"),
                PAINTER_STYLES,
                index=PAINTER_STYLES.index(st.session_state.settings["painter_style"]),
            )
        with col2:
            if st.button(t("Jackpot!")):
                style = random.choice(PAINTER_STYLES)
        st.session_state.settings["painter_style"] = style

        st.session_state.settings["model"] = st.selectbox(
            t("Default Model"),
            ALL_MODELS,
            index=ALL_MODELS.index(st.session_state.settings["model"]) if st.session_state.settings["model"] in ALL_MODELS else 0,
        )
        st.session_state.settings["max_tokens"] = st.number_input(
            t("Default max_tokens"),
            min_value=1000,
            max_value=120000,
            value=int(st.session_state.settings["max_tokens"]),
            step=1000,
        )
        st.session_state.settings["temperature"] = st.slider(
            t("Temperature"),
            0.0,
            1.0,
            float(st.session_state.settings["temperature"]),
            0.05,
        )

        st.markdown("---")
        st.markdown(f"### {t('API Keys')}")

        keys = {}

        if os.getenv("OPENAI_API_KEY"):
            keys["openai"] = os.getenv("OPENAI_API_KEY")
            st.caption("OpenAI key: from environment (hidden).")
        else:
            keys["openai"] = st.text_input("OpenAI API Key", type="password")

        if os.getenv("GEMINI_API_KEY"):
            keys["gemini"] = os.getenv("GEMINI_API_KEY")
            st.caption("Gemini key: from environment (hidden).")
        else:
            keys["gemini"] = st.text_input("Gemini API Key", type="password")

        if os.getenv("ANTHROPIC_API_KEY"):
            keys["anthropic"] = os.getenv("ANTHROPIC_API_KEY")
            st.caption("Anthropic key: from environment (hidden).")
        else:
            keys["anthropic"] = st.text_input("Anthropic API Key", type="password")

        if os.getenv("GROK_API_KEY"):
            keys["grok"] = os.getenv("GROK_API_KEY")
            st.caption("Grok key: from environment (hidden).")
        else:
            keys["grok"] = st.text_input("Grok API Key", type="password")

        st.session_state["api_keys"] = keys

        # Provider readiness quick wall
        st.markdown("### WOW Provider Readiness")
        pr = provider_readiness()
        badge_map = {"env": ("✅ env", "#22c55e"), "session": ("🟦 session", "#60a5fa"), "missing": ("⚠️ missing", "#f59e0b")}
        for p in ["openai", "gemini", "anthropic", "grok"]:
            label, _ = badge_map[pr[p]]
            st.caption(f"{p}: {label}")

        st.markdown("---")
        st.markdown(f"### {t('Agents Catalog (agents.yaml)')}")
        uploaded_agents = st.file_uploader(
            t("Upload custom agents.yaml"),
            type=["yaml", "yml"],
            key="sidebar_agents_yaml",
        )
        if uploaded_agents is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents.read())
                if isinstance(cfg, dict) and "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Custom agents.yaml loaded for this session.")
                else:
                    st.warning("Uploaded YAML has no top-level 'agents' key. Keeping previous config.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")

        st.markdown("---")
        with st.expander(t("Live Log"), expanded=False):
            render_live_log_panel(filter_tab=None, height=260, limit=100)


# =============================================================================
# Dashboard
# =============================================================================

def render_dashboard():
    st.title(t("Dashboard"))

    # WOW top banner
    pr = provider_readiness()
    missing = [k for k, v in pr.items() if v == "missing"]
    warn = ""
    if missing:
        warn = f"Missing keys: {', '.join(missing)} (some models will fail)."
    st.markdown(
        f"""
        <div class="wow-card" style="background:linear-gradient(135deg,#0ea5e9,#2563eb);color:#f8fafc;">
          <div class="wow-card-title">{st._escape_html(t('app_title'))}</div>
          <div class="wow-card-main">WOW Dashboard</div>
          <div style="margin-top:6px;font-size:0.95rem;opacity:0.95;">
            Theme: <b>{st.session_state.settings['theme']}</b> ·
            UI Language: <b>{st.session_state.settings['language']}</b> ·
            Style: <b>{st.session_state.settings['painter_style']}</b><br>
            {st._escape_html(warn) if warn else ""}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hist = st.session_state.get("history", [])
    if not hist:
        st.info("No runs yet.")
        st.markdown("### " + t("Live Log"))
        render_live_log_panel(filter_tab=None, height=320, limit=200)
        return

    df = pd.DataFrame(hist)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Runs", len(df))
    with col2:
        st.metric("Unique Tabs", int(df["tab"].nunique()) if "tab" in df.columns else 0)
    with col3:
        st.metric("Approx Tokens", int(df["tokens_est"].sum()) if "tokens_est" in df.columns else 0)
    with col4:
        ok_rate = (df["status"].eq("done").mean() * 100) if "status" in df.columns else 0
        st.metric("Success Rate", f"{ok_rate:.0f}%")

    # WOW latest snapshot
    st.markdown("### WOW Status Wall — Latest Activity")
    last = df.sort_values("ts", ascending=False).iloc[0]
    tok = int(last.get("tokens_est", 0) or 0)
    grad = "linear-gradient(135deg,#22c55e,#16a34a)"
    if tok > 40000:
        grad = "linear-gradient(135deg,#f97316,#ea580c)"
    if tok > 80000:
        grad = "linear-gradient(135deg,#ef4444,#b91c1c)"
    st.markdown(
        f"""
        <div class="wow-card" style="background:{grad};color:#f8fafc;">
          <div class="wow-card-title">LATEST RUN SNAPSHOT</div>
          <div class="wow-card-main">{st._escape_html(str(last.get('tab','')))} · {st._escape_html(str(last.get('agent','')))}</div>
          <div style="margin-top:6px;font-size:0.92rem;">
            Model: <b>{st._escape_html(str(last.get('model','')))}</b> · Provider: <b>{st._escape_html(str(last.get('provider','')))}</b><br>
            Tokens ≈ <b>{tok}</b> · Duration: <b>{(float(last.get('duration_ms',0))/1000):.1f}s</b> · Status: <b>{st._escape_html(str(last.get('status','')))}</b><br>
            Time (UTC): {st._escape_html(str(last.get('ts','')))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Runs by Tab")
    chart_tab = alt.Chart(df).mark_bar().encode(
        x=alt.X("tab:N", sort="-y"),
        y="count():Q",
        color="tab:N",
        tooltip=["tab", "count()"],
    )
    st.altair_chart(chart_tab, use_container_width=True)

    st.markdown("### Runs by Model")
    chart_model = alt.Chart(df).mark_bar().encode(
        x=alt.X("model:N", sort="-y"),
        y="count():Q",
        color="model:N",
        tooltip=["model", "count()"],
    )
    st.altair_chart(chart_model, use_container_width=True)

    st.markdown("### Model × Tab Usage Heatmap")
    heat_df = df.groupby(["tab", "model"]).size().reset_index(name="count")
    heatmap = alt.Chart(heat_df).mark_rect().encode(
        x=alt.X("model:N", title="Model"),
        y=alt.Y("tab:N", title="Tab"),
        color=alt.Color("count:Q", scale=alt.Scale(scheme="blues"), title="Runs"),
        tooltip=["tab", "model", "count"],
    ).properties(height=260)
    st.altair_chart(heatmap, use_container_width=True)

    st.markdown("### Token Usage Over Time")
    df_time = df.copy()
    if "ts" in df_time.columns:
        chart_time = alt.Chart(df_time.dropna(subset=["ts"])).mark_line(point=True).encode(
            x="ts:T",
            y="tokens_est:Q",
            color="tab:N",
            tooltip=["ts", "tab", "agent", "model", "tokens_est", "status"],
        )
        st.altair_chart(chart_time, use_container_width=True)

    st.markdown("### Recent Activity")
    st.dataframe(df.sort_values("ts", ascending=False).head(30), use_container_width=True)

    st.markdown("### " + t("Live Log"))
    render_live_log_panel(filter_tab=None, height=320, limit=200)


# =============================================================================
# TW Premarket (kept close to original, with minor additions)
# =============================================================================

TW_APP_FIELDS = [
    "doc_no", "e_no", "apply_date", "case_type", "device_category", "case_kind",
    "origin", "product_class", "similar", "replace_flag", "prior_app_no",
    "name_zh", "name_en", "indications", "spec_comp",
    "main_cat", "item_code", "item_name",
    "uniform_id", "firm_name", "firm_addr",
    "resp_name", "contact_name", "contact_tel", "contact_fax", "contact_email",
    "confirm_match", "cert_raps", "cert_ahwp", "cert_other",
    "manu_type", "manu_name", "manu_country", "manu_addr", "manu_note",
    "auth_applicable", "auth_desc",
    "cfs_applicable", "cfs_desc",
    "qms_applicable", "qms_desc",
    "similar_info", "labeling_info", "tech_file_info",
    "preclinical_info", "preclinical_replace",
    "clinical_just", "clinical_info",
]


def build_tw_app_dict_from_session() -> dict:
    s = st.session_state
    apply_date = s.get("tw_apply_date")
    apply_date_str = apply_date.strftime("%Y-%m-%d") if apply_date else ""
    return {
        "doc_no": s.get("tw_doc_no", ""),
        "e_no": s.get("tw_e_no", ""),
        "apply_date": apply_date_str,
        "case_type": s.get("tw_case_type", ""),
        "device_category": s.get("tw_device_category", ""),
        "case_kind": s.get("tw_case_kind", ""),
        "origin": s.get("tw_origin", ""),
        "product_class": s.get("tw_product_class", ""),
        "similar": s.get("tw_similar", ""),
        "replace_flag": s.get("tw_replace_flag", ""),
        "prior_app_no": s.get("tw_prior_app_no", ""),
        "name_zh": s.get("tw_dev_name_zh", ""),
        "name_en": s.get("tw_dev_name_en", ""),
        "indications": s.get("tw_indications", ""),
        "spec_comp": s.get("tw_spec_comp", ""),
        "main_cat": s.get("tw_main_cat", ""),
        "item_code": s.get("tw_item_code", ""),
        "item_name": s.get("tw_item_name", ""),
        "uniform_id": s.get("tw_uniform_id", ""),
        "firm_name": s.get("tw_firm_name", ""),
        "firm_addr": s.get("tw_firm_addr", ""),
        "resp_name": s.get("tw_resp_name", ""),
        "contact_name": s.get("tw_contact_name", ""),
        "contact_tel": s.get("tw_contact_tel", ""),
        "contact_fax": s.get("tw_contact_fax", ""),
        "contact_email": s.get("tw_contact_email", ""),
        "confirm_match": bool(s.get("tw_confirm_match", False)),
        "cert_raps": bool(s.get("tw_cert_raps", False)),
        "cert_ahwp": bool(s.get("tw_cert_ahwp", False)),
        "cert_other": s.get("tw_cert_other", ""),
        "manu_type": s.get("tw_manu_type", ""),
        "manu_name": s.get("tw_manu_name", ""),
        "manu_country": s.get("tw_manu_country", ""),
        "manu_addr": s.get("tw_manu_addr", ""),
        "manu_note": s.get("tw_manu_note", ""),
        "auth_applicable": s.get("tw_auth_app", ""),
        "auth_desc": s.get("tw_auth_desc", ""),
        "cfs_applicable": s.get("tw_cfs_app", ""),
        "cfs_desc": s.get("tw_cfs_desc", ""),
        "qms_applicable": s.get("tw_qms_app", ""),
        "qms_desc": s.get("tw_qms_desc", ""),
        "similar_info": s.get("tw_similar_info", ""),
        "labeling_info": s.get("tw_labeling_info", ""),
        "tech_file_info": s.get("tw_tech_file_info", ""),
        "preclinical_info": s.get("tw_preclinical_info", ""),
        "preclinical_replace": s.get("tw_preclinical_replace", ""),
        "clinical_just": s.get("tw_clinical_app", ""),
        "clinical_info": s.get("tw_clinical_info", ""),
    }


def apply_tw_app_dict_to_session(data: dict):
    s = st.session_state
    s["tw_doc_no"] = data.get("doc_no", "")
    s["tw_e_no"] = data.get("e_no", "")

    from datetime import date
    try:
        if data.get("apply_date"):
            y, m, d = map(int, str(data["apply_date"]).split("-"))
            s["tw_apply_date"] = date(y, m, d)
    except Exception:
        pass

    s["tw_case_type"] = data.get("case_type", "")
    s["tw_device_category"] = data.get("device_category", "")
    s["tw_case_kind"] = data.get("case_kind", "")
    s["tw_origin"] = data.get("origin", "")
    s["tw_product_class"] = data.get("product_class", "")
    s["tw_similar"] = data.get("similar", "")
    s["tw_replace_flag"] = data.get("replace_flag", "")
    s["tw_prior_app_no"] = data.get("prior_app_no", "")
    s["tw_dev_name_zh"] = data.get("name_zh", "")
    s["tw_dev_name_en"] = data.get("name_en", "")
    s["tw_indications"] = data.get("indications", "")
    s["tw_spec_comp"] = data.get("spec_comp", "")
    s["tw_main_cat"] = data.get("main_cat", "")
    s["tw_item_code"] = data.get("item_code", "")
    s["tw_item_name"] = data.get("item_name", "")
    s["tw_uniform_id"] = data.get("uniform_id", "")
    s["tw_firm_name"] = data.get("firm_name", "")
    s["tw_firm_addr"] = data.get("firm_addr", "")
    s["tw_resp_name"] = data.get("resp_name", "")
    s["tw_contact_name"] = data.get("contact_name", "")
    s["tw_contact_tel"] = data.get("contact_tel", "")
    s["tw_contact_fax"] = data.get("contact_fax", "")
    s["tw_contact_email"] = data.get("contact_email", "")
    s["tw_confirm_match"] = bool(data.get("confirm_match", False))
    s["tw_cert_raps"] = bool(data.get("cert_raps", False))
    s["tw_cert_ahwp"] = bool(data.get("cert_ahwp", False))
    s["tw_cert_other"] = data.get("cert_other", "")
    s["tw_manu_type"] = data.get("manu_type", "")
    s["tw_manu_name"] = data.get("manu_name", "")
    s["tw_manu_country"] = data.get("manu_country", "")
    s["tw_manu_addr"] = data.get("manu_addr", "")
    s["tw_manu_note"] = data.get("manu_note", "")
    s["tw_auth_app"] = data.get("auth_applicable", "")
    s["tw_auth_desc"] = data.get("auth_desc", "")
    s["tw_cfs_app"] = data.get("cfs_applicable", "")
    s["tw_cfs_desc"] = data.get("cfs_desc", "")
    s["tw_qms_app"] = data.get("qms_applicable", "")
    s["tw_qms_desc"] = data.get("qms_desc", "")
    s["tw_similar_info"] = data.get("similar_info", "")
    s["tw_labeling_info"] = data.get("labeling_info", "")
    s["tw_tech_file_info"] = data.get("tech_file_info", "")
    s["tw_preclinical_info"] = data.get("preclinical_info", "")
    s["tw_preclinical_replace"] = data.get("preclinical_replace", "")
    s["tw_clinical_app"] = data.get("clinical_just", "")
    s["tw_clinical_info"] = data.get("clinical_info", "")


def standardize_tw_app_info_with_llm(raw_obj) -> dict:
    api_keys = st.session_state.get("api_keys", {})
    model = "gemini-2.5-flash"
    if (not api_keys.get("gemini")) and (not os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("No Gemini API key available for standardizing application info.")

    raw_json = json.dumps(raw_obj, ensure_ascii=False, indent=2)
    fields_str = ", ".join(TW_APP_FIELDS)

    system_prompt = f"""
You are a data normalization assistant for a Taiwanese TFDA medical device premarket application.

Goal:
Map arbitrary JSON or CSV-like key/value structures into a STANDARD JSON object
that uses EXACTLY the following top-level keys (all strings except where noted):

{fields_str}

Rules:
- Output MUST be a single JSON object (no markdown, no comments).
- Every key above MUST appear in the JSON.
- If information for a field is clearly not present, set it to an empty string,
  or for boolean-like fields use `false`.
- Map semantically similar keys to the standard keys.
- `apply_date` should be 'YYYY-MM-DD' if you can infer; otherwise empty string.
- Do NOT invent new facts; just reorganize/rename what exists.
"""
    user_prompt = f"Here is the raw data to normalize:\n\n{raw_json}"
    out, _ = call_llm(
        model=model,
        system_prompt=system_prompt.strip(),
        user_prompt=user_prompt,
        max_tokens=4000,
        temperature=0.1,
        api_keys=api_keys,
    )

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        start = out.find("{")
        end = out.rfind("}")
        if start != -1 and end != -1 and end > start:
            data = json.loads(out[start:end + 1])
        else:
            raise RuntimeError("LLM did not return valid JSON for application info.")
    if not isinstance(data, dict):
        raise RuntimeError("Standardized application info is not a JSON object.")

    for k in TW_APP_FIELDS:
        if k not in data:
            data[k] = "" if k not in ("confirm_match", "cert_raps", "cert_ahwp") else False
    return data


def compute_tw_app_completeness() -> float:
    s = st.session_state
    required_keys = [
        "tw_e_no", "tw_case_type", "tw_device_category",
        "tw_origin", "tw_product_class",
        "tw_dev_name_zh", "tw_dev_name_en",
        "tw_uniform_id", "tw_firm_name", "tw_firm_addr",
        "tw_resp_name", "tw_contact_name", "tw_contact_tel",
        "tw_contact_email",
        "tw_manu_name", "tw_manu_addr",
    ]
    filled = 0
    for k in required_keys:
        v = s.get(k, "")
        if isinstance(v, str):
            if v.strip():
                filled += 1
        else:
            if v:
                filled += 1
    return filled / len(required_keys) if required_keys else 0.0


def render_tw_premarket_tab():
    st.title(t("TW Premarket"))

    st.markdown(
        """
        <div class="wow-card" style="background:rgba(255,255,255,0.28);">
          <div class="wow-card-title">Workflow</div>
          <div style="font-size:0.95rem;line-height:1.55;">
            <b>Step 1.</b> 線上填寫 / JSON/CSV 匯入申請欄位 → 生成 Markdown 草稿<br>
            <b>Step 2.</b> 貼上或上傳預審/形式審查指引（可選）<br>
            <b>Step 3.</b> 形式審查代理輸出預審報告（可編輯）<br>
            <b>Step 4.</b> 文件編修代理優化申請書（可編輯）<br>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Import / Export
    st.markdown("### Application Info 匯入 / 匯出 (JSON / CSV)")
    col_ie1, col_ie2 = st.columns(2)

    with col_ie1:
        st.markdown("**上傳 Application Info**")
        app_file = st.file_uploader(
            "Upload Application Info (JSON / CSV)",
            type=["json", "csv"],
            key="tw_app_upload",
        )
        if app_file is not None:
            try:
                if app_file.name.lower().endswith(".json"):
                    raw_data = json.load(app_file)
                else:
                    df_up = pd.read_csv(app_file)
                    raw_data = df_up.to_dict(orient="records")[0] if len(df_up) else None
                if raw_data is not None:
                    if isinstance(raw_data, dict) and all(k in raw_data for k in TW_APP_FIELDS):
                        standardized = raw_data
                    else:
                        with st.spinner("使用 LLM 將欄位轉為標準 TFDA 申請書格式..."):
                            standardized = standardize_tw_app_info_with_llm(raw_data)
                    apply_tw_app_dict_to_session(standardized)
                    st.session_state["tw_app_last_loaded"] = standardized
                    log_live({
                        "ts": utc_ts(),
                        "event_type": "info",
                        "tab": "TW Premarket",
                        "agent": "Importer",
                        "model": "",
                        "provider": "",
                        "status": "done",
                        "tokens_est": 0,
                        "message": "Imported and applied application info.",
                    })
                    st.success("已將上傳資料轉換並套用至申請表單。")
                    st.rerun()
            except Exception as e:
                st.error(f"上傳或標準化失敗：{e}")

    with col_ie2:
        st.markdown("**下載 Application Info**")
        app_dict = build_tw_app_dict_from_session()
        json_bytes = json.dumps(app_dict, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button("Download JSON", data=json_bytes, file_name="tw_premarket_application.json", mime="application/json")
        df_app = pd.DataFrame([app_dict])
        csv_bytes = df_app.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv_bytes, file_name="tw_premarket_application.csv", mime="text/csv")

    if "tw_app_last_loaded" in st.session_state:
        st.markdown("**最近載入/標準化之 Application JSON 預覽**")
        st.json(st.session_state["tw_app_last_loaded"], expanded=False)

    st.markdown("---")

    # Completeness WOW card
    completeness = compute_tw_app_completeness()
    pct = int(completeness * 100)
    if pct >= 80:
        card_grad = "linear-gradient(135deg,#22c55e,#16a34a)"
        txt = "申請基本欄位完成度高，適合進行預審。"
    elif pct >= 50:
        card_grad = "linear-gradient(135deg,#f97316,#ea580c)"
        txt = "部分關鍵欄位仍待補齊，建議補足後再送預審。"
    else:
        card_grad = "linear-gradient(135deg,#ef4444,#b91c1c)"
        txt = "多數基本欄位尚未填寫，請先充實申請資訊。"

    st.markdown(
        f"""
        <div class="wow-card" style="background:{card_grad};color:#f8fafc;">
          <div class="wow-card-title">APPLICATION COMPLETENESS</div>
          <div class="wow-card-main">{pct}%</div>
          <div style="margin-top:6px;font-size:0.95rem;">{st._escape_html(txt)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(completeness)

    # Step 1: form (kept minimal; preserves key fields)
    st.markdown("### Step 1 — 線上填寫申請書（草稿）")

    if "tw_app_status" not in st.session_state:
        st.session_state["tw_app_status"] = "pending"
    show_status_line("申請書填寫", st.session_state["tw_app_status"])

    st.markdown("#### 一、案件基本資料")
    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        st.text_input("公文文號", key="tw_doc_no")
        st.text_input("電子流水號", value=st.session_state.get("tw_e_no", "MDE"), key="tw_e_no")
    with col_a2:
        st.date_input("申請日", key="tw_apply_date")
        st.selectbox(
            "案件類型*",
            ["一般申請案", "同一產品不同品名", "專供外銷", "許可證有效期限屆至後六個月內重新申請"],
            key="tw_case_type",
        )
    with col_a3:
        st.selectbox("醫療器材類型*", ["一般醫材", "體外診斷器材(IVD)"], key="tw_device_category")
        st.selectbox("案件種類*", ["新案", "變更案", "展延案"], key="tw_case_kind")

    col_a4, col_a5, col_a6 = st.columns(3)
    with col_a4:
        st.selectbox("產地*", ["國產", "輸入", "陸輸"], key="tw_origin")
    with col_a5:
        st.selectbox("產品等級*", ["第二等級", "第三等級"], key="tw_product_class")
    with col_a6:
        st.selectbox("有無類似品*", ["有", "無", "全球首創"], key="tw_similar")

    st.markdown("#### 二、醫療器材基本資訊")
    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.text_input("醫療器材中文名稱*", key="tw_dev_name_zh")
        st.text_input("醫療器材英文名稱*", key="tw_dev_name_en")
    with col_b2:
        st.text_area("效能、用途或適應症說明", value=st.session_state.get("tw_indications", "詳如核定之中文說明書"), key="tw_indications")
        st.text_area("型號、規格或主要成分說明", value=st.session_state.get("tw_spec_comp", "詳如核定之中文說明書"), key="tw_spec_comp")

    st.markdown("#### 三、醫療器材商資料")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.text_input("統一編號*", key="tw_uniform_id")
        st.text_input("醫療器材商名稱*", key="tw_firm_name")
        st.text_area("醫療器材商地址*", height=80, key="tw_firm_addr")
    with col_c2:
        st.text_input("負責人姓名*", key="tw_resp_name")
        st.text_input("聯絡人姓名*", key="tw_contact_name")
        st.text_input("電話*", key="tw_contact_tel")
        st.text_input("電子郵件*", key="tw_contact_email")

    st.markdown("#### 四、製造廠資訊")
    st.radio(
        "製造方式",
        ["單一製造廠", "全部製程委託製造", "委託非全部製程之製造/包裝/貼標/滅菌及最終驗放"],
        index=0,
        key="tw_manu_type",
    )
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.text_input("製造廠名稱*", key="tw_manu_name")
        st.selectbox(
            "製造國別*",
            ["TAIWAN， ROC", "UNITED STATES", "EU (Member State)", "JAPAN", "CHINA", "KOREA， REPUBLIC OF", "OTHER"],
            key="tw_manu_country",
        )
    with col_d2:
        st.text_area("製造廠地址*", height=80, key="tw_manu_addr")
        st.text_area("製造相關說明", height=80, key="tw_manu_note")

    # Generate application markdown
    if st.button("生成申請書 Markdown 草稿", key="tw_generate_md_btn"):
        app_dict = build_tw_app_dict_from_session()
        missing = []
        must = [
            ("e_no", "電子流水號"), ("case_type", "案件類型"), ("device_category", "醫療器材類型"),
            ("origin", "產地"), ("product_class", "產品等級"),
            ("name_zh", "中文名稱"), ("name_en", "英文名稱"),
            ("uniform_id", "統一編號"), ("firm_name", "醫材商名稱"), ("firm_addr", "醫材商地址"),
            ("resp_name", "負責人"), ("contact_name", "聯絡人"), ("contact_tel", "電話"), ("contact_email", "Email"),
            ("manu_name", "製造廠名稱"), ("manu_addr", "製造廠地址"),
        ]
        for k, label in must:
            v = app_dict.get(k, "")
            if isinstance(v, str) and not v.strip():
                missing.append(label)

        if missing:
            st.session_state["tw_app_status"] = "error"
            st.warning("以下基本欄位尚未填寫完整（形式檢查）：\n- " + "\n- ".join(missing))
        else:
            st.session_state["tw_app_status"] = "done"

        app_md = f"""# 第二、三等級醫療器材查驗登記申請書（線上草稿）

## 一、案件基本資料
- 公文文號：{app_dict.get('doc_no') or "（未填）"}
- 電子流水號：{app_dict.get('e_no') or "（未填）"}
- 申請日：{app_dict.get('apply_date') or "（未填）"}
- 案件類型：{app_dict.get('case_type')}
- 醫療器材類型：{app_dict.get('device_category')}
- 案件種類：{app_dict.get('case_kind')}
- 產地：{app_dict.get('origin')}
- 產品等級：{app_dict.get('product_class')}
- 有無類似品：{app_dict.get('similar')}

## 二、醫療器材基本資訊
- 中文名稱：{app_dict.get('name_zh')}
- 英文名稱：{app_dict.get('name_en')}
- 效能、用途或適應症說明：{app_dict.get('indications')}
- 型號、規格或主要成分：{app_dict.get('spec_comp')}

## 三、醫療器材商資料
- 統一編號：{app_dict.get('uniform_id')}
- 名稱：{app_dict.get('firm_name')}
- 地址：{app_dict.get('firm_addr')}
- 負責人：{app_dict.get('resp_name')}
- 聯絡人：{app_dict.get('contact_name')}
- 電話：{app_dict.get('contact_tel')}
- Email：{app_dict.get('contact_email')}

## 四、製造廠資訊
- 製造方式：{app_dict.get('manu_type')}
- 製造廠名稱：{app_dict.get('manu_name')}
- 製造國別：{app_dict.get('manu_country')}
- 製造廠地址：{app_dict.get('manu_addr')}
- 製造相關說明：{app_dict.get('manu_note')}
"""
        st.session_state["tw_app_markdown"] = app_md
        log_live({
            "ts": utc_ts(),
            "event_type": "info",
            "tab": "TW Premarket",
            "agent": "Markdown Generator",
            "model": "",
            "provider": "",
            "status": "done",
            "tokens_est": approx_tokens(app_md),
            "message": "Generated TW application markdown draft.",
        })

    st.markdown("##### 申請書 Markdown（可編輯）")
    app_md_current = st.session_state.get("tw_app_markdown", "")
    st.text_area("申請書內容", value=app_md_current, height=260, key="tw_app_md_edited")
    st.session_state["tw_app_effective_md"] = st.session_state.get("tw_app_md_edited", "")

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Download .md", data=st.session_state["tw_app_effective_md"].encode("utf-8"),
                           file_name="tw_application.md", mime="text/markdown")
    with col_dl2:
        st.download_button("Download .txt", data=st.session_state["tw_app_effective_md"].encode("utf-8"),
                           file_name="tw_application.txt", mime="text/plain")

    st.markdown("---")
    st.markdown("### Step 2 — 輸入預審/形式審查指引（可選）")

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        guidance_file = st.file_uploader("上傳預審指引 (PDF / TXT / MD)", type=["pdf", "txt", "md"], key="tw_guidance_file")
        guidance_text_from_file = ""
        if guidance_file is not None:
            suffix = guidance_file.name.lower().rsplit(".", 1)[-1]
            if suffix == "pdf":
                guidance_text_from_file = extract_pdf_pages_to_text(guidance_file, 1, 9999)
            else:
                guidance_text_from_file = guidance_file.read().decode("utf-8", errors="ignore")
    with col_g2:
        guidance_text_manual = st.text_area("或直接貼上預審/形式審查指引文字或 Markdown", height=180, key="tw_guidance_manual")

    guidance_text = guidance_text_from_file or guidance_text_manual
    st.session_state["tw_guidance_text"] = guidance_text

    st.markdown("---")
    st.markdown("### Step 3 — 形式審查 / 完整性檢核（Agent）")
    combined_input = f"""=== 申請書草稿（Markdown） ===
{st.session_state.get("tw_app_effective_md","")}

=== 預審 / 形式審查指引（文字/Markdown） ===
{guidance_text or "（尚未提供指引，請依一般法規常規進行形式檢核）"}
"""

    default_screen_prompt = """你是一位熟悉臺灣「第二、三等級醫療器材查驗登記」的形式審查(預審)審查員。

請根據申請書草稿與預審指引（如有），以繁體中文 Markdown 輸出預審報告，包含：
1) 文件類別完整性檢核表
2) 重要欄位矛盾/缺漏清單
3) 預審評語摘要（300–600字）
4) 明確標註「依現有輸入無法判斷」的地方，不要臆測
"""
    agent_run_ui(
        agent_id="tw_screen_review_agent",
        tab_key="tw_screen",
        default_prompt=default_screen_prompt,
        default_input_text=combined_input,
        allow_model_override=True,
        tab_label_for_history="TW Premarket Screen Review",
    )

    st.markdown("---")
    st.markdown("### Step 4 — AI 協助編修申請書內容（Agent）")
    helper_default_prompt = """你是一位協助臺灣醫療器材查驗登記申請人的文件撰寫助手。

請在不改變實際內容的前提下，優化申請書草稿的結構、標題層級、語句通順。
不得自行新增原文沒有的關鍵技術/法規/臨床資訊。
資訊不足處以「※待補：...」標註提醒。輸出 Markdown。
"""
    agent_run_ui(
        agent_id="tw_app_doc_helper",
        tab_key="tw_app_helper",
        default_prompt=helper_default_prompt,
        default_input_text=st.session_state.get("tw_app_effective_md", ""),
        allow_model_override=True,
        tab_label_for_history="TW Application Doc Helper",
    )

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="TW Premarket", height=260, limit=120)


# =============================================================================
# 510(k) Intelligence
# =============================================================================

def render_510k_intel_tab():
    st.title(t("510k_tab"))

    col1, col2 = st.columns(2)
    with col1:
        device_name = st.text_input("Device Name", key="intel_device_name")
        k_number = st.text_input("510(k) Number (e.g., K123456)", key="intel_k_number")
    with col2:
        sponsor = st.text_input("Sponsor / Manufacturer (optional)", key="intel_sponsor")
        product_code = st.text_input("Product Code (optional)", key="intel_product_code")

    extra_info = st.text_area("Additional context (indications, technology, etc.)", key="intel_extra")

    out_lang = st.selectbox(
        t("Output language"),
        ["English", "繁體中文"],
        index=0 if st.session_state.settings.get("language") == "English" else 1,
        key="intel_out_lang",
    )

    default_prompt = f"""
You are assisting an FDA 510(k) reviewer.

Task:
1) Create a detailed, review-oriented summary for the provided device inputs.
2) Organize the output as Markdown with headings and multiple tables (overview, indications, testing, risks).
3) Do not invent unknown facts; clearly label unknowns and assumptions.

Output language: {out_lang}.
"""
    combined_input = f"""=== Device Inputs ===
Device name: {device_name}
510(k) number: {k_number}
Sponsor: {sponsor}
Product code: {product_code}

Additional context:
{extra_info}
"""
    agent_run_ui(
        agent_id="fda_510k_intel_agent",
        tab_key="intel_510k",
        default_prompt=default_prompt.strip(),
        default_input_text=combined_input.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Intelligence",
    )

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="510(k) Intelligence", height=260, limit=120)


# =============================================================================
# PDF → Markdown
# =============================================================================

def render_pdf_to_md_tab():
    st.title(t("PDF → Markdown"))

    uploaded = st.file_uploader("Upload PDF to convert selected pages to Markdown", type=["pdf"], key="pdf_to_md_uploader")
    if uploaded:
        col1, col2, col3 = st.columns([1, 1, 1.2])
        with col1:
            num_start = st.number_input("From page", min_value=1, value=int(st.session_state.get("pdf_from", 1)), key="pdf_from")
        with col2:
            num_end = st.number_input("To page", min_value=1, value=int(st.session_state.get("pdf_to", 5)), key="pdf_to")
        with col3:
            fidelity = st.selectbox(
                "Table fidelity mode",
                ["Fast", "Structured", "Conservative"],
                index=1,
                key="pdf_table_fidelity",
            )

        if st.button("Extract Text", key="pdf_to_md_extract_btn"):
            text = extract_pdf_pages_to_text(uploaded, int(num_start), int(num_end))
            st.session_state["pdf_raw_text"] = text
            log_live({
                "ts": utc_ts(),
                "event_type": "info",
                "tab": "PDF → Markdown",
                "agent": "PDF Extractor",
                "model": "",
                "provider": "",
                "status": "done",
                "tokens_est": approx_tokens(text),
                "message": f"Extracted pages {int(num_start)}–{int(num_end)} (mode={fidelity}).",
            })

    raw_text = st.session_state.get("pdf_raw_text", "")
    if raw_text:
        fidelity = st.session_state.get("pdf_table_fidelity", "Structured")
        extra = {
            "Fast": "Prioritize speed. Preserve headings/lists; minimal table reconstruction.",
            "Structured": "Attempt Markdown tables where obvious; keep conservative for uncertain cells.",
            "Conservative": "Avoid reconstructing tables unless the structure is clear; do not guess cells.",
        }[fidelity]
        default_prompt = f"""
You are converting PDF-extracted text into clean markdown.

Requirements:
- Preserve headings, lists, and key formatting.
- If there are tables, follow this fidelity policy: {extra}
- Do not hallucinate content not present in the text.

Output language: {st.session_state.settings.get("language","English")}.
"""
        agent_run_ui(
            agent_id="pdf_to_markdown_agent",
            tab_key="pdf_to_md",
            default_prompt=default_prompt.strip(),
            default_input_text=raw_text,
            allow_model_override=True,
            tab_label_for_history="PDF → Markdown",
        )
    else:
        st.info("Upload a PDF and click 'Extract Text' to begin.")

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="PDF → Markdown", height=260, limit=120)


# =============================================================================
# 510(k) Review Pipeline (UPDATED: prompt/model override + editable handoff)
# =============================================================================

def render_510k_review_pipeline_tab():
    st.title(t("Checklist & Report"))

    st.markdown(
        """
        <div class="wow-card" style="background:rgba(255,255,255,0.28);">
          <div class="wow-card-title">Pipeline</div>
          <div style="font-size:0.95rem;line-height:1.55;">
            <b>Step 1</b> Submission Structurer → <b>Step 2</b> Checklist Cleaner (optional) → <b>Step 3</b> Review Memo Builder<br>
            Each step supports <b>prompt edit</b>, <b>model selection</b>, and <b>editable output handoff</b>.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    out_lang = st.selectbox(
        t("Output language"),
        ["English", "繁體中文"],
        index=0 if st.session_state.settings.get("language") == "English" else 1,
        key="pipeline_out_lang",
    )

    # Step 1: structure submission
    st.markdown("## Step 1 — Structure Submission (Agent)")
    raw_subm = st.text_area("Paste 510(k) submission material (text/markdown)", height=180, key="pipe_raw_submission")

    prompt_s1 = f"""You are a 510(k) submission organizer.

Task:
- Restructure the content into organized Markdown sections:
  1) Device & submitter information
  2) Device description and technology
  3) Intended use / indications for use
  4) Predicate / comparator information
  5) Performance testing (bench/software/EMC/biocomp/sterilization/etc. as applicable)
  6) Risks, mitigations, labeling notes
  7) Open questions / missing items
- Do NOT invent facts; explicitly label unknowns.

Output language: {out_lang}.
"""
    agent_run_ui(
        agent_id="fda_510k_submission_structurer",
        tab_key="pipe_s1",
        default_prompt=prompt_s1.strip(),
        default_input_text=raw_subm.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Review Pipeline",
        language_hint="Tip: Keep temperature low for regulatory tasks.",
    )
    structured_submission = st.session_state.get("pipe_s1_effective_output", "").strip()

    st.markdown("## Step 2 — Checklist Cleaner (Optional Agent)")
    chk_raw = st.text_area("Paste checklist (text/markdown)", height=170, key="pipe_raw_checklist")
    prompt_s2 = f"""You are a regulatory checklist normalizer.

Task:
- Convert the checklist into clean Markdown with:
  - clear headings,
  - consistent check items,
  - and a table format if appropriate.
- Do not add new requirements not present in the checklist.
- If the checklist is empty, output an empty markdown section.

Output language: {out_lang}.
"""
    agent_run_ui(
        agent_id="fda_510k_checklist_cleaner",
        tab_key="pipe_s2",
        default_prompt=prompt_s2.strip(),
        default_input_text=chk_raw.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Review Pipeline",
    )
    cleaned_checklist = st.session_state.get("pipe_s2_effective_output", "").strip()

    st.markdown("## Step 3 — Review Memo Builder (Agent)")
    # Handoff: allow user to choose which checklist version to use (raw or cleaned)
    use_cleaned = st.checkbox("Use cleaned checklist output as input (recommended)", value=True, key="pipe_use_cleaned_chk")
    chk_effective = cleaned_checklist if (use_cleaned and cleaned_checklist) else chk_raw

    memo_input = f"""=== CHECKLIST ===
{chk_effective}

=== STRUCTURED SUBMISSION ===
{structured_submission}
"""
    prompt_s3 = f"""You are drafting an internal FDA 510(k) review memo.

Write a comprehensive Markdown review memo that includes:
- Introduction & scope
- Device overview (with a table)
- Predicate / comparator discussion (with a comparison table)
- Checklist-based assessment (use a coverage table that maps checklist items to evidence in submission)
- Performance testing summary (tables as needed)
- Risks, labeling, software/cybersecurity (as applicable)
- Open issues / information requests
- Overall conclusion and recommendation

Rules:
- Do NOT invent facts. If information is missing, state "Not provided" and place it in Open Issues.
- Use multiple tables and clear headings.

Output language: {out_lang}.
"""
    # Guardrails: show warnings if missing prerequisites
    if not structured_submission:
        st.warning("Structured submission is empty — Step 3 quality will be poor. Please run Step 1 or paste structured content.")
    if not chk_effective.strip():
        st.warning("Checklist is empty — Step 3 will still run but will lack checklist mapping.")

    agent_run_ui(
        agent_id="fda_510k_review_memo_builder",
        tab_key="pipe_s3",
        default_prompt=prompt_s3.strip(),
        default_input_text=memo_input.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Review Pipeline",
    )

    with st.expander("WOW Quality Gate (Memo)", expanded=False):
        memo_md = st.session_state.get("pipe_s3_effective_output", "")
        render_quality_gate_card(memo_md, "Memo Quality Gate", word_range=None, min_tables=2, entities_target=None)

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="510(k) Review Pipeline", height=260, limit=160)


# =============================================================================
# NEW: 510(k) Review Report Generator Workspace
# =============================================================================

def render_510k_report_generator_tab():
    st.title(t("510k Report Generator"))

    st.markdown(
        """
        <div class="wow-card" style="background:rgba(255,255,255,0.28);">
          <div class="wow-card-title">WOW Report Studio</div>
          <div style="font-size:0.95rem;line-height:1.55;">
            Paste <b>510(k) review notes</b> + choose/paste a <b>report template</b> → generate a <b>2000–3000 word</b> Markdown report with
            <b>≥5 tables</b> and <b>20 entities with context</b>. Then generate <b>skill.md</b> so the report process can be reused.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    out_lang = st.selectbox(
        t("Output language"),
        ["English", "繁體中文"],
        index=0 if st.session_state.settings.get("language") == "English" else 1,
        key="rg_out_lang",
    )

    # Step 1 inputs
    st.markdown("## Step 1 — Inputs")
    st.caption("Reminder: Avoid pasting PHI/PII unless authorized. The model will not browse; it only uses your pasted content.")

    notes = st.text_area(
        "Paste 510(k) review notes (text/markdown)",
        height=220,
        key="rg_notes",
    )

    template_mode = st.radio(
        "Template source",
        ["Use default template", "Paste template / existing report"],
        index=0,
        key="rg_template_mode",
        horizontal=True,
    )

    if template_mode == "Use default template":
        default_tpl = DEFAULT_510K_REPORT_TEMPLATE_EN if out_lang == "English" else DEFAULT_510K_REPORT_TEMPLATE_ZH
        tpl = st.text_area("Active template (editable)", value=default_tpl, height=220, key="rg_template_text")
    else:
        tpl = st.text_area("Paste template or previous 510(k) review report (text/markdown)", height=220, key="rg_template_text")

    # readiness WOW
    st.markdown("### WOW Readiness")
    ready_notes = bool(notes.strip())
    ready_tpl = bool(tpl.strip())
    readiness_grad = "linear-gradient(135deg,#22c55e,#16a34a)" if (ready_notes and ready_tpl) else "linear-gradient(135deg,#f97316,#ea580c)"
    st.markdown(
        f"""
        <div class="wow-card" style="background:{readiness_grad};color:#f8fafc;">
          <div class="wow-card-title">INPUT READINESS</div>
          <div class="wow-card-main">{'READY' if (ready_notes and ready_tpl) else 'NEEDS INPUT'}</div>
          <div style="margin-top:6px;">
            <span class="wow-badge">Notes: {'✅' if ready_notes else '❌'}</span>
            <span class="wow-badge">Template: {'✅' if ready_tpl else '❌'}</span>
            <span class="wow-badge">Output language: {st._escape_html(out_lang)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Step 2: Outline & plan agent
    st.markdown("## Step 2 — Normalize & Outline (Agent)")
    outline_input = f"""=== NOTES ===
{notes}

=== TEMPLATE ===
{tpl}
"""
    outline_prompt = f"""You are a senior 510(k) review report planner.

Using the NOTES and TEMPLATE:
1) Produce a structured outline that mirrors the template headings (adapt if needed).
2) Create a "Missing Information / Gaps" checklist (bullets).
3) Provide a table "Section → Evidence in Notes → Draft Coverage Plan".

Rules:
- Do NOT invent facts.
- Use Markdown.
- Keep it actionable for writing the full report.

Output language: {out_lang}.
"""
    agent_run_ui(
        agent_id="fda_510k_report_outline_agent",
        tab_key="rg_outline",
        default_prompt=outline_prompt.strip(),
        default_input_text=outline_input.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Report Generator",
    )
    report_plan = st.session_state.get("rg_outline_effective_output", "")

    st.markdown("---")

    # Step 3: Draft full report agent
    st.markdown("## Step 3 — Draft Full Report (Agent)")
    full_input = f"""=== REPORT PLAN / OUTLINE ===
{report_plan}

=== NOTES (source of truth) ===
{notes}

=== TEMPLATE (structure constraint) ===
{tpl}
"""
    report_prompt = f"""You are writing a comprehensive 510(k) review report in Markdown.

Hard requirements (must satisfy):
- Length target: 2000–3000 words (approx).
- Include at least 5 distinct Markdown tables. Each table must have a title line above it.
- Create exactly 20 entities with context in a Markdown table (Entity | Type | Context | Evidence pointer).
- Explicitly label unknowns as "Not provided" and list them in "Open Issues / Information Requests".
- Do NOT invent device facts beyond the NOTES. Use TEMPLATE only for structure.

Report guidance:
- Follow the TEMPLATE structure (adapt headings only if necessary).
- Include these suggested tables (you may add more):
  1) Device overview table
  2) Predicate/comparator differences table
  3) Standards/testing coverage matrix
  4) Risk controls mapping table
  5) Open issues / information requests table
- Add a short "Assumptions & Limitations" section.

Output language: {out_lang}.
"""
    agent_run_ui(
        agent_id="fda_510k_report_writer_agent",
        tab_key="rg_report",
        default_prompt=report_prompt.strip(),
        default_input_text=full_input.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Report Generator",
    )

    report_md = st.session_state.get("rg_report_effective_output", "")

    st.markdown("### WOW Quality Gate — Report")
    render_quality_gate_card(report_md, "510(k) Report Quality Gate", word_range=(2000, 3000), min_tables=5, entities_target=20)

    st.markdown("---")

    # Step 4: Generate skill.md agent (skill-creator principles)
    st.markdown("## Step 4 — Generate skill.md (Agent)")
    skill_input = f"""=== TEMPLATE ===
{tpl}

=== REPORT (example output) ===
{report_md}

=== NOTES (example input) ===
{notes}
"""
    skill_prompt = f"""You are generating a reusable SKILL.md that helps an agent create similar 510(k) review reports for other devices.

Use the "skill-creator" principles:
- Provide a strong description with when-to-trigger guidance (be pushy about dashboards/reports/510k/review templates).
- Provide clear input expectations: notes + optional template.
- Provide strict output requirements: 2000–3000 words, ≥5 tables, and 20 entities table.
- Include a quality checklist the model should self-verify (word range, table count, entities count, unknowns labeled).
- Include 2–3 realistic test prompts (examples) at the end.

Rules:
- Output MUST be Markdown content suitable to save as 'skill.md'.
- Do not include any code.
- Output language: {out_lang} (but the skill can mention it supports English/Traditional Chinese).

Generate the full skill.md content now.
"""
    agent_run_ui(
        agent_id="skill_creator_510k_report_agent",
        tab_key="rg_skill",
        default_prompt=skill_prompt.strip(),
        default_input_text=skill_input.strip(),
        allow_model_override=True,
        tab_label_for_history="510(k) Report Generator",
    )

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="510(k) Report Generator", height=260, limit=200)


# =============================================================================
# Note Keeper & Magics (preserve + add AI Entities + AI Chat)
# =============================================================================

def highlight_keywords(text: str, keywords: List[str], color: str) -> str:
    if not text or not keywords:
        return text
    out = text
    for kw in sorted(set([k for k in keywords if k.strip()]), key=len, reverse=True):
        safe_kw = kw.strip()
        if not safe_kw:
            continue
        span = f'<span style="color:{color};font-weight:800;">{safe_kw}</span>'
        out = out.replace(safe_kw, span)
    return out


def render_note_keeper_tab():
    st.title(t("Note Keeper & Magics"))

    st.markdown("### Step 1 — Paste Notes & Transform to Structured Markdown")
    raw_notes = st.text_area("Paste your notes (text or markdown)", height=220, key="notes_raw")

    col_n1, col_n2 = st.columns(2)
    with col_n1:
        note_model = st.selectbox("Model for Note → Markdown", ALL_MODELS,
                                 index=ALL_MODELS.index(st.session_state.settings["model"]), key="note_model")
    with col_n2:
        note_max_tokens = st.number_input("max_tokens", min_value=2000, max_value=120000, value=12000, step=1000, key="note_max_tokens")

    default_note_prompt = """你是一位協助醫療器材/510(k)/TFDA 審查員整理個人筆記的助手。

請將下列雜亂或半結構化的筆記，整理成：
1) 清晰的 Markdown 結構（標題、子標題、條列）
2) 保留所有技術與法規重點，不要憑空新增內容
3) 顯示出：關鍵技術要點、主要風險與疑問、待釐清/追問事項
"""
    note_struct_prompt = st.text_area("Prompt for Note → Markdown", value=default_note_prompt, height=160, key="note_struct_prompt")

    if st.button("Transform notes to structured Markdown", key="note_run_btn"):
        if not raw_notes.strip():
            st.warning("Please paste notes first.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = note_struct_prompt + "\n\n=== RAW NOTES ===\n" + raw_notes
            try:
                log_live({"ts": utc_ts(), "event_type": "run_start", "tab": "Note Keeper", "agent": "Note Structurer",
                          "model": note_model, "provider": get_provider(note_model), "status": "running",
                          "tokens_est": approx_tokens(user_prompt), "message": "Started note transform."})
                out, meta = call_llm(
                    model=note_model,
                    system_prompt="You organize reviewer's notes into clean markdown.",
                    user_prompt=user_prompt,
                    max_tokens=int(note_max_tokens),
                    temperature=0.15,
                    api_keys=api_keys,
                )
                st.session_state["note_md"] = out
                log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "Note Structurer",
                          "model": note_model, "provider": meta["provider"], "status": "done",
                          "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                          "message": "Completed note transform."})
            except Exception as e:
                st.error(f"Error: {e}")
                log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "Note Structurer",
                          "model": note_model, "provider": get_provider(note_model), "status": "error",
                          "tokens_est": approx_tokens(user_prompt), "message": f"Error: {e}"})

    note_md = st.session_state.get("note_md", raw_notes)
    st.markdown("#### Structured Note (editable)")
    note_view = st.radio("View mode for base note", [t("Markdown"), t("Plain text")], horizontal=True, key="note_view_mode")
    note_md_edited = st.text_area("Base note", value=note_md, height=260, key="note_md_edited")
    st.session_state["note_effective"] = note_md_edited
    base_note = st.session_state.get("note_effective", "")

    # Magic 1 — AI Formatting
    st.markdown("---")
    st.markdown("### Magic 1 — AI Formatting")
    fmt_model = st.selectbox("Model (Formatting)", ALL_MODELS, index=ALL_MODELS.index(st.session_state.settings["model"]), key="fmt_model")
    fmt_prompt = st.text_area("Prompt for AI Formatting",
                              value="請在不改變內容的前提下，統一標題層級與條列格式，讓此筆記更易讀（輸出 Markdown）。",
                              height=110, key="fmt_prompt")

    if st.button("Run AI Formatting", key="fmt_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = fmt_prompt + "\n\n=== NOTE ===\n" + base_note
            out, meta = call_llm(fmt_model, "You are a formatting-only assistant for markdown notes.", user_prompt, 12000, 0.1, api_keys)
            st.session_state["fmt_note"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Formatting",
                      "model": fmt_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Formatting completed."})

    fmt_note = st.session_state.get("fmt_note", "")
    if fmt_note:
        st.text_area("Formatted Note (Markdown)", value=fmt_note, height=220, key="fmt_note_edited")

    # Magic 2 — AI Keywords (manual highlight)
    st.markdown("---")
    st.markdown("### Magic 2 — AI Keywords (Manual highlight)")
    kw_input = st.text_input("Keywords (comma-separated)", key="kw_input", value="510(k), TFDA, QMS, biocompatibility")
    kw_color = st.color_picker("Color for keywords", "#ff7f50", key="kw_color")
    if st.button("Apply Keyword Highlighting", key="kw_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
            st.session_state["kw_note"] = highlight_keywords(base_note, keywords, kw_color)

    kw_note = st.session_state.get("kw_note", "")
    if kw_note:
        st.markdown("#### Note with Highlighted Keywords (Markdown rendering)")
        st.markdown(kw_note, unsafe_allow_html=True)

    # Magic 3 — AI Entities (NEW)
    st.markdown("---")
    st.markdown("### Magic 3 — AI Entities (20 entities with context)")
    ent_model = st.selectbox("Model (Entities)", ALL_MODELS, index=ALL_MODELS.index("gemini-2.5-flash") if "gemini-2.5-flash" in ALL_MODELS else 0, key="ent_model")
    ent_prompt = st.text_area(
        "Prompt for Entities",
        value="""From the following note, extract exactly 20 entities with context and output as ONE markdown table.

Table columns:
Entity | Type | Context | Evidence pointer

Rules:
- Exactly 20 rows (not counting header/divider).
- Do not invent facts. Evidence pointer should reference a phrase or section from the note.
""",
        height=150,
        key="ent_prompt",
    )
    if st.button("Run AI Entities", key="ent_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = ent_prompt + "\n\n=== NOTE ===\n" + base_note
            out, meta = call_llm(ent_model, "You extract entities from regulatory notes.", user_prompt, 12000, 0.2, api_keys)
            st.session_state["note_entities"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Entities",
                      "model": ent_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Entities extracted."})

    if st.session_state.get("note_entities"):
        st.text_area("Entities Table", value=st.session_state["note_entities"], height=220, key="note_entities_edited")
        with st.expander("WOW Entities Gate", expanded=False):
            render_quality_gate_card(st.session_state.get("note_entities", ""), "Entities Gate", word_range=None, min_tables=1, entities_target=20)

    # Magic 4 — AI Chat (NEW)
    st.markdown("---")
    st.markdown("### Magic 4 — AI Chat (Q&A over your note)")
    chat_model = st.selectbox("Model (Chat)", ALL_MODELS, index=ALL_MODELS.index(st.session_state.settings["model"]), key="chat_model")
    chat_prompt = st.text_area("Chat prompt", value="Ask me questions about the note, identify risks, and suggest next steps.", height=100, key="chat_prompt")
    chat_question = st.text_input("Your question", value="What are the top 5 risks and what evidence supports them?", key="chat_question")
    if st.button("Run AI Chat", key="chat_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = f"{chat_prompt}\n\nQuestion: {chat_question}\n\n=== NOTE ===\n{base_note}"
            out, meta = call_llm(chat_model, "You answer questions grounded in the provided note.", user_prompt, 12000, 0.2, api_keys)
            st.session_state["note_chat"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Chat",
                      "model": chat_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Chat answered."})
    if st.session_state.get("note_chat"):
        st.text_area("Chat Answer", value=st.session_state["note_chat"], height=220, key="note_chat_edited")

    # Magic 5 — AI Summary (kept)
    st.markdown("---")
    st.markdown("### Magic 5 — AI Summary")
    sum_model = st.selectbox("Model (Summary)", ALL_MODELS,
                            index=ALL_MODELS.index("gpt-4o-mini") if "gpt-4o-mini" in ALL_MODELS else 0, key="note_sum_model")
    sum_prompt = st.text_area("Prompt for Summary",
                              value="請將以下審查筆記摘要為 5–10 個重點 bullet，並附上一段 3–5 句的整體摘要（使用繁體中文）。",
                              height=130, key="note_sum_prompt")
    if st.button("Run AI Summary", key="note_sum_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = sum_prompt + "\n\n=== NOTE ===\n" + base_note
            out, meta = call_llm(sum_model, "You write executive-style regulatory summaries.", user_prompt, 12000, 0.2, api_keys)
            st.session_state["note_summary"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Summary",
                      "model": sum_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Summary created."})

    if st.session_state.get("note_summary"):
        st.text_area("Summary", value=st.session_state["note_summary"], height=200, key="note_summary_edited")

    # Magic 6 — AI Action Items (kept)
    st.markdown("---")
    st.markdown("### Magic 6 — AI Action Items")
    act_model = st.selectbox("Model (Action Items)", ALL_MODELS, index=ALL_MODELS.index(st.session_state.settings["model"]), key="note_act_model")
    act_prompt = st.text_area(
        "Prompt for Action Items",
        value="請從以下筆記中萃取需要後續行動的事項（補件、澄清、內部會議等），並以 Markdown 表格輸出：項目、負責人(可留空)、優先順序、說明。",
        height=130, key="note_act_prompt",
    )
    if st.button("Run AI Action Items", key="note_act_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = act_prompt + "\n\n=== NOTE ===\n" + base_note
            out, meta = call_llm(act_model, "You extract action items from regulatory review notes.", user_prompt, 12000, 0.2, api_keys)
            st.session_state["note_actions"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Action Items",
                      "model": act_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Action items created."})

    if st.session_state.get("note_actions"):
        st.text_area("Action Items", value=st.session_state["note_actions"], height=220, key="note_actions_edited")

    # Magic 7 — AI Glossary (kept)
    st.markdown("---")
    st.markdown("### Magic 7 — AI Glossary (術語表)")
    glo_model = st.selectbox("Model (Glossary)", ALL_MODELS,
                            index=ALL_MODELS.index("gemini-2.5-flash") if "gemini-2.5-flash" in ALL_MODELS else 0,
                            key="note_glo_model")
    glo_prompt = st.text_area(
        "Prompt for Glossary",
        value="請從以下筆記中找出重要專有名詞 (英文縮寫、標準、指引文件名稱、專業術語)，製作 Markdown 表格：Term, Full Name/Chinese, Explanation。",
        height=130, key="note_glo_prompt",
    )
    if st.button("Run AI Glossary", key="note_glo_run_btn"):
        if not base_note.strip():
            st.warning("No base note available.")
        else:
            api_keys = st.session_state.get("api_keys", {})
            user_prompt = glo_prompt + "\n\n=== NOTE ===\n" + base_note
            out, meta = call_llm(glo_model, "You build glossaries for regulatory/technical notes.", user_prompt, 12000, 0.2, api_keys)
            st.session_state["note_glossary"] = out
            log_live({"ts": utc_ts(), "event_type": "run_complete", "tab": "Note Keeper", "agent": "AI Glossary",
                      "model": glo_model, "provider": meta["provider"], "status": "done",
                      "tokens_est": meta["tokens_est_total"], "duration_ms": meta["duration_ms"],
                      "message": "Glossary created."})

    if st.session_state.get("note_glossary"):
        st.text_area("Glossary", value=st.session_state["note_glossary"], height=220, key="note_glossary_edited")

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="Note Keeper", height=260, limit=200)


# =============================================================================
# Agents Config Studio
# =============================================================================

def render_agents_config_tab():
    st.title(t("Agents Config"))

    agents_cfg = st.session_state.get("agents_cfg", {"agents": {}})
    agents_dict = agents_cfg.get("agents", {})

    st.subheader("1) Current Agents Overview")
    if not agents_dict:
        st.warning("No agents found in current agents.yaml.")
    else:
        df = pd.DataFrame([{
            "agent_id": aid,
            "name": acfg.get("name", ""),
            "model": acfg.get("model", ""),
            "category": acfg.get("category", ""),
            "max_tokens": acfg.get("max_tokens", ""),
        } for aid, acfg in agents_dict.items()])
        st.dataframe(df, use_container_width=True, height=260)

        # quick validation
        unknown_models = [row["model"] for _, row in df.iterrows() if row["model"] and (row["model"] not in ALL_MODELS)]
        missing_system = [aid for aid, acfg in agents_dict.items() if not (acfg.get("system_prompt") or "").strip()]
        with st.expander("Validation summary", expanded=False):
            if unknown_models:
                st.warning(f"Unknown models (not in ALL_MODELS): {sorted(set(unknown_models))}. They may still work if provider routing can infer.")
            else:
                st.success("All agent models are in ALL_MODELS.")
            if missing_system:
                st.warning(f"Agents missing system_prompt: {missing_system}")
            else:
                st.success("All agents have system_prompt.")

    st.markdown("---")
    st.subheader("2) Edit Full agents.yaml (raw text)")

    yaml_str_current = yaml.dump(st.session_state["agents_cfg"], allow_unicode=True, sort_keys=False)
    edited_yaml_text = st.text_area("agents.yaml (editable)", value=yaml_str_current, height=340, key="agents_yaml_text_editor")

    col_a1, col_a2, col_a3 = st.columns(3)
    with col_a1:
        if st.button("Apply edited YAML to session", key="apply_edited_yaml"):
            try:
                cfg = yaml.safe_load(edited_yaml_text)
                if not isinstance(cfg, dict) or "agents" not in cfg:
                    st.error("Parsed YAML does not contain top-level key 'agents'. No changes applied.")
                else:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Updated agents.yaml in current session.")
                    log_live({"ts": utc_ts(), "event_type": "info", "tab": "Agents Config", "agent": "YAML Editor",
                              "model": "", "provider": "", "status": "done", "tokens_est": 0,
                              "message": "Applied edited agents.yaml."})
            except Exception as e:
                st.error(f"Failed to parse edited YAML: {e}")

    with col_a2:
        uploaded_agents_tab = st.file_uploader("Upload agents.yaml file", type=["yaml", "yml"], key="agents_yaml_tab_uploader")
        if uploaded_agents_tab is not None:
            try:
                cfg = yaml.safe_load(uploaded_agents_tab.read())
                if "agents" in cfg:
                    st.session_state["agents_cfg"] = cfg
                    st.success("Uploaded agents.yaml applied to this session.")
                else:
                    st.warning("Uploaded file has no top-level 'agents' key. Ignoring.")
            except Exception as e:
                st.error(f"Failed to parse uploaded YAML: {e}")

    with col_a3:
        st.download_button("Download current agents.yaml", data=yaml_str_current.encode("utf-8"),
                           file_name="agents.yaml", mime="text/yaml", key="download_agents_yaml_current")

    st.markdown("---")
    st.subheader("3) Quick Test Runner")
    agent_ids = sorted(list(agents_dict.keys()))
    if agent_ids:
        test_agent = st.selectbox("Pick an agent", agent_ids, key="agent_test_pick")
        test_input = st.text_area("Test input", value="Hello. Summarize this in 5 bullets.", height=120, key="agent_test_input")
        agent_run_ui(
            agent_id=test_agent,
            tab_key="agent_test_runner",
            default_prompt="Run a quick sanity test. Keep output short.",
            default_input_text=test_input,
            allow_model_override=True,
            tab_label_for_history="Agents Config",
        )
    else:
        st.info("No agents to test (agents.yaml empty).")

    with st.expander(t("Live Log"), expanded=False):
        render_live_log_panel(filter_tab="Agents Config", height=260, limit=120)


# =============================================================================
# App bootstrap
# =============================================================================

st.set_page_config(page_title="Agentic Medical Device Reviewer", layout="wide")

if "settings" not in st.session_state:
    st.session_state["settings"] = {
        "theme": "Light",
        "language": "繁體中文",
        "painter_style": "Van Gogh",
        "model": "gpt-4o-mini",
        "max_tokens": 12000,
        "temperature": 0.2,
    }
if "history" not in st.session_state:
    st.session_state["history"] = []
if "live_log" not in st.session_state:
    st.session_state["live_log"] = []

# Load agents.yaml or default minimal set
if "agents_cfg" not in st.session_state:
    try:
        with open("agents.yaml", "r", encoding="utf-8") as f:
            st.session_state["agents_cfg"] = yaml.safe_load(f)
            if not isinstance(st.session_state["agents_cfg"], dict):
                raise ValueError("agents.yaml invalid")
    except Exception:
        st.session_state["agents_cfg"] = {
            "agents": {
                # existing / preserved
                "fda_510k_intel_agent": {
                    "name": "510(k) Intelligence Agent",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You are an FDA 510(k) analyst. Be structured and avoid hallucinations; label unknowns.",
                    "max_tokens": 12000,
                    "category": "FDA 510(k)",
                },
                "pdf_to_markdown_agent": {
                    "name": "PDF to Markdown Agent",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You convert PDF-extracted text into clean markdown. Do not invent content.",
                    "max_tokens": 12000,
                    "category": "Document Preprocessing",
                },
                "tw_screen_review_agent": {
                    "name": "TFDA 預審形式審查代理",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You are a TFDA premarket screen reviewer. Produce structured markdown. Do not invent facts.",
                    "max_tokens": 12000,
                    "category": "TFDA Premarket",
                },
                "tw_app_doc_helper": {
                    "name": "TFDA 申請書撰寫助手",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You improve TFDA application documents without adding new factual claims.",
                    "max_tokens": 12000,
                    "category": "TFDA Premarket",
                },

                # NEW: 510(k) Review Pipeline agents
                "fda_510k_submission_structurer": {
                    "name": "510(k) Submission Structurer",
                    "model": "gpt-4o-mini",
                    "system_prompt": "You restructure a 510(k) submission into clean, complete markdown without adding facts.",
                    "max_tokens": 14000,
                    "category": "FDA 510(k) Pipeline",
                },
                "fda_510k_checklist_cleaner": {
                    "name": "510(k) Checklist Cleaner",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You normalize checklists into clean markdown; do not add new requirements.",
                    "max_tokens": 12000,
                    "category": "FDA 510(k) Pipeline",
                },
                "fda_510k_review_memo_builder": {
                    "name": "510(k) Review Memo Builder",
                    "model": "gpt-4.1-mini",
                    "system_prompt": "You draft an internal 510(k) review memo grounded in the provided submission and checklist. Label unknowns explicitly.",
                    "max_tokens": 20000,
                    "category": "FDA 510(k) Pipeline",
                },

                # NEW: 510(k) Report Generator agents
                "fda_510k_report_outline_agent": {
                    "name": "510(k) Report Outline Agent",
                    "model": "gemini-2.5-flash",
                    "system_prompt": "You create a structured outline and evidence plan for a 510(k) review report. No hallucinations.",
                    "max_tokens": 14000,
                    "category": "510(k) Report Generator",
                },
                "fda_510k_report_writer_agent": {
                    "name": "510(k) Report Writer Agent",
                    "model": "gpt-4.1-mini",
                    "system_prompt": "You write a long-form 510(k) review report in markdown. Follow constraints strictly. Ground all claims in notes.",
                    "max_tokens": 32000,
                    "category": "510(k) Report Generator",
                },
                "skill_creator_510k_report_agent": {
                    "name": "Skill Creator — 510(k) Report Skill",
                    "model": "claude-3-5-sonnet-2024-10",
                    "system_prompt": "You are a skill-creator assistant. Create reusable skills with strong triggering descriptions and quality gates.",
                    "max_tokens": 16000,
                    "category": "Skill Creator",
                },
            }
        }

render_sidebar()
apply_style(st.session_state.settings["theme"], st.session_state.settings["painter_style"])

tab_labels = [
    t("Dashboard"),
    t("TW Premarket"),
    t("510k_tab"),
    t("PDF → Markdown"),
    t("Checklist & Report"),
    t("510k Report Generator"),
    t("Note Keeper & Magics"),
    t("Agents Config"),
]
tabs = st.tabs(tab_labels)

with tabs[0]:
    render_dashboard()
with tabs[1]:
    render_tw_premarket_tab()
with tabs[2]:
    render_510k_intel_tab()
with tabs[3]:
    render_pdf_to_md_tab()
with tabs[4]:
    render_510k_review_pipeline_tab()
with tabs[5]:
    render_510k_report_generator_tab()
with tabs[6]:
    render_note_keeper_tab()
with tabs[7]:
    render_agents_config_tab()
