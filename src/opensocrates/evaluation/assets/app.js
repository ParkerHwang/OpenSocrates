"use strict";

// Only a per-launch capability is kept in session storage; answers stay in memory.
let language = "ko";
let token = sessionStorage.getItem("office-lab-token") || "";
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has("token")) {
  token = fragment.get("token") || "";
  sessionStorage.setItem("office-lab-token", token);
  history.replaceState(null, "", location.pathname + location.search);
}
const reviewMode = location.pathname === "/review";
const groupId = new URLSearchParams(location.search).get("group") || "";
const app = document.getElementById("app");
const notice = document.getElementById("notice");
let snapshot = null;
let selectedRun = "";
let prepared = null;
let packet = null;
let reveal = null;
let pollBusy = false;

const tr = (ko, en) => language === "ko" ? ko : en;
const statuses = {
  planned: ["준비 전", "Planned"], prepared: ["준비됨", "Prepared"],
  running: ["실행 기록 중", "Running"], completed: ["완료", "Completed"],
  failed: ["실패", "Failed"], aborted: ["중단", "Aborted"],
  blocked: ["진행 불가", "Blocked"], timed_out: ["시간 초과", "Timed out"],
};
const statusLabel = value => statuses[value] ? tr(...statuses[value]) : String(value || "—");

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function add(parent, ...children) {
  for (const child of children) if (child) parent.append(child);
  return parent;
}

function panel(title, parent = app) {
  const section = element("section");
  if (title) section.append(element("h2", title));
  parent.append(section);
  return section;
}

function message(text, error = false) {
  notice.textContent = text;
  notice.className = error ? "error" : "callout";
}

function errorText(code) {
  const descriptions = {
    group_incomplete: ["이 비교의 첫 시도 세 개가 아직 모두 완료되지 않았습니다.", "All three original attempts must finish before review."],
    judgment_required: ["먼저 첫 선택과 느낌을 저장하세요.", "Save your first judgment before revealing conditions."],
    model_mismatch: ["지정 모델과 실제 모델을 다시 확인하세요.", "The observed model must match the requested model."],
    budget_exhausted: ["이번 실험의 실행 한도를 모두 사용했습니다.", "This study has no attempt budget remaining."],
    request_rejected: ["연결이 만료되었습니다. 실행기가 연 원래 창에서 다시 접속하세요.", "Connection expired. Reopen the original launcher window."],
    preview_expired: ["미리보기가 만료되었거나 파일이 바뀌었습니다. 다시 미리보기를 여세요.", "Preview expired or changed. Preview the current file again."],
    preview_changed: ["미리보기 후 파일이 바뀌었습니다. 다시 미리보기를 여세요.", "The file changed after preview. Preview it again."],
    preview_required: ["현재 파일의 미리보기를 다시 열어 승인하세요.", "Preview and approve the current file again."],
    preflight_blocked: ["실행 전 확인에서 막힌 항목을 해결하세요. 확인 내용을 다시 저장하면 항목을 볼 수 있습니다.", "Resolve preflight blockers. Save preflight again to see them."],
    criteria_not_frozen: ["새 과제를 열기 전에 아래에서 확인 실험의 기준을 고정하세요.", "Freeze confirmation criteria below before exposing fresh cases."],
    run_already_running: ["이미 기록 중인 실행을 먼저 완료하거나 종료 상태로 기록하세요.", "Finish or terminate the current running attempt first."],
    invalid_plan: ["환경과 실행 한도를 확인하세요. 한도는 계획된 시도를 포함해야 합니다.", "Check selected environments and attempt cap; the cap must cover planned attempts."],
    invalid_host_version: ["앱 버전에는 영문자·숫자·점·하이픈 등 버전 표기만 입력하세요.", "Enter only a version label using ASCII letters, numbers and version punctuation."],
    criteria_locked: ["이미 고정한 기준입니다. 새 답변에 맞춰 덮어쓸 수 없습니다.", "Criteria are already frozen and cannot be overwritten."],
    approval_required: ["가상 업무 내용만 보관하도록 먼저 승인하세요.", "Approve retention of synthetic-task content first."],
  };
  const item = descriptions[code];
  return item ? tr(...item) : tr("진행할 수 없습니다. 상태와 입력을 확인하세요. 코드: ", "Unable to continue. Check the state and fields. Code: ") + String(code || "unavailable");
}

async function api(action, data = {}) {
  const response = await fetch("/api", {
    method: "POST", credentials: "omit", cache: "no-store",
    headers: {"Content-Type": "application/json", "Authorization": `Bearer ${token}`},
    body: JSON.stringify({action, data}),
  });
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(errorText(result.error));
  return result.result;
}

function button(text, action, primary = false) {
  const node = element("button", text, primary ? "primary" : "");
  node.type = "button";
  node.addEventListener("click", async () => {
    node.disabled = true;
    try { await action(); } catch (error) { message(error.message || tr("연결 오류", "Connection error"), true); }
    finally { node.disabled = false; }
  });
  return node;
}

function field(parent, text, kind = "text", value = "") {
  const label = element("label", text);
  const input = element(kind === "textarea" ? "textarea" : "input");
  if (kind !== "textarea") input.type = kind;
  input.value = value;
  label.append(input);
  parent.append(label);
  return input;
}

function choice(parent, text, options, current = "") {
  const label = element("label", text);
  const select = element("select");
  for (const [value, caption] of options) {
    const option = element("option", caption);
    option.value = value;
    select.append(option);
  }
  if (current) select.value = current;
  label.append(select);
  parent.append(label);
  return select;
}

function check(parent, text, checked = false) {
  const label = element("label", undefined, "check");
  const input = element("input");
  input.type = "checkbox";
  input.checked = checked;
  add(label, input, element("span", text));
  parent.append(label);
  return input;
}

function details(parent, title, text) {
  const node = element("details");
  add(node, element("summary", title), element("pre", text, "answer scroll prompt"));
  parent.append(node);
  return node;
}

function copyButton(text, value) {
  return button(text, async () => {
    await navigator.clipboard.writeText(value);
    message(tr("복사했습니다.", "Copied."));
  });
}

function optionPairs(values) { return values.map(([value, ko, en]) => [value, tr(ko, en)]); }

function inlineText(parent, text) {
  // Tiny explicit formatting subset; no HTML, URL evaluation or image fetching.
  for (const part of text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/g)) {
    if (part.startsWith("**") && part.endsWith("**")) parent.append(element("strong", part.slice(2, -2)));
    else if (part.startsWith("`") && part.endsWith("`")) parent.append(element("code", part.slice(1, -1)));
    else parent.append(document.createTextNode(part));
  }
  return parent;
}

function tableCells(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(cell => cell.trim());
}

function markdown(text) {
  const body = element("div", undefined, "markdown");
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) { index++; continue; }
    if (/^\s*```/.test(line)) {
      const code = []; index++;
      while (index < lines.length && !/^\s*```/.test(lines[index])) code.push(lines[index++]);
      if (index < lines.length) index++;
      body.append(add(element("pre"), element("code", code.join("\n")))); continue;
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      body.append(inlineText(element(`h${Math.min(heading[1].length + 1, 6)}`), heading[2])); index++; continue;
    }
    if (line.includes("|") && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1]) && tableCells(lines[index + 1]).every(cell => /^:?-{3,}:?$/.test(cell))) {
      const table = element("table"); const head = element("tr");
      for (const cell of tableCells(line)) head.append(inlineText(element("th"), cell));
      table.append(add(element("thead"), head)); const rows = element("tbody"); index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        const row = element("tr"); for (const cell of tableCells(lines[index++])) row.append(inlineText(element("td"), cell)); rows.append(row);
      }
      table.append(rows); body.append(add(element("div", undefined, "table-wrap"), table)); continue;
    }
    const bullet = /^([-*+]\s+|\d+[.)]\s+)/.exec(line);
    if (bullet) {
      const ordered = /^\d/.test(line); const list = element(ordered ? "ol" : "ul");
      if (ordered) list.start = Number.parseInt(line, 10);
      while (index < lines.length) {
        const match = /^([-*+]\s+|\d+[.)]\s+)(.*)$/.exec(lines[index]);
        if (!match || /^\d/.test(lines[index]) !== ordered) break;
        list.append(inlineText(element("li"), match[2])); index++;
      }
      body.append(list); continue;
    }
    if (/^> ?/.test(line)) {
      const quote = [];
      while (index < lines.length && /^> ?/.test(lines[index])) quote.push(lines[index++].replace(/^> ?/, ""));
      body.append(inlineText(element("blockquote"), quote.join("\n"))); continue;
    }
    const paragraph = [line]; index++;
    while (index < lines.length && lines[index].trim() && !/^(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\s*```)/.test(lines[index])) paragraph.push(lines[index++]);
    body.append(inlineText(element("p"), paragraph.join("\n")));
  }
  return body;
}

function blockerLabel(code) {
  const labels = {
    model_mismatch: ["모델 확인 필요", "Model mismatch"], effort_mismatch: ["추론 수준 확인 필요", "Effort mismatch"],
    known_contamination: ["다른 지침이 섞여 있음", "Known contamination"], isolation_unknown: ["격리 미확인 · 탐색용 선택 필요", "Isolation unknown; exploratory opt-in needed"],
    opensocrates_state_mismatch: ["A/B는 비활성화 · C는 활성화 필요", "A/B must be absent; C enabled"],
    mapping_confirmation_required: ["Antigravity 모델 대응 확인 필요", "Confirm Antigravity model mapping"], pack_approval_required: ["공통 과제·B 지시 승인 필요", "Approve the case pack and fixed B"],
    content_unavailable: ["필요한 콘텐츠 설치 자료 없음", "Required content payload unavailable"], host_version_unknown: ["앱 버전 확인 필요", "App version unknown"],
    controller_os_mismatch: ["선택한 OS와 현재 기기가 다름", "Assigned OS differs from this machine"], controller_environment_changed: ["실험 시작 후 기기 환경이 달라짐", "Controller environment changed"],
    criteria_not_frozen: ["확인 실험 기준 고정 필요", "Freeze confirmation criteria"], group_host_version_mismatch: ["같은 비교의 앱 버전이 다름", "App version differs within comparison"],
    preflight_required: ["실행 전 확인 필요", "Preflight required"],
  };
  return labels[code] ? tr(...labels[code]) : code;
}

function renderHeader() {
  document.documentElement.lang = language;
  document.getElementById("title").textContent = reviewMode
    ? tr("답변을 먼저 비교하세요", "Compare the whole answers first")
    : tr("사무업무 비교 실험실", "Office work evaluation lab");
  document.getElementById("language").textContent = language === "ko" ? "English" : "한국어";
  document.getElementById("footer").textContent = tr(
    "실제 앱 실행과 최종 선택은 직접 합니다. 이 도구는 모델을 호출하지 않습니다.",
    "You run the real apps and make the judgment. This lab never calls models."
  );
}

async function refresh() {
  snapshot = await api("snapshot");
  renderOperator();
}

function renderOperator() {
  renderHeader();
  app.replaceChildren();
  if (!snapshot) return;
  const intro = panel(tr("1. 준비 → 2. 앱에서 실행 → 3. 나중에 비교", "1. Prepare → 2. Run in app → 3. Review a batch later"));
  intro.append(element("p", tr(
    "공개된 가상 업무 자료만 사용합니다. 이 창은 전용 결과 폴더만 관찰하며 대화 기록·화면·다른 업무 파일을 수집하지 않습니다.",
    "Use the fictional public office materials. This window watches only the dedicated output folder, never conversations, screens or unrelated work files."
  )));
  if (snapshot.warnings?.length) intro.append(element("p", tr("운영자와 평가자가 같아 부분 가림만 가능합니다. 환경 확인은 사용자 진술이며 자동으로 검증된 격리가 아닙니다.", "Blinding is partial because the operator is also the reviewer. Environment checks are operator attestations, not automatically verified isolation."), "callout warning"));
  if (!snapshot.initialized) { renderCreate(); return; }
  renderStudySummary();
  renderRunList();
  const run = snapshot.runs.find(item => item.id === selectedRun);
  if (run) renderRun(run);
  renderGroups();
  renderFreeze();
  renderExport();
}

function renderCreate() {
  const section = panel(tr("새 실험 만들기", "Create a study"));
  const phase = choice(section, tr("단계", "Phase"), optionPairs([
    ["calibration", "절차 확인 · 2개 과제", "Calibration · 2 cases"],
    ["discovery", "발견 · 4개 과제", "Discovery · 4 cases"],
    ["confirmation", "기준 고정 후 확인 · 2개 새 과제", "Confirmation after freezing · 2 fresh cases"],
  ]));
  section.append(element("p", tr("우선 현재 기기의 한 환경부터 시작하세요. 절차 확인 결과로 효과를 결론 내리지 않습니다.", "Start with one environment on this machine. Calibration does not establish an effect."), "help"));
  const cells = element("fieldset");
  cells.append(element("legend", tr("환경 선택 · 각각 별도로 보고", "Environments · reported separately")));
  const currentOS = snapshot.controller_environment?.os || (navigator.platform.toLowerCase().includes("win") ? "windows" : "macos");
  const selectors = snapshot.cells.map(cell => ({cell, input: check(cells,
    `${cell.os} · ${cell.host} · ${cell.requested_model}`, cell.id === `${currentOS}-work`)}));
  section.append(cells);
  const budget = field(section, tr("전체 실행 한도 · 실패한 실행과 재시도도 포함", "Total attempt cap · includes failed starts and retries"), "number", "6");
  budget.min = "1"; budget.max = "180";
  const planned = element("p", "", "callout");
  const update = () => {
    const count = selectors.filter(item => item.input.checked).length * (phase.value === "discovery" ? 12 : 6);
    planned.textContent = tr(`예정 ${count}회 · 자동 실행 0회. 한도는 예정 횟수 이상으로 직접 설정하세요.`, `${count} planned attempts · 0 automatic calls. Set the cap explicitly to cover the plan.`);
  };
  for (const item of selectors) item.input.addEventListener("change", update);
  phase.addEventListener("change", update);
  update();
  section.append(planned);
  section.append(button(tr("이 조건으로 실험 만들기", "Create this study"), async () => {
    const cells = selectors.filter(item => item.input.checked).map(item => item.cell.id);
    await api("create", {phase: phase.value, cells, budget: Number(budget.value)});
    await refresh();
    message(tr("실험을 만들었습니다. 아직 모델 실행은 시작하지 않았습니다.", "Study created. No model run has started."));
  }, true));
}

function renderStudySummary() {
  const section = panel(tr("이번 실험", "This study"));
  if (snapshot.study_id) {
    section.append(element("p", `${tr("실험 ID", "Study ID")}: ${snapshot.study_id}`, "mono"));
    section.append(copyButton(tr("실험 ID 복사 · 다음 확인 단계에서 참조", "Copy study ID · reference it in confirmation"), snapshot.study_id));
  }
  const stats = element("div", undefined, "grid");
  const completed = snapshot.runs.filter(run => run.status === "completed").length;
  for (const [value, label] of [
    [snapshot.phase, tr("단계", "Phase")],
    [`${snapshot.started_count} / ${snapshot.budget}`, tr("시작한 횟수 / 한도", "Started / attempt cap")],
    [completed, tr("승인한 최종 답변", "Approved final answers")],
  ]) add(stats, add(element("div", undefined, "stat"), document.createTextNode(String(value)), element("small", label)));
  section.append(stats);
  section.append(element("p", `${snapshot.pack.id} · ${snapshot.pack.version} · ${snapshot.pack.sha256}`, "mono muted"));
  if (snapshot.controller_environment) section.append(element("p", tr(
    `이 도구가 실행 중인 환경: ${snapshot.controller_environment.os} · ${snapshot.controller_environment.arch}. 앱의 실제 작업 실행 위치와는 별도입니다.`,
    `Lab controller: ${snapshot.controller_environment.os} · ${snapshot.controller_environment.arch}. This is separate from the app's actual execution mode.`
  ), "help"));
  const approval = snapshot.pack.approval;
  if (approval) {
    if (approval.b_instruction) details(section, tr("비교 전에 확인할 공통 B 지시", "Review the fixed B instruction before comparison"), approval.b_instruction[language] || approval.b_instruction.ko);
    for (const task of approval.cases || []) details(section, `${task.id} · ${task.title}`, task.deliverable);
  }
}

function renderRunList() {
  const section = panel(tr("실행할 과제", "Select an attempt"));
  const options = [["", tr("과제를 선택하세요", "Select an attempt")], ...snapshot.runs.map(run => [run.id,
    `${run.case_id} · ${run.cell_id} · ${run.arm} · #${run.attempt} · ${statusLabel(run.status)}`])];
  const select = choice(section, tr("표시된 순서대로 진행하면 됩니다", "Follow the displayed assignment order"), options, selectedRun);
  select.addEventListener("change", () => { selectedRun = select.value; prepared = null; renderOperator(); });
  section.append(element("p", tr("재시도는 진단용입니다. 비교에는 처음 배정된 답변만 사용하며 실패를 지우지 않습니다.", "Retries are diagnostic. Primary review uses original assignments; failures remain recorded."), "help"));
}

function renderRun(run) {
  const section = panel(`${run.case_id} · ${statusLabel(run.status)}`);
  section.append(element("p", `${run.cell_id} · ${run.arm} · #${run.attempt}`, "muted"));
  if (run.status === "planned") {
    section.append(button(tr("전용 작업 폴더와 프롬프트 준비", "Prepare the dedicated folder and prompt"), async () => {
      prepared = await api("prepare", {run_id: run.id});
      await refresh();
    }, true));
    renderTerminal(section, run);
  }
  const info = prepared?.run?.id === run.id ? prepared : run;
  if (run.status === "prepared" || run.status === "running") {
    renderPrepared(section, info);
    if (run.status === "prepared") renderPreflight(section, run);
    else renderCapture(section, run);
    renderTerminal(section, run);
  }
  if (["completed", "failed", "aborted", "blocked", "timed_out"].includes(run.status)) {
    section.append(button(tr("별도 시도로 재시도 준비", "Add a separate diagnostic retry"), async () => {
      const result = await api("retry", {run_id: run.id});
      selectedRun = result.run.id; prepared = null; await refresh();
    }));
  }
}

function renderPrepared(section, info) {
  if (info.actor_path) {
    section.append(element("p", tr("앱에는 아래 폴더 하나만 연결하세요. 상위 실험 폴더를 연결하면 비교 자료가 노출됩니다.", "Give the app only this folder. Granting its parent exposes evaluation material."), "callout warning"));
    section.append(element("p", info.actor_path, "mono"));
    section.append(copyButton(tr("폴더 경로 복사", "Copy folder path"), info.actor_path));
  }
  if (info.setup) {
    const guide = info.setup;
    section.append(element("h3", tr("해당 앱 설정", "Set up the actual app")));
    section.append(element("p", `${guide.profile || ""} · ${guide.status || "unknown"}`, "mono"));
    const list = element("ol");
    for (const step of guide.steps || []) list.append(element("li", step));
    section.append(list);
    for (const link of guide.links || []) {
      if (!/^https:\/\//.test(link.url)) continue;
      const anchor = element("a", link.title); anchor.href = link.url;
      anchor.target = "_blank"; anchor.rel = "noopener noreferrer";
      section.append(add(element("p"), anchor));
    }
  }
  if (info.prompt) {
    details(section, tr("앱에 보낼 프롬프트", "Prompt for the app"), info.prompt);
    section.append(copyButton(tr("프롬프트 복사", "Copy prompt"), info.prompt));
  }
  if (info.clarification_reply) details(section, tr("추가 질문을 받으면 이 고정 답변만 사용", "Use this fixed reply for unsolicited questions"), info.clarification_reply);
}

function renderPreflight(section, run) {
  const form = element("div", undefined, "spacer");
  form.append(element("h3", tr("실행 전 확인", "Before starting")));
  form.append(element("p", tr("새 폴더만으로 깨끗한 환경이 되지는 않습니다. 계정 플러그인·지침·메모리·연결 도구·상위 폴더 규칙을 직접 확인하세요. 확인값은 사용자 진술로 기록됩니다.", "A new folder is not a clean environment. Check account plugins, instructions, memory, connectors and parent rules. These checks are operator attestations."), "help"));
  const cell = snapshot.cells.find(item => item.id === run.cell_id);
  const old = run.preflight || {};
  form.append(element("p", tr(`요청 모델: ${cell.requested_model}`, `Requested model: ${cell.requested_model}`), "callout"));
  const grid = element("div", undefined, "grid"); form.append(grid);
  const model = choice(grid, tr("화면에서 확인한 모델", "Model observed in UI"), [["unknown", tr("아직 확인하지 않음", "Not yet observed")], [cell.expected_model, cell.expected_model]], old.observed_model);
  const effort = choice(grid, tr("화면에서 확인한 추론 수준", "Effort observed in UI"), [["unknown", tr("아직 확인하지 않음", "Not yet observed")], [cell.expected_effort, cell.expected_effort]], old.observed_effort);
  const version = field(grid, tr("앱 버전 · 모르면 unknown", "App version · unknown if unavailable"), "text", old.host_version || "unknown");
  version.maxLength = 64;
  const mode = choice(grid, tr("실제 작업 실행 위치", "Execution mode"), optionPairs([["unknown", "모름", "Unknown"], ["local", "로컬", "Local"], ["cloud", "클라우드", "Cloud"], ["sync", "동기화", "Sync"]]), old.execution_mode);
  const isolation = choice(grid, tr("계정·전역·작업 폴더 영향 확인", "Account / global / workspace influences"), optionPairs([["unknown", "아직 모름", "Unknown"], ["clear", "직접 확인: 혼입 없음", "Attested clear"], ["contaminated", "다른 지침/조건이 섞임", "Contaminated"]]), old.isolation);
  const environment = choice(grid, tr("환경 준비 방식", "Environment preparation"), optionPairs([["unknown", "모름", "Unknown"], ["fresh_os", "새로 설치한 OS", "Fresh OS"], ["clean_snapshot", "깨끗한 스냅샷 복원", "Clean snapshot"], ["new_user", "새 OS 사용자", "New OS user"], ["new_folder", "새 폴더만", "New folder only"]]), old.environment);
  const osState = choice(grid, tr("이 세션의 OpenSocrates 상태", "OpenSocrates in this session"), optionPairs([["unknown", "모름", "Unknown"], ["absent", "없음 · A/B 조건", "Absent · A/B"], ["enabled", "활성화됨 · C 조건", "Enabled · C"]]), old.opensocrates);
  const mapping = check(form, tr("Antigravity 요청 문자열을 UI의 Gemini 3.8 Flash Medium으로 대응하는 것을 직접 확인했습니다.", "I explicitly verified the Antigravity requested string maps to Gemini 3.8 Flash Medium in the UI."), old.model_mapping_confirmed || false);
  if (cell.host !== "antigravity") mapping.parentElement.classList.add("hide");
  const approved = check(form, tr("이 가상 업무 자료, 공통 산출물 범위와 고정 B 지시를 적절한 비교 표본으로 확인했습니다.", "I approve these fictional cases, common deliverable boundaries and fixed B instruction as a plausible comparison."), old.pack_approved || false);
  const exploratory = check(form, tr("격리를 확정할 수 없으면 탐색용으로만 실행합니다. 깨끗한 비교라고 보고하지 않습니다.", "If isolation is unknown, explicitly allow exploratory evidence only, never a clean comparison."), old.exploratory || false);
  const result = element("div");
  form.append(button(tr("확인 내용을 저장", "Save preflight"), async () => {
    const response = await api("preflight", {run_id: run.id, observed_model: model.value,
      observed_effort: effort.value, host_version: version.value, execution_mode: mode.value,
      isolation: isolation.value, environment: environment.value, opensocrates: osState.value,
      model_mapping_confirmed: mapping.checked, exploratory: exploratory.checked, pack_approved: approved.checked});
    await refresh();
    if (!response.can_start) message(tr("아직 시작할 수 없습니다: ", "Start is blocked: ") + (response.blockers || []).map(blockerLabel).join(" · "), true);
    else message(tr("확인 내용을 저장했습니다. 아래 버튼으로 기록을 시작한 다음 앱에서 실행하세요.", "Preflight saved. Start recording below, then run the task in the app."));
  }));
  form.append(result);
  form.append(button(tr("실행 1회를 기록하고 시작 · 다음에 앱에서 Run", "Reserve one attempt · then click Run in the app"), async () => {
    await api("start", {run_id: run.id}); await refresh();
    message(tr("실행을 기록했습니다. 이제 해당 앱의 새 작업에서 프롬프트를 실행하세요.", "Attempt reserved. Run the prompt in a fresh task in the actual app now."));
  }, true));
  section.append(form);
}

function renderCapture(section, run) {
  section.append(element("h3", tr("최종 결과 확인", "Collect the final deliverable")));
  section.append(element("p", tr("앱이 전용 폴더의 out/final.md에 최종 답변을 저장하도록 하세요. 파일 도착은 앱 완료나 OpenSocrates 적용의 증거가 아닙니다.", "Have the app save its final deliverable to out/final.md. File arrival does not prove host completion or OpenSocrates application."), "help"));
  const monitor = element("p", tr("파일 확인 중…", "Checking output…"), "callout");
  monitor.id = "outbox-monitor"; section.append(monitor);
  const previewArea = element("div");
  const evidence = element("div", undefined, "grid");
  const clarification = field(evidence, tr("추가 질문 횟수", "Clarification count"), "number", "0");
  clarification.min = "0"; clarification.max = "100";
  const delivery = choice(evidence, tr("전달에 대한 증거", "Delivery evidence"), optionPairs([["unknown", "모름", "Unknown"], ["operator_reported", "사용자 확인", "Operator reported"], ["observed", "직접 관찰", "Observed"]]));
  const application = choice(evidence, tr("실제 적용에 대한 증거", "Application evidence"), optionPairs([["unknown", "확인할 수 없음", "Unknown"], ["self_reported", "모델의 자기 보고만 있음", "Self reported only"]]));
  const tokens = field(evidence, tr("공식 화면에 나온 전체 토큰 수 · 선택 사항", "Total tokens from official UI · optional"), "number");
  tokens.min = "0";
  const elapsed = field(evidence, tr("확인한 소요 시간 · 초 · 선택 사항", "Observed elapsed seconds · optional"), "number");
  elapsed.min = "0";
  section.append(evidence);
  const finishData = () => ({run_id: run.id, status: "completed", synthetic_approved: true,
    clarification_count: Number(clarification.value), delivery: delivery.value, application: application.value,
    tokens: tokens.value === "" ? null : Number(tokens.value), elapsed_seconds: elapsed.value === "" ? null : Number(elapsed.value)});
  section.append(button(tr("최종 파일 미리보기", "Preview the final file"), async () => {
    const preview = await api("preview", {run_id: run.id});
    previewArea.replaceChildren();
    previewArea.append(element("pre", preview.text, "answer scroll"));
    const approval = check(previewArea, tr("아래 내용은 이번 가상 업무의 최종 산출물이며 실제 개인정보나 대화 기록이 없습니다. 이 내용만 보관하는 데 동의합니다.", "This is only the fictional task's final deliverable, without private information or conversation traces. I approve retaining this text."));
    previewArea.append(button(tr("이 미리보기 그대로 승인하고 완료", "Approve this exact preview and complete"), async () => {
      if (!approval.checked) throw new Error(tr("먼저 최종 내용의 보관을 승인하세요.", "Approve the final content first."));
      await api("finish", {...finishData(), intake: "file", approval_token: preview.approval_token});
      await refresh(); message(tr("승인한 최종 답변만 보관했습니다.", "Only the approved final deliverable was retained."));
    }, true));
  }));
  section.append(previewArea);
  const fallback = element("details");
  fallback.append(element("summary", tr("앱이 파일을 저장할 수 없으면 · 수동 입력", "If the app cannot save a file · manual intake")));
  fallback.append(element("p", tr("대화 전체를 붙여넣지 마세요. 가상 업무의 최종 산출물만 직접 골라 붙여넣으세요. 수동 수집으로 기록됩니다.", "Paste only the fictional final deliverable, never the conversation. This is recorded as manual intake."), "help"));
  const manual = field(fallback, tr("검토한 최종 산출물", "Reviewed final deliverable"), "textarea"); manual.maxLength = 65536;
  const approved = check(fallback, tr("붙여넣은 내용을 직접 확인했으며 가상 업무의 최종 내용만 보관하도록 승인합니다.", "I inspected the pasted text and approve retaining only this fictional final deliverable."));
  fallback.append(button(tr("수동 내용 승인 후 완료", "Approve manual text and complete"), async () => {
    if (!approved.checked) throw new Error(tr("먼저 최종 내용의 보관을 승인하세요.", "Approve the final content first."));
    await api("finish", {...finishData(), intake: "manual", final_text: manual.value});
    manual.value = ""; await refresh();
  }));
  section.append(fallback);
  void pollOutbox();
}

function renderTerminal(section, run) {
  const details = element("details");
  details.append(element("summary", tr("완료하지 못했거나 실행하지 못한 경우", "If the task failed or could not run")));
  const status = choice(details, tr("결과 상태", "Outcome"), optionPairs([["blocked", "진행 불가", "Blocked"], ["failed", "실패", "Failed"], ["aborted", "중단", "Aborted"], ["timed_out", "시간 초과", "Timed out"]]));
  details.append(element("p", tr("원본 오류나 대화 내용을 기록하지 않습니다. 시작하지 않은 시도를 실행했다고 세지 않습니다.", "Raw errors and conversations are not recorded. An unstarted attempt is not counted as an invocation."), "help"));
  details.append(button(tr("이 상태로 기록", "Record this outcome"), async () => {
    await api("finish", {run_id: run.id, status: status.value}); await refresh();
  }));
  section.append(details);
}

async function pollOutbox() {
  if (reviewMode || pollBusy || document.hidden || !snapshot) return;
  const run = snapshot.runs.find(item => item.id === selectedRun);
  if (!run || run.status !== "running") return;
  pollBusy = true;
  try {
    const data = await api("monitor", {run_id: run.id});
    const label = document.getElementById("outbox-monitor");
    if (label && selectedRun === run.id) label.textContent = data.exists
      ? tr(`파일 도착 · ${data.bytes}바이트 · ${data.ready ? "미리보기 가능" : "아직 준비되지 않음"}`, `Output found · ${data.bytes} bytes · ${data.ready ? "ready for preview" : "not ready"}`)
      : tr("최종 파일을 기다리고 있습니다. 다른 위치는 관찰하지 않습니다.", "Waiting for the final file. No other location is monitored.");
    if (label && data.overdue) label.append(document.createTextNode(tr(" 시간이 오래 걸리고 있습니다. 종료 상태는 직접 선택하세요.", " This attempt is overdue. Choose an outcome manually.")));
  } catch (_) { /* Transient polling failures never advance or retry an attempt. */ }
  finally { pollBusy = false; }
}

function renderGroups() {
  const section = panel(tr("답변 비교 · 한 묶음을 나중에 함께 읽기", "Review · read a completed batch later"));
  section.append(element("p", tr("같은 사람이 실행과 평가를 하므로 부분 가림입니다. 조건을 떠올렸다면 그대로 기록하세요. 처음 선택을 저장하기 전에는 조건 대응표를 불러오지 않습니다.", "The same operator is also the reviewer, so blinding is partial. Record any recognition. Condition mappings are not fetched before the first judgment is locked."), "help"));
  const rows = element("div", undefined, "stack");
  for (const group of snapshot.groups) {
    const row = element("div", undefined, "row");
    row.append(element("span", `${group.case_id} · ${group.cell_id}`));
    row.append(button(group.judged ? tr("저장한 평가 보기", "View locked review") : tr("전체 답변 비교하기", "Compare whole answers"), async () => {
      const url = `/review?group=${encodeURIComponent(group.id)}#token=${encodeURIComponent(token)}`;
      window.open(url, "_blank", "noopener");
    }));
    rows.append(row);
  }
  section.append(rows);
}

function renderFreeze() {
  if (snapshot.phase !== "confirmation") return;
  const section = panel(tr("후속 확인 실험의 기준 고정", "Freeze criteria for confirmation"));
  if (snapshot.criteria_frozen) {
    section.append(element("p", tr("이 실험의 기준이 이미 고정되었습니다. 이제 새 과제를 준비할 수 있습니다.", "Criteria are already frozen for this study. Fresh cases can now be prepared."), "callout"));
    return;
  }
  section.append(element("p", tr("발견 단계에서 실제로 중요했던 차이를 직접 확인한 뒤 기준을 고정하세요. 확인 단계의 새 답변을 보고 기준을 바꾸지 않습니다.", "Freeze what mattered after discovery, before seeing fresh confirmation answers. Do not change criteria after those answers."), "help"));
  const criteria = field(section, tr("직접 확인한 기준", "Human-confirmed criteria"), "textarea"); criteria.maxLength = 4000;
  const reference = field(section, tr("발견 실험 참조 ID", "Prior discovery study reference")); reference.maxLength = 200;
  const approved = check(section, tr("가상 업무에 대한 평가 기준만 포함했으며 이 기준을 고정합니다.", "This includes only synthetic-task criteria, which I confirm and freeze."));
  section.append(button(tr("기준 고정", "Freeze criteria"), async () => {
    await api("freeze", {criteria: criteria.value, discovery_reference: reference.value, synthetic_approved: approved.checked});
    await refresh();
    message(tr("기준을 고정했습니다. 기록한 기준은 덮어쓰지 않습니다.", "Criteria frozen. The saved criteria cannot be overwritten."));
  }));
}

function renderExport() {
  const section = panel(tr("이 기기의 결과 내보내기", "Export this machine's results"));
  section.append(element("p", tr("승인된 최종 답변과 잠근 평가, 허용된 메타데이터만 로컬 파일로 내보냅니다. 네트워크 업로드는 하지 않습니다. Mac·Windows 결과는 각 환경별로 합칩니다.", "Export only approved finals, locked judgments and allowed metadata locally. No upload. Mac and Windows evidence remains separated by environment."), "help"));
  const report = element("div");
  section.append(button(tr("보고서와 결과 파일 만들기", "Create report and export"), async () => {
    const result = await api("export");
    const blob = new Blob([JSON.stringify(result.export, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob);
    const anchor = element("a", tr("결과 JSON 저장", "Save result JSON"), "button");
    anchor.href = url; anchor.download = String(result.filename || "office-results.json").split(/[\\/]/).pop();
    anchor.addEventListener("click", () => setTimeout(() => URL.revokeObjectURL(url), 30000), {once: true});
    report.replaceChildren(element("pre", typeof result.report === "string" ? result.report : JSON.stringify(result.report, null, 2), "answer scroll"), anchor);
  }));
  section.append(report);
}

async function loadReview() {
  if (!groupId) throw new Error(tr("평가할 묶음이 없습니다. 운영 화면의 비교 버튼을 사용하세요.", "No group selected. Use a review button in the operator window."));
  packet = await api("packet", {group_id: groupId});
  renderReview();
}

function renderReview() {
  renderHeader(); app.replaceChildren();
  if (!packet) return;
  const task = panel(packet.title);
  task.append(element("p", tr("업무에 실제로 쓸 답변을 먼저 고르세요. 이유를 설명하지 못해도 괜찮습니다. 풋터나 문체로 조건을 알아봤다면 뒤에서 기록합니다.", "Choose what you would actually use. It is fine if you cannot explain why. Record any condition recognition from wording or footers afterward."), "callout"));
  task.append(element("p", tr("모든 답변에 같은 안전한 Markdown 일부 표시를 적용합니다: 제목·문단·목록·표·코드·인용·굵은 글씨. 지원하지 않는 문법과 링크는 글자로 표시하며 이미지는 불러오지 않습니다. 각 답변의 원문 보기는 저장된 내용을 그대로 보여줍니다.", "All answers use the same safe Markdown subset: headings, paragraphs, lists, tables, code, quotes and bold. Unsupported syntax and links remain text; images never load. Each original-text view preserves the exact stored answer."), "help"));
  details(task, tr("공통 업무 요청", "Common task"), packet.prompt);
  details(task, tr("산출물 범위", "Deliverable boundary"), packet.deliverable);
  for (const material of packet.materials || []) details(task, material.name, material.text);
  const answers = element("div", undefined, "review-answers");
  for (const answer of packet.answers) {
    const card = element("section", undefined, "card");
    add(card, element("h2", answer.alias), markdown(answer.text));
    details(card, tr("변경하지 않은 원문 보기", "View unchanged original text"), answer.text);
    card.append(copyButton(tr("원문 복사", "Copy original"), answer.text));
    answers.append(card);
  }
  app.append(answers);
  if (!packet.judged) renderJudgment();
  else renderLockedJudgment();
}

function renderJudgment() {
  const section = panel(tr("첫 선택과 느낌", "Your first choice and reaction"));
  const pick = choice(section, tr("실제로 사용할 답변", "Answer you would actually use"), [
    ["", tr("선택하세요", "Choose")], ...packet.answers.map(answer => [answer.alias, answer.alias]),
    ["tie", tr("동점 · 실질적인 차이 없음", "Tie · no practical difference")],
    ["all_unusable", tr("모두 쓰기 어려움", "All unusable")],
  ]);
  const reaction = field(section, tr("처음 든 느낌 · 선택 사항 · 설명하기 어려우면 비워도 됨", "First reaction · optional · leave blank if hard to explain"), "textarea"); reaction.maxLength = 4000;
  const grid = element("div", undefined, "grid"); section.append(grid);
  const confidence = choice(grid, tr("선택 확신", "Confidence"), optionPairs([["medium", "중간", "Medium"], ["low", "낮음", "Low"], ["high", "높음", "High"]]));
  const recognition = choice(grid, tr("어떤 조건인지 알아보았나요?", "Did you recognize the conditions?"), optionPairs([["unknown", "모르겠음", "Unknown"], ["guessed", "짐작함", "Guessed"], ["known", "알고 있음", "Known"]]));
  const reproduced = choice(grid, tr("평소 느끼던 차이를 이 비교에서 다시 느꼈나요?", "Did this reproduce the difference you normally feel?"), optionPairs([["uncertain", "아직 모르겠음", "Uncertain"], ["yes", "그렇다", "Yes"], ["no", "아니다", "No"]]));
  const editing = element("details");
  editing.append(element("summary", tr("말로 설명하기 어렵다면 · 직접 고친 본문 남기기 · 선택 사항", "If hard to explain · optionally keep your own edited draft")));
  editing.append(element("p", tr("원래 답변은 바뀌지 않습니다. 실제로 쓰려고 고친 가상 업무 본문만 입력하세요.", "Original answers remain unchanged. Enter only your own edited fictional deliverable."), "help"));
  const edit = field(editing, tr("내가 고친 본문", "My edited draft"), "textarea"); edit.maxLength = 65536;
  section.append(editing);
  const approved = check(section, tr("입력한 느낌에는 이 가상 업무에 대한 평가만 포함됩니다. 이 첫 판단을 변경할 수 없도록 저장합니다.", "My comments concern only this fictional task. Save this first judgment immutably."));
  section.append(button(tr("첫 판단 저장 · 이후 조건 확인 가능", "Lock first judgment · then conditions can be revealed"), async () => {
    const data = {group_id: groupId, choice: pick.value, first_reaction: reaction.value,
      confidence: confidence.value, recognition: recognition.value, reproduced_experience: reproduced.value,
      synthetic_approved: approved.checked};
    if (edit.value) data.edit = edit.value;
    await api("judge", data);
    packet = await api("packet", {group_id: groupId}); renderReview();
    message(tr("첫 판단을 저장했습니다. 조건 확인은 아래에서 별도로 선택하세요.", "First judgment locked. Reveal conditions separately below."));
  }, true));
}

function renderLockedJudgment() {
  const section = panel(tr("첫 판단이 잠겼습니다", "First judgment locked"));
  if (packet.judgment) {
    section.append(element("p", `${tr("선택", "Choice")}: ${packet.judgment.choice}`));
    if (packet.judgment.first_reaction) section.append(element("pre", packet.judgment.first_reaction, "answer"));
  }
  section.append(button(tr("이제 조건과 사실 확인 항목 보기", "Reveal conditions and factual guardrails now"), async () => {
    reveal = await api("reveal", {group_id: groupId}); renderReveal(section);
  }));
  if (reveal) renderReveal(section);
}

function renderReveal(section) {
  const previous = document.getElementById("revealed"); if (previous) previous.remove();
  const area = element("div"); area.id = "revealed";
  area.append(element("h3", tr("조건 대응표", "Condition mapping")));
  area.append(element("pre", JSON.stringify(reveal.mapping, null, 2), "answer scroll"));
  area.append(element("h3", tr("별도로 확인할 사실·참조", "Separate fact and reference guardrails")));
  const list = element("ul"); for (const item of reveal.evaluator_checks || []) list.append(element("li", item));
  area.append(list);
  area.append(element("p", tr("이 항목은 사실 확인을 돕습니다. AI의 선택이나 효과 검증 결과가 아닙니다. 한 사람의 선호를 일반 사용자 전체로 확대하지 않습니다.", "These checks support factual review, not an AI preference vote or proof of benefit. One person's preference does not establish general-user effects."), "help"));
  section.append(area);
}

document.getElementById("language").addEventListener("click", () => {
  language = language === "ko" ? "en" : "ko";
  if (reviewMode) renderReview(); else renderOperator();
});
setInterval(() => { void pollOutbox(); }, 4000);
async function initialize() {
  renderHeader();
  try {
    if (!token) throw new Error(tr("실행기에서 연 전용 주소로 접속하세요.", "Open the private URL supplied by the launcher."));
    if (reviewMode) await loadReview(); else await refresh();
  } catch (error) { app.replaceChildren(); message(error.message || tr("연결할 수 없습니다.", "Unable to connect."), true); }
}
void initialize();
