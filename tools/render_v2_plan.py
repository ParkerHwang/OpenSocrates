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


def section_id(chapter: str, label: str) -> str:
    stable_label = re.sub(r"^\d+\.\s+", "", label) or label
    digest = hashlib.sha256(stable_label.encode("utf-8")).hexdigest()[:16]
    return f"{chapter}-section-{digest}"


def navigation_link(anchor: str, label: str, context: str, occurrence: int) -> str:
    accessible_label = f"{context} · {label}"
    if occurrence > 1:
        accessible_label += f" (같은 제목 {occurrence}번째)"
    return (
        f'<a href="#{anchor}" aria-label="{html.escape(accessible_label, quote=True)}">'
        f"{html.escape(label)}</a>"
    )


specific_sections = {
    "시스템 설계 §12–14": section_id("system", "12. 공통 가이드 생성 지침의 작업 초안"),
    "두 업무 합성 가이드 사례": section_id(
        "system", "두 업무에서 만들어진 후보와 현재 요청: 합성 사례"
    ),
}
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
navigation = []
observed_counts = {}
replaced_specific_links = set()
for key, num, title, name in parts:
    raw = (root / name).read_text(encoding="utf-8")
    raw = re.sub(r"\s*\[English\]\((?:VISION|VALIDATION)_2\.0\.md\)\.?", "", raw)
    for source, target in links.items():
        raw = raw.replace("](" + source + ")", "](" + target + ")")
    tokens = md.parse(raw)
    if tokens and tokens[0].type == "heading_open" and tokens[0].tag == "h1":
        tokens = tokens[3:]
    headings = []
    seen_headings = {}
    for index, token in enumerate(tokens):
        if token.type != "heading_open" or token.tag not in {"h2", "h3"}:
            continue
        inline = tokens[index + 1]
        label = "".join(
            child.content
            if child.type in {"text", "code_inline", "image"}
            else " "
            if child.type in {"softbreak", "hardbreak"}
            else ""
            for child in inline.children or []
        ).strip()
        if not label:
            raise SystemExit(f"An empty section heading was found in {name}.")
        stable_label = re.sub(r"^\d+\.\s+", "", label) or label
        base_id = section_id(key, label)
        digest = base_id.rsplit("-", 1)[-1]
        previous_label, previous_count = seen_headings.get(digest, (stable_label, 0))
        if previous_label != stable_label:
            raise SystemExit(f"Section heading ID collision in {name}.")
        count = previous_count + 1
        seen_headings[digest] = (stable_label, count)
        anchor = base_id + (f"-{count}" if count > 1 else "")
        token.attrSet("id", anchor)
        observed_counts[base_id] = count
        if token.tag == "h2":
            headings.append((anchor, label, count, []))
        elif headings:
            headings[-1][3].append((anchor, label, count))
        else:
            raise SystemExit(f"A subsection appeared before a section in {name}.")
    body = md.renderer.render(tokens, md.options, {})
    for link_label, target in specific_sections.items():
        source_link = f'<a href="#system">{html.escape(link_label)}</a>'
        if source_link in body:
            body = body.replace(source_link, f'<a href="#{target}">{html.escape(link_label)}</a>')
            replaced_specific_links.add(link_label)
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
    entries = ""
    for anchor, label, count, children in headings:
        nested = "".join(
            f"<li>{navigation_link(child_anchor, child_label, label, child_count)}</li>"
            for child_anchor, child_label, child_count in children
        )
        entries += f"<li>{navigation_link(anchor, label, title, count)}"
        entries += f"<ul>{nested}</ul>" if nested else ""
        entries += "</li>"
    navigation.append(
        f'<div class="nav-group"><a href="#{key}"><span>{num}</span>{html.escape(title)}</a>'
        f'<details><summary aria-label="{html.escape(title, quote=True)} 세부 목차">세부 목차</summary>'
        f"<ul>{entries}</ul></details></div>"
    )
if any(observed_counts.get(target) != 1 for target in specific_sections.values()):
    raise SystemExit("A specific system-section link has a missing or ambiguous target heading.")
if replaced_specific_links != set(specific_sections):
    raise SystemExit("A specific system-section link no longer exists in the source documents.")
nav = "".join(navigation)
document = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OpenSocrates 2.0 개발계획서</title>
<style>
:root{color-scheme:light;--ink:#17242d;--muted:#60717a;--paper:#f4f5f2;--white:#fff;--border:#dce4e1;--green:#087968;--soft:#e4f2ed;--navy:#102831;--navy2:#173c43;--serif:Georgia,"Noto Serif KR",serif;--sans:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);line-height:1.75;font-size:16px}.layout{display:grid;grid-template-columns:258px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;padding:30px 24px;border-right:1px solid var(--border);background:#f9faf7;display:flex;flex-direction:column}.brand{font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:800;color:#174b47}.brand b{display:block;font-size:20px;letter-spacing:-.02em;color:#122c2e}.side-label{color:#82918f;font-size:11px;font-weight:800;letter-spacing:.16em;margin:52px 0 14px}.nav{display:grid;gap:4px}.nav a{color:#334a4c;text-decoration:none;font-size:14px;padding:10px 8px;border-radius:7px;display:flex;gap:12px}.nav a:hover,.nav a:focus{background:var(--soft);color:#075d53}.nav span{color:#62a092;font-size:12px;font-weight:700}.side-foot{margin-top:auto;font-size:12px;color:var(--muted)}.main{min-width:0}.hero{background:linear-gradient(125deg,var(--navy),var(--navy2));color:#f5f9f5;padding:72px max(44px,calc((100% - 930px)/2)) 58px}.eyebrow{color:#9addc9;letter-spacing:.18em;font-size:12px;font-weight:800}.hero h1{font-family:var(--serif);font-size:clamp(38px,5vw,58px);line-height:1.14;letter-spacing:-.035em;margin:16px 0}.hero p{max-width:720px;color:#d1e3df;font-size:17px;margin:0}.hero .meta{display:flex;gap:12px;flex-wrap:wrap;margin-top:30px}.pill{border:1px solid #658b83;border-radius:999px;padding:3px 12px;color:#c9e7dd;font-size:12px;font-weight:700}.content{max-width:1030px;padding:0 50px 80px;margin:auto}.intro{background:var(--white);border:1px solid var(--border);padding:25px 28px;border-radius:10px;margin:-22px 0 48px;position:relative;box-shadow:0 6px 22px rgba(15,54,45,.05)}.intro strong{color:#13675b}.intro p{margin:0}.flow{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:20px}.step{background:#edf5f0;border-radius:6px;color:#125f54;padding:6px 10px;font-weight:700;font-size:12px}.arrow{color:#a0b6ad}.chapter{scroll-margin-top:32px;padding:0 0 55px;margin-bottom:55px;border-bottom:1px solid var(--border)}.chapter-label{font-size:11px;letter-spacing:.18em;font-weight:800;color:var(--green)}.chapter h1{font-family:var(--serif);font-size:34px;letter-spacing:-.03em;line-height:1.2;margin:12px 0 26px}.chapter h2{font-size:23px;line-height:1.35;letter-spacing:-.025em;margin:48px 0 15px}.chapter h3{font-size:18px;line-height:1.4;margin:30px 0 10px}.chapter p{margin:12px 0}.chapter a{color:#006c60;text-decoration-thickness:1px;text-underline-offset:3px;overflow-wrap:anywhere}.chapter strong{color:#122c2a}.chapter li{margin:5px 0}.chapter ul,.chapter ol{padding-left:24px}.chapter blockquote{margin:24px 0;border-left:3px solid #70b2a0;background:#edf7f2;padding:12px 18px}.chapter code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;background:#edf2ee;border-radius:4px;padding:1px 4px;font-size:.88em;overflow-wrap:anywhere}.chapter pre{background:#152c30;color:#d9eee6;padding:16px;border-radius:8px;overflow:auto}.chapter pre code{background:transparent;color:inherit;padding:0}.table-wrap{max-width:100%;overflow-x:auto;border:1px solid var(--border);border-radius:8px;margin:20px 0;background:#fff}table{border-collapse:collapse;width:100%;min-width:550px;font-size:14px;line-height:1.55}th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid #e3ebe6}th{background:#eaf3ee;color:#254e45;font-weight:750}tr:last-child td{border-bottom:0}details.diagram-code{border:1px solid var(--border);border-radius:8px;padding:12px 16px;margin:20px 0}summary{cursor:pointer;color:#0b6a5c;font-weight:700}.footer{font-size:13px;color:var(--muted);padding-bottom:30px}.toplink{font-size:13px;font-weight:700;color:var(--green)}@media(max-width:820px){.layout{display:block}.sidebar{height:auto;position:static;border-right:0;border-bottom:1px solid var(--border);padding:18px 22px}.brand b{font-size:17px}.side-label,.side-foot{display:none}.nav{display:flex;overflow-x:auto;margin-top:12px}.nav a{white-space:nowrap;padding:8px}.hero{padding:48px 25px 50px}.hero p{font-size:16px}.content{padding:0 22px 50px}.intro{padding:20px}.chapter h1{font-size:29px}.chapter h2{font-size:21px}}@media print{.sidebar{display:none}.layout{display:block}.hero{padding:25px 0;color:#111;background:white}.hero p,.eyebrow{color:#333}.pill{color:#333;border-color:#aaa}.intro{margin:15px 0}.content{padding:0;max-width:none}.chapter{break-before:page}.table-wrap{overflow:visible}table{min-width:0}a{color:#000!important}details.diagram-code{display:none}}
</style></head><body><div id="top" class="layout"><aside class="sidebar"><div class="brand"><b>OpenSocrates</b>Development · 2.0</div><div class="side-label">CONTENTS</div><nav class="nav" aria-label="문서 목차">__NAV__</nav><div class="side-foot">개발 계획 문서<br>2026.11.03 · 한국어</div></aside><main class="main"><header class="hero"><div class="eyebrow">PRODUCT · SYSTEM · DELIVERY</div><h1>OpenSocrates 2.0<br>개발계획서</h1><p>사용자를 중심으로 함께 일하고, 실제 업무 경험에서 발전하는 에이전트 팀을 위한 계획입니다.</p><div class="meta"><span class="pill">개발 계획</span><span class="pill">macOS + Windows</span><span class="pill">ChatGPT + Claude 데스크톱</span></div></header><div class="content"><div class="intro"><p><strong>이 문서의 상태</strong> · 대화에서 정한 제품 방향과 구현·검증 계획입니다. 아직 제품 구현, 효과 또는 각 환경의 연결 성공을 뜻하지 않습니다.</p><div class="flow" role="group" aria-label="업무 흐름"><span class="step">사용자의 요청</span> <span class="arrow" aria-hidden="true">→</span> <span class="step">상담과 작업 준비</span> <span class="arrow" aria-hidden="true">→</span> <span class="step">별도 작업 대화</span> <span class="arrow" aria-hidden="true">→</span> <span class="step">결과 전달</span></div></div>__SECTIONS__<div class="footer">이 문서는 계획 문서의 한국어 내용을 하나로 모은 스냅샷입니다. 최신 개발과 변경 이력은 저장소 원본 문서를 확인하세요. <a class="toplink" href="#top">맨 위로 ↑</a></div></div></main></div></body></html>"""
diagram_style = """
.sidebar{overflow-y:auto}
.intro p+p{margin-top:10px}
.intro .flow+p{margin-top:14px}
.skip-link{position:absolute;left:16px;top:-80px;z-index:10;background:#fff;color:#075d53;padding:8px 12px}
.skip-link:focus{top:12px;outline:3px solid #087968}
.nav{display:block}
.nav-group{margin-bottom:6px}
.nav-group details{padding-left:28px}
.nav-group summary{font-size:12px;line-height:1.5;padding:4px 8px;color:#526b64}
.nav-group ul{list-style:none;margin:2px 0 8px;padding:0}
.nav-group ul ul{padding-left:12px;border-left:1px solid var(--border)}
.nav-group li a{display:block;font-size:12px;line-height:1.4;padding:5px 8px;overflow-wrap:anywhere}
.nav-group a:focus-visible,.nav-group summary:focus-visible{outline:3px solid #087968;outline-offset:2px}
.chapter h2[id],.chapter h3[id]{scroll-margin-top:24px}
.flow-overview{margin:26px 0;padding:12px;background:#fff;border:1px solid var(--border);border-radius:12px}
.diagram-viewport{max-width:100%;overflow-x:auto;overscroll-behavior-x:contain}
.diagram-viewport:focus-visible{outline:3px solid #087968;outline-offset:3px}
.diagram-viewport svg{display:block;width:100%;min-width:1080px;height:auto}
.flow-overview figcaption{font-size:13px;color:#526b64;padding:8px 6px 2px}
@media(max-width:820px){.nav{display:block;overflow:visible}.nav-group>a{white-space:normal}.nav-group li a{white-space:normal}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{.diagram-viewport{overflow:visible}.diagram-viewport svg{min-width:0}.flow-overview{break-inside:avoid}}
"""
document = document.replace("</style>", diagram_style + "</style>", 1)
document = document.replace(
    '<body><div id="top"',
    '<body><a class="skip-link" href="#content">본문 바로가기</a><div id="top"',
    1,
).replace('<main class="main">', '<main id="content" class="main" tabindex="-1">', 1)
document = (
    document.replace(
        "개발 계획 문서<br>2026.11.03 · 한국어", "원본 네 문서에서 생성한<br>한국어 스냅샷", 1
    )
    .replace(
        '<span class="pill">macOS + Windows</span>',
        '<span class="pill">목표 환경 · macOS + Windows</span>',
        1,
    )
    .replace(
        '<span class="pill">ChatGPT + Claude 데스크톱</span>',
        '<span class="pill">목표 앱 · ChatGPT + Claude 데스크톱</span>',
        1,
    )
)
intro_flow = '<div class="flow" role="group" aria-label="업무 흐름">'
if document.count(intro_flow) != 1:
    raise SystemExit("The opening work-flow marker is missing or ambiguous.")
document = document.replace(
    intro_flow,
    "<p><strong>무엇을 만들까</strong> · 기본 48개 가이드에서 시작해 사용자에게 맞는 "
    "생각의 방향을 발전시키고, 대화 사이의 협업과 맥락을 연결하는 프로그램을 계획합니다.</p>"
    "<p><strong>어떻게 일할까</strong> · 의뢰 대화에서 목적과 결과물의 형식을 상담하고, "
    "실제 제작은 별도 작업 대화에서 합니다. 필요하면 일을 더 나누어 맡기며, 대화 간 의뢰와 "
    "결과는 OpenSocrates를 거칩니다. 중요한 결정은 사용자와 함께합니다.</p>"
    "<p><strong>무엇을 확인해야 할까</strong> · 앱·운영체제별 연결, 진행 중 반영과 "
    "학습, 실제 업무의 품질과 사용자 부담을 각각 검증해야 합니다.</p>" + intro_flow,
    1,
)
intro_end = "</div></div>__SECTIONS__"
if document.count(intro_end) != 1:
    raise SystemExit("The opening section marker is missing or ambiguous.")
document = document.replace(
    intro_end,
    "</div><p><strong>일하면서 발전</strong> · 상담과 작업에 맞는 가이드를 준비합니다. "
    "적합한 개인 가이드를 우선하고, 필요하면 기본 가이드와 조합합니다. 개인 가이드가 "
    "맞지 않으면 기본 48개 중 적합한 것을 살핍니다. 작업 중 사용자의 수정은 현재 업무에 "
    "반영을 시도합니다. 작업 중이나 이후의 경험에 따라 개인 가이드를 만들거나 조정·유지하고, "
    "맞는 경우 진행 중 또는 다음 관련 업무에 활용할 수 있습니다. 경험마다 가이드가 바뀌는 "
    "것은 아니며, 사용자가 멈춘 학습과 가이드 사용의 범위를 따릅니다.</p></div>__SECTIONS__",
    1,
)
(root / "PLAN_2.0.ko.html").write_text(
    document.replace("__NAV__", nav).replace("__SECTIONS__", "\n".join(sections)), encoding="utf-8"
)
print("Created docs/v2.0/PLAN_2.0.ko.html from four Korean plan documents")
