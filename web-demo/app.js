// This visual explanation reproduces the observable rules in the public Python core.
// It runs in the visitor's browser; it does not connect to Dragonfly or call an LLM.
const INITIAL_DOCUMENTS = {
  "harbor-policy": "Harbor permits expire after 30 days.",
  "museum-policy": "Museum tickets are refundable within 14 days."
};
const QUESTION = "When do harbor permits expire?";
const ENCODER = new TextEncoder();
const $ = (id) => document.getElementById(id);
const nextButton = $("nextButton");
const resetButton = $("resetButton");

let phase = 0;
let documents = { ...INITIAL_DOCUMENTS };
let cache = new Map();
let oldVersion = "";
let currentVersion = "";
let questionHash = "";
let firstResults = null;
let finalResults = null;

async function sha256(value) {
  const bytes = await crypto.subtle.digest("SHA-256", ENCODER.encode(value));
  return [...new Uint8Array(bytes)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function documentVersion(docs) {
  const canonical = JSON.stringify(Object.fromEntries(Object.entries(docs).sort(([a], [b]) => a.localeCompare(b))));
  return sha256(canonical);
}

function setText(id, value) { $(id).textContent = value; }
function state(id, label, tone) { const el = $(id); el.textContent = label; el.className = `state-tag ${tone}`; }
function answer(id, text, tone = "") { const el = $(id); el.textContent = text; el.className = `answer ${tone}`.trim(); }
function keyLabel(mode, version) {
  return mode === "naive" ? `extractive-v1 · unversioned · q:${questionHash.slice(0, 10)}…` : `extractive-v1 · source:${version.slice(0, 10)}… · q:${questionHash.slice(0, 10)}…`;
}
function lookup(mode) {
  const versionPart = mode === "versioned" ? currentVersion : "unversioned";
  const key = `citation-demo:answer:${mode}:extractive-v1:${versionPart}:${questionHash}`;
  let result = cache.get(key);
  const hit = Boolean(result);
  if (!result) {
    const excerpt = documents["harbor-policy"];
    result = { answer: `The source says: ${excerpt}`, citation: { document_id: "harbor-policy", excerpt } };
    cache.set(key, result);
  }
  return { ...result, hit, valid: result.citation.excerpt === documents[result.citation.document_id] };
}
function updateSteps() {
  ["stepOne", "stepTwo", "stepThree"].forEach((id, index) => {
    $(id).className = phase > index + 1 ? "done" : phase === index + 1 ? "active" : "";
  });
  setText("stepBadge", `STEP ${phase} / 3`);
}

function render() {
  updateSteps();
  const changed = phase >= 2;
  setText("sourceVersion", changed ? "v2 · 수정됨" : "v1 · 원문");
  $("sourceText").innerHTML = changed
    ? "“Harbor permits expire after <strong>45 days.</strong>”"
    : "“Harbor permits expire after <strong>30 days.</strong>”";
  setText("sourceHash", `${currentVersion.slice(0, 16)}…`);
  setText("naiveKey", keyLabel("naive", currentVersion));
  setText("versionedKey", keyLabel("versioned", currentVersion));
  resetButton.disabled = phase === 0;

  if (phase === 0) {
    for (const mode of ["naive", "versioned"]) {
      state(`${mode}State`, "대기 중", "neutral");
      answer(`${mode}Answer`, "실험을 시작하면 답변이 여기에 표시됩니다.", "muted");
      setText(`${mode}Hit`, "—"); setText(`${mode}Valid`, "—");
    }
    setText("statusText", "첫 답변을 저장해 두 캐시의 출발점을 맞춥니다.");
    nextButton.innerHTML = '1. 답변 캐시에 저장 <span aria-hidden="true">→</span>';
  } else if (phase === 1) {
    for (const mode of ["naive", "versioned"]) {
      state(`${mode}State`, "처음 생성", "neutral");
      answer(`${mode}Answer`, `허가 기간은 ${firstResults[mode].citation.excerpt.includes("30 days") ? "30" : "45"}일입니다.`);
      setText(`${mode}Hit`, firstResults[mode].hit ? "HIT" : "MISS → 저장"); setText(`${mode}Valid`, firstResults[mode].valid ? "일치" : "불일치");
    }
    setText("statusText", "두 방식 모두 원문 30일을 인용한 답변을 캐시에 저장했습니다.");
    nextButton.innerHTML = '2. 원문을 45일로 수정 <span aria-hidden="true">→</span>';
  } else if (phase === 2) {
    for (const mode of ["naive", "versioned"]) {
      state(`${mode}State`, "재조회 전", "neutral");
      answer(`${mode}Answer`, "저장된 답변: 허가 기간은 30일입니다.", "muted");
      setText(`${mode}Hit`, "대기"); setText(`${mode}Valid`, "재검사 예정");
    }
    setText("statusText", "원문이 45일로 바뀌었습니다. 이제 같은 질문을 다시 보냅니다.");
    nextButton.innerHTML = '3. 같은 질문 다시 보내기 <span aria-hidden="true">→</span>';
  } else {
    for (const mode of ["naive", "versioned"]) {
      const result = finalResults[mode];
      state(`${mode}State`, result.valid ? "현재 원문" : "오래된 인용", result.valid ? "good" : "bad");
      answer(`${mode}Answer`, `허가 기간은 ${result.citation.excerpt.includes("30 days") ? "30" : "45"}일입니다.`, result.valid ? "good" : "bad");
      setText(`${mode}Hit`, result.hit ? "HIT" : "MISS → 재생성");
      setText(`${mode}Valid`, result.valid ? "일치 ✓" : "불일치 ✕");
    }
    setText("statusText", "일반 캐시는 오래된 30일 답변을 재사용했습니다. 버전 기반 캐시는 새 원문으로 45일 답변을 만들었습니다.");
    nextButton.innerHTML = '실험 완료 <span aria-hidden="true">✓</span>';
    nextButton.disabled = true;
  }
  if (phase < 3) nextButton.disabled = false;
}

async function reset() {
  phase = 0; documents = { ...INITIAL_DOCUMENTS }; cache = new Map();
  oldVersion = await documentVersion(documents);
  currentVersion = oldVersion;
  questionHash = await sha256(QUESTION.toLowerCase().trim().replace(/\s+/g, " "));
  firstResults = null;
  finalResults = null;
  render();
}

async function advance() {
  if (phase === 0) {
    firstResults = { naive: lookup("naive"), versioned: lookup("versioned") };
  } else if (phase === 1) {
    documents["harbor-policy"] = "Harbor permits expire after 45 days.";
    currentVersion = await documentVersion(documents);
  } else if (phase === 2) {
    finalResults = { naive: lookup("naive"), versioned: lookup("versioned") };
  }
  phase = Math.min(phase + 1, 3);
  render();
}

nextButton.addEventListener("click", () => { advance().catch(showError); });
resetButton.addEventListener("click", () => { reset().catch(showError); });
function showError() { setText("statusText", "브라우저에서 해시를 계산하지 못했습니다. HTTPS 또는 localhost에서 다시 열어 주세요."); nextButton.disabled = true; }
reset().catch(showError);
