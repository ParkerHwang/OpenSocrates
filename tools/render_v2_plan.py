"""Rebuild the standalone Korean 2.0 plan from its Markdown sources.

Run with ``uv run --no-project --with 'markdown-it-py==4.2.0'
python tools/render_v2_plan.py`` from the repository root.
"""

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from markdown_it import MarkdownIt

root = Path(__file__).resolve().parent.parent / "docs" / "v2.0"
parts = [
    ("vision", "01", "제품 비전과 요구사항", "VISION_2.0.ko.md"),
    ("system", "02", "시스템 구조와 데이터 흐름", "SYSTEM_2.0.ko.md"),
    ("roadmap", "03", "개발 로드맵과 인계", "ROADMAP_2.0.ko.md"),
    ("validation", "04", "검증과 평가", "VALIDATION_2.0.ko.md"),
]
md = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
flow_source = (root / "SYSTEM_2.0.ko.md").read_text(encoding="utf-8")
flow_match = re.search(r"```mermaid\n(.*?)\n```", flow_source, re.S)
if not flow_match:
    raise SystemExit("The Korean system plan has no Mermaid data-flow source.")
flow_svg = (root / "FLOW_2.0.ko.svg").read_text(encoding="utf-8")
flow_root = ET.fromstring(flow_svg)
flow_hash = hashlib.sha256(flow_match.group(1).encode("utf-8")).hexdigest()
if flow_root.attrib.get("data-mermaid-sha256") != flow_hash:
    raise SystemExit(
        "Review FLOW_2.0.ko.svg against the changed Mermaid source; "
        f"after review, set data-mermaid-sha256 to {flow_hash}."
    )
flow_figure = (
    '<figure class="flow-overview">'
    '<div class="diagram-viewport" role="region" tabindex="0" '
    'aria-label="데이터 흐름도, 필요하면 가로로 스크롤">'
    + flow_svg
    + "</div><figcaption>설계 요약입니다. 같은 이름은 같은 구성 요소를 반복 표시합니다. "
    "좁은 화면에서는 그림을 가로로 움직여 볼 수 있으며, 아래 원문과 이어지는 설명에서 "
    "상세 관계를 확인할 수 있습니다.</figcaption></figure>\n"
)
links = {
    "VISION_2.0.ko.md": "#vision",
    "SYSTEM_2.0.ko.md": "#system",
    "ROADMAP_2.0.ko.md": "#roadmap",
    "VALIDATION_2.0.ko.md": "#validation",
    "README.ko.md": "#top",
    "README.md": "#top",
    "../../AGENTS.md": "https://github.com/ParkerHwang/OpenSocrates/blob/49b14a58bc214bd53faaecaa09204645259a987a/AGENTS.md",
    "../../CONTRIBUTING.md": "https://github.com/ParkerHwang/OpenSocrates/blob/49b14a58bc214bd53faaecaa09204645259a987a/CONTRIBUTING.md",
    "RELEASE_BASELINE_1.5.3.md": "https://github.com/ParkerHwang/OpenSocrates/blob/49b14a58bc214bd53faaecaa09204645259a987a/docs/v2.0/RELEASE_BASELINE_1.5.3.md",
}
sections = []
for key, num, title, name in parts:
    raw = (root / name).read_text(encoding="utf-8")
    raw = re.sub(r"\s*\[English\]\((?:VISION|VALIDATION)_2\.0\.md\)\.?", "", raw)
    for source, target in links.items():
        raw = raw.replace("](" + source + ")", "](" + target + ")")
    tokens = md.parse(raw)
    if tokens and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        tokens = tokens[3:]
    body = md.renderer.render(tokens, md.options, {})
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace(
        "</table>", "</table></div>"
    )
    body = body.replace(
        '<pre><code class="language-mermaid">',
        '<details class="diagram-code"><summary>구조도 원문 보기</summary><pre><code class="language-mermaid">',
    )
    body = re.sub(
        r'(<details class="diagram-code"><summary>구조도 원문 보기</summary><pre><code class="language-mermaid">.*?</code></pre>)(\n?)',
        r"\1</details>\2",
        body,
        flags=re.S,
    )
    if key == "system":
        marker = '<details class="diagram-code"><summary>구조도 원문 보기</summary>'
        if marker not in body:
            raise SystemExit("The Korean system plan is missing its data-flow diagram block.")
        body = body.replace(marker, flow_figure + marker, 1)
    sections.append(
        f'<section id="{key}" class="chapter"><div class="chapter-label">{num} / DEVELOPMENT PLAN</div><h1>{html.escape(title)}</h1>{body}</section>'
    )
nav = "".join(
    f'<a href="#{key}"><span>{num}</span>{html.escape(title)}</a>'
    for key, num, title, name in parts
)
document = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OpenSocrates 2.0 개발계획서</title>
<style>
:root{color-scheme:light;--ink:#17242d;--muted:#60717a;--paper:#f4f5f2;--white:#fff;--border:#dce4e1;--green:#087968;--soft:#e4f2ed;--navy:#102831;--navy2:#173c43;--serif:Georgia,"Noto Serif KR",serif;--sans:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.75;font-size:16px}.layout{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:30px 24px;border-right:1px solid var(--border);background:#f9faf7;display:flex;flex-direction:column}.brand{font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:800;color:#174b47}.brand b{display:block;font-size:20px;letter-spacing:-.02em;color:#122c2e}.side-label{color:#82918f;font-size:11px;font-weight:800;letter-spacing:.16em;margin:52px 0 14px}.nav{display:grid;gap:4px}.nav a{color:#334a4c;text-decoration:none;font-size:14px;padding:10px 8px;border-radius:7px;display:flex;gap:12px}.nav a:hover,.nav a:focus{background:var(--soft);color:#075d53}.nav span{color:#62a092;font-size:12px;font-weight:700}.side-foot{margin-top:auto;font-size:12px;color:var(--muted)}.main{min-width:0}.hero{background:linear-gradient(125deg,var(--navy),var(--navy2));color:#f5f9f5;padding:72px max(44px,calc((100% - 930px)/2)) 58px}.eyebrow{color:#9addc9;letter-spacing:.18em;font-size:12px;font-weight:800}.hero h1{font-family:var(--serif);font-size:clamp(38px,5vw,58px);line-height:1.14;letter-spacing:-.035em;margin:16px 0}.hero p{max-width:720px;color:#d1e3df;font-size:17px;margin:0}.hero .meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}.pill{border:1px solid #658b83;border-radius:999px;padding:3px 12px;color:#c9e7dd;font-size:12px;font-weight:700}.content{max-width:1030px;padding:0 50px 80px;margin:auto}.intro{background:var(--white);border:1px solid var(--border);padding:25px 28px;border-radius:10px;margin:-22px 0 48px;position:relative;box-shadow:0 6px 22px rgba(15,54,45,.05)}.intro strong{color:#13675b}.intro p{margin:0}.flow{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:20px}.step{background:#edf5f0;border-radius:6px;color:#125f54;padding:6px 10px;font-weight:700;font-size:12px}.arrow{color:#a0b6ad}.chapter{scroll-margin-top:32px;padding:0 0 55px;margin-bottom:55px;border-bottom:1px solid var(--border)}.chapter-label{font-size:11px;letter-spacing:.18em;font-weight:800;color:var(--green)}.chapter h1{font-family:var(--serif);font-size:34px;letter-spacing:-.03em;line-height:1.2;margin:12px 0 26px}.chapter h2{font-size:23px;line-height:1.35;letter-spacing:-.025em;margin:48px 0 15px}.chapter h3{font-size:18px;line-height:1.4;margin:30px 0 10px}.chapter p{margin:12px 0}.chapter a{color:#006c60;text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}.chapter strong{color:#122c2a}.chapter li{margin:5px 0}.chapter ul,.chapter ol{padding-left:24px}.chapter blockquote{margin:24px 0;border-left:3px solid #70b2a0;background:#edf7f2;padding:12px 18px}.chapter code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#edf2ee;border-radius:4px;padding:1px 4px;font-size:.88em;overflow-wrap:anywhere}.chapter pre{background:#152c30;color:#d9eee6;padding:16px;border-radius:8px;overflow:auto}.chapter pre code{background:transparent;color:inherit;padding:0}.table-wrap{max-width:100%;overflow-x:auto;border:1px solid var(--border);border-radius:8px;margin:20px 0;background:#fff}table{border-collapse:collapse;width:100%;min-width:550px;font-size:14px;line-height:1.55}th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid #e3ebe6}th{background:#eaf3ee;color:#254e45;font-weight:750}tr:last-child td{border-bottom:0}details.diagram-code{border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin:20px 0}summary{cursor:pointer;color:#0b6a5c;font-weight:700}.footer{font-size:13px;color:var(--muted);padding-bottom:30px}.toplink{font-size:13px;font-weight:700;color:var(--green)}@media(max-width:820px){.layout{display:block}.sidebar{height:auto;position:static;border-right:0;border-bottom:1px solid var(--border);padding:18px 22px}.brand b{font-size:17px}.side-label,.side-foot{display:none}.nav{display:flex;overflow-x:auto;margin-top:12px}.nav a{white-space:nowrap;padding:8px}.hero{padding:48px 25px 50px}.hero p{font-size:16px}.content{padding:0 22px 50px}.intro{padding:20px}.chapter h1{font-size:29px}.chapter h2{font-size:21px}}@media print{.sidebar{display:none}.layout{display:block}.hero{padding:25px 0;color:#111;background:white}.hero p,.eyebrow{color:#333}.pill{color:#333;border-color:#aaa}.intro{margin:15px 0}.content{padding:0;max-width:none}.chapter{break-before:page}.table-wrap{overflow:visible}table{min-width:0}a{color:#000!important}details.diagram-code{display:none}}
</style></head><body><div id="top" class="layout"><aside class="sidebar"><div class="brand"><b>OpenSocrates</b>Development · 2.0</div><div class="side-label">CONTENTS</div><nav class="nav" aria-label="문서 목차">__NAV__</nav><div class="side-foot">개발 계획 문서<br>2026.11.03 · 한국어</div></aside><main class="main"><header class="hero"><div class="eyebrow">PRODUCT · SYSTEM · DELIVERY</div><h1>OpenSocrates 2.0<br>개발계획서</h1><p>사용자를 중심으로 함께 일하고, 실제 업무 경험에서 발전하는 에이전트 팀을 위한 계획입니다.</p><div class="meta"><span class="pill">개발 계획</span><span class="pill">macOS + Windows</span><span class="pill">ChatGPT + Claude 데스크톱</span></div></header><div class="content"><div class="intro"><p><strong>이 문서의 상태</strong> · 대화에서 정한 제품 방향과 구현·검증 계획입니다. 아직 제품 구현, 효과 또는 각 환경의 연결 성공을 뜻하지 않습니다.</p><div class="flow" aria-label="주요 작동 흐름"><span class="step">사용자의 요청</span><span class="arrow">→</span><span class="step">OpenSocrates 준비·조율</span><span class="arrow">→</span><span class="step">새 작업 세션</span><span class="arrow">→</span><span class="step">결과와 경험</span><span class="arrow">→</span><span class="step">개인별 학습</span></div></div>__SECTIONS__<div class="footer">이 문서는 계획 문서의 한국어 내용을 하나로 모은 스냅샷입니다. 최신 개발과 변경 이력은 저장소 원본 문서를 확인하세요. <a class="toplink" href="#top">맨 위로 ↑</a></div></div></main></div></body></html>"""
diagram_style = """
.flow-overview{margin:26px 0;padding:12px;background:#fff;border:1px solid var(--border);border-radius:12px}
.diagram-viewport{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain}
.diagram-viewport:focus-visible{outline:3px solid #087968;outline-offset:3px}
.diagram-viewport svg{display:block;width:100%;min-width:1080px;height:auto}
.flow-overview figcaption{font-size:13px;color:#526b64;padding:8px 6px 2px}
@media print{.diagram-viewport{overflow:visible}.diagram-viewport svg{min-width:0}.flow-overview{break-inside:avoid}}
"""
document = document.replace("</style>", diagram_style + "</style>", 1)
(root / "PLAN_2.0.ko.html").write_text(
    document.replace("__NAV__", nav).replace("__SECTIONS__", "\n".join(sections)), encoding="utf-8"
)
print("Created docs/v2.0/PLAN_2.0.ko.html from four Korean plan documents")
