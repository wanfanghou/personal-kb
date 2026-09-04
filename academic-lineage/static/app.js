'use strict';

/* 学术谱系本地管理页逻辑 */

const state = {
  previews: { mentor: null, student: null },
  centerId: null,
  up: 3,
  down: 2,
};

const REL_TYPE_ZH = {
  phd: '博士导师',
  master: '硕士导师',
  postdoc: '博士后合作导师',
  informal: '非正式指导',
  other: '其他',
};

const STATUS_ZH = { draft: '草稿', verified: '已确认', rejected: '已拒绝' };
const CONFIDENCE_ZH = { confirmed: 'confirmed 已确认', probable: 'probable 很可能', uncertain: 'uncertain 不确定' };

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.error || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return body;
}

/* ---------- 双 URL 录入 ---------- */

function setEntryStatus(message, isError = false) {
  const el = $('entry-status');
  el.textContent = message;
  el.className = 'status ' + (isError ? 'error' : 'ok');
}

function renderIdentityCard(role, preview) {
  const card = $(`${role}-card`);
  const ok = !preview.fetch_error;
  card.hidden = false;
  card.innerHTML = `
    <div class="identity-head">
      <span class="identity-label">${role === 'mentor' ? '导师' : '学生'}</span>
      ${ok
        ? '<span class="badge badge-ok">预览成功</span>'
        : '<span class="badge badge-warn">抓取失败，可手动填写</span>'}
    </div>
    <input class="name-input" id="${role}-name" type="text"
           value="${escapeHtml(preview.candidate_name)}"
           placeholder="姓名（可手动修改）">
    <input class="title-input" id="${role}-title" type="text"
           placeholder="${role === 'mentor' ? '导师职称（如 Professor）' : '学生当前职称（如 Assistant Professor）'}">
    <div class="identity-url">${escapeHtml(preview.normalized_url)}</div>
    ${ok && preview.title ? `<div class="identity-title">标题：${escapeHtml(preview.title)}</div>` : ''}
    ${!ok ? `<div class="identity-error">${escapeHtml(preview.fetch_error)}</div>` : ''}
    ${preview.description ? `<div class="identity-desc">${escapeHtml(preview.description)}</div>` : ''}
  `;
  const nameInput = $(`${role}-name`);
  nameInput.addEventListener('input', () => { updateSentence(); updateConfirmEnabled(); });
}

async function previewRole(role) {
  const urlInput = $(`${role}-url`);
  const url = urlInput.value.trim();
  if (!url) {
    setEntryStatus(`请先填写${role === 'mentor' ? '导师' : '学生'}主页 URL`, true);
    return;
  }
  const button = $(`preview-${role}`);
  button.disabled = true;
  button.textContent = '获取中…';
  try {
    const result = await api('/api/preview-person', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
    state.previews[role] = result;
    renderIdentityCard(role, result);
    updateSentence();
    updateConfirmEnabled();
    setEntryStatus(result.fetch_error
      ? '抓取失败，请手动填写姓名后仍可保存'
      : '预览成功，请确认身份信息');
  } catch (error) {
    setEntryStatus(`预览失败：${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = '预览';
  }
}

function currentName(role) {
  const input = $(`${role}-name`);
  if (input) return input.value.trim();
  const preview = state.previews[role];
  return preview ? (preview.candidate_name || '').trim() : '';
}

function currentTitle(role) {
  const input = $(`${role}-title`);
  return input ? input.value.trim() : '';
}

function updateSentence() {
  const mentorName = currentName('mentor');
  const studentName = currentName('student');
  const sentence = $('confirmation-sentence');
  if (mentorName && studentName) {
    $('sentence-mentor').textContent = mentorName;
    $('sentence-student').textContent = studentName;
    sentence.hidden = false;
  } else {
    sentence.hidden = true;
  }
}

function updateConfirmEnabled() {
  const ready = state.previews.mentor && state.previews.student
    && currentName('mentor') && currentName('student');
  $('confirm-btn').disabled = !ready;
}

async function confirmEntry() {
  const mentorName = currentName('mentor');
  const studentName = currentName('student');
  if (!mentorName || !studentName || !state.previews.mentor || !state.previews.student) return;

  const publicFlag = $('public-flag').checked;
  const payload = {
    relationship_type: $('relationship-type').value,
    status: $('rel-status').value,
    confidence: $('confidence').value,
    evidence_url: $('evidence-url').value.trim() || state.previews.student.normalized_url,
    public: publicFlag,
  };
  const startYear = $('start-year').value;
  const endYear = $('end-year').value;
  const institution = $('rel-institution').value.trim();
  const studentPlacement = $('student-placement').value.trim();
  const evidenceText = $('evidence-text').value.trim();
  const notesPrivate = $('notes-private').value.trim();
  if (startYear) payload.start_year = parseInt(startYear, 10);
  if (endYear) payload.end_year = parseInt(endYear, 10);
  if (institution) payload.institution = institution;
  if (studentPlacement) payload.student_placement = studentPlacement;
  if (evidenceText) payload.evidence_text = evidenceText;
  if (notesPrivate) payload.notes_private = notesPrivate;

  const confirmBtn = $('confirm-btn');
  confirmBtn.disabled = true;
  setEntryStatus('正在保存…');
  try {
    const mentor = await api('/api/persons', {
      method: 'POST',
      body: JSON.stringify({
        name: mentorName,
        title: currentTitle('mentor') || null,
        homepage_url: state.previews.mentor.normalized_url,
        homepage_title: state.previews.mentor.title || null,
        public: publicFlag,
      }),
    });
    const student = await api('/api/persons', {
      method: 'POST',
      body: JSON.stringify({
        name: studentName,
        title: currentTitle('student') || null,
        homepage_url: state.previews.student.normalized_url,
        homepage_title: state.previews.student.title || null,
        public: publicFlag,
      }),
    });
    const mentorship = await api('/api/mentorships', {
      method: 'POST',
      body: JSON.stringify({
        ...payload,
        mentor_id: mentor.person.id,
        student_id: student.person.id,
      }),
    });
    setEntryStatus(`已保存：学生 ${studentName} 是导师 ${mentorName} 的学生`);
    await loadLineage(student.person.id, 1, 0);
    clearEntryForm();
  } catch (error) {
    if (error.status === 409) {
      setEntryStatus(`关系已存在，未重复创建：${error.message}`, true);
    } else {
      setEntryStatus(`保存失败：${error.message}`, true);
    }
  } finally {
    updateConfirmEnabled();
  }
}

function clearEntryForm() {
  ['mentor', 'student'].forEach((role) => {
    $(`${role}-card`).hidden = true;
    state.previews[role] = null;
  });
  ['start-year', 'end-year', 'rel-institution', 'student-placement', 'evidence-url', 'evidence-text', 'notes-private'].forEach(
    (id) => { $(id).value = ''; }
  );
  $('confirmation-sentence').hidden = true;
  updateConfirmEnabled();
}

/* ---------- 搜索 ---------- */

let searchTimer = null;

function bindSearch() {
  $('search-input').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 250);
  });
}

async function runSearch() {
  const q = $('search-input').value.trim();
  const list = $('search-results');
  if (!q) { list.innerHTML = ''; return; }
  try {
    const data = await api(`/api/persons?q=${encodeURIComponent(q)}`);
    list.innerHTML = '';
    if (!data.persons.length) {
      list.innerHTML = '<li class="muted">没有匹配的学者</li>';
      return;
    }
    for (const person of data.persons) {
      const item = document.createElement('li');
      item.className = 'result-item';
      item.innerHTML = `
        <span class="result-name">${escapeHtml(person.name)}</span>
        ${person.institution ? `<span class="result-meta">${escapeHtml(person.institution)}</span>` : ''}
        ${person.public
          ? '<span class="badge badge-pub">公开</span>'
          : '<span class="badge badge-priv">私有</span>'}`;
      item.addEventListener('click', () => selectPerson(person));
      list.appendChild(item);
    }
  } catch (error) {
    list.innerHTML = `<li class="status error">${escapeHtml(error.message)}</li>`;
  }
}

function selectPerson(person) {
  state.centerId = person.id;
  state.up = 3;
  state.down = 2;
  loadLineage(person.id, state.up, state.down);
}

/* ---------- 图谱 ---------- */

let cy = null;

function ensureCy() {
  if (cy) return cy;
  cy = cytoscape({
    container: $('cy'),
    elements: [],
    style: [
      {
        selector: 'node',
        style: {
          label: 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': 11,
          color: '#1f2937',
          'background-color': '#93c5fd',
          width: 36,
          height: 36,
          'border-width': 1.5,
          'border-color': '#2563eb',
          'text-wrap': 'wrap',
          'text-max-width': 90,
        },
      },
      {
        selector: 'node[type = "mentor"]',
        style: { 'background-color': '#fca5a5', 'border-color': '#dc2626' },
      },
      {
        selector: 'node.center',
        style: {
          width: 50,
          height: 50,
          'background-color': '#fde047',
          'border-color': '#ca8a04',
          'border-width': 3,
          'font-size': 12,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 2,
          'line-color': '#9ca3af',
          'target-arrow-color': '#6b7280',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 1.1,
        },
      },
    ],
    layout: { name: 'preset' },
    wheelSensitivity: 0.25,
  });
  cy.on('tap', 'node', (event) => showNodeDetails(event.target));
  cy.on('tap', 'edge', (event) => showEdgeDetails(event.target));
  return cy;
}

function renderGraph(nodes, edges) {
  const cyGraph = ensureCy();
  const sourceIds = new Set(edges.map((e) => e.mentor_id));
  const elements = [
    ...nodes.map((n) => ({
      data: { id: n.id, label: n.name, type: sourceIds.has(n.id) ? 'mentor' : 'student', ...n },
      classes: n.id === state.centerId ? 'center' : '',
    })),
    ...edges.map((e) => ({
      data: { id: e.id, source: e.mentor_id, target: e.student_id, ...e },
    })),
  ];
  cyGraph.elements().remove();
  cyGraph.add(elements);
  cyGraph.layout({
    name: 'breadthfirst',
    directed: true,
    roots: `#${state.centerId}`,
    padding: 35,
    spacingFactor: 1.2,
  }).run();
  cyGraph.fit(undefined, 45);
}

function findName(nodes, id) {
  const node = nodes.find((n) => n.id === id);
  return node ? node.name : id;
}

async function loadLineage(personId, up, down) {
  try {
    const data = await api(
      `/api/persons/${encodeURIComponent(personId)}/lineage?up=${up}&down=${down}`
    );
    state.centerId = data.center_id;
    state.up = data.up;
    state.down = data.down;
    renderGraph(data.nodes, data.edges);
    $('graph-info').textContent =
      `中心：${findName(data.nodes, data.center_id)} · 向上 ${data.up} 代 · 向下 ${data.down} 代 · ` +
      `${data.nodes.length} 个节点 / ${data.edges.length} 条边`;
    const center = data.nodes.find((n) => n.id === data.center_id);
    if (center) renderPersonDetails(center);
  } catch (error) {
    $('graph-info').textContent = `加载失败：${error.message}`;
  }
}

function expandUp() {
  if (state.up >= 10 || !state.centerId) return;
  state.up += 1;
  loadLineage(state.centerId, state.up, state.down);
}

function expandDown() {
  if (state.down >= 10 || !state.centerId) return;
  state.down += 1;
  loadLineage(state.centerId, state.up, state.down);
}

/* ---------- 详情面板 ---------- */

let detailPerson = null;

function renderPersonDetails(person) {
  detailPerson = person;
  $('detail-title').textContent = `学者：${person.name}`;
  $('detail-content').innerHTML = `
    <dl class="detail-list">
      <dt>姓名</dt><dd>${escapeHtml(person.name)}</dd>
      ${person.name_en ? `<dt>英文名</dt><dd>${escapeHtml(person.name_en)}</dd>` : ''}
      ${person.title ? `<dt>职称/头衔</dt><dd>${escapeHtml(person.title)}</dd>` : ''}
      ${person.institution ? `<dt>机构</dt><dd>${escapeHtml(person.institution)}</dd>` : ''}
      ${person.field ? `<dt>研究方向</dt><dd>${escapeHtml(person.field)}</dd>` : ''}
      ${person.editorial_roles && person.editorial_roles.length
        ? `<dt>编委会任职</dt><dd>${escapeHtml(person.editorial_roles.join('、'))}</dd>` : ''}
      ${person.honors && person.honors.length
        ? `<dt>荣誉 / 人才称号</dt><dd>${escapeHtml(person.honors.join('、'))}</dd>` : ''}
      ${person.aliases && person.aliases.length
        ? `<dt>别名</dt><dd>${escapeHtml(person.aliases.join('、'))}</dd>` : ''}
      <dt>主页</dt><dd><a href="${escapeHtml(person.homepage_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(person.homepage_url)}</a></dd>
      <dt>公开</dt><dd>${person.public ? '是' : '否（仅本地，不参与公开导出）'}</dd>
      ${person.notes_private ? `<dt>私有备注</dt><dd>${escapeHtml(person.notes_private)}</dd>` : ''}
    </dl>
    <div class="detail-actions">
      <button class="btn btn-small" data-action="edit-person">编辑学者信息</button>
      <button class="btn btn-small" data-action="expand-up">↑ 向上展开一代</button>
      <button class="btn btn-small" data-action="expand-down">↓ 向下展开一代</button>
      <button class="btn btn-small" data-action="reset-view">重置视图</button>
    </div>
  `;
}

function renderPersonEditForm(person) {
  $('detail-title').textContent = `编辑：${person.name}`;
  $('detail-content').innerHTML = `
    <div class="edit-form">
      <label>姓名 <input id="edit-name" type="text" value="${escapeHtml(person.name)}"></label>
      <label>英文名 <input id="edit-name-en" type="text" value="${escapeHtml(person.name_en)}"></label>
      <label>职称/头衔 <input id="edit-title" type="text" value="${escapeHtml(person.title)}" placeholder="如：Professor / 教授"></label>
      <label>机构 <input id="edit-institution" type="text" value="${escapeHtml(person.institution)}"></label>
      <label>研究方向 <input id="edit-field" type="text" value="${escapeHtml(person.field)}"></label>
      <label>别名（逗号分隔）<input id="edit-aliases" type="text" value="${escapeHtml((person.aliases || []).join(', '))}"></label>
      <label>编委会任职（每行一个）<textarea id="edit-editorial" rows="3">${escapeHtml((person.editorial_roles || []).join('\n'))}</textarea></label>
      <label>荣誉 / 人才称号（每行一个，如：国家杰青）<textarea id="edit-honors" rows="3">${escapeHtml((person.honors || []).join('\n'))}</textarea></label>
      <label class="checkbox-row"><input id="edit-public" type="checkbox" ${person.public ? 'checked' : ''}> 公开（允许导出到公开站点）</label>
      <label>私有备注 <input id="edit-notes" type="text" value="${escapeHtml(person.notes_private)}"></label>
      <div class="detail-actions">
        <button class="btn btn-primary btn-small" data-action="save-person">保存</button>
        <button class="btn btn-small" data-action="cancel-edit">取消</button>
      </div>
    </div>
  `;
}

function splitLines(id) {
  return $(id).value.split('\n').map((s) => s.trim()).filter(Boolean);
}

async function savePersonEdit(personId) {
  try {
    const updated = await api(`/api/persons/${encodeURIComponent(personId)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: $('edit-name').value.trim(),
        name_en: $('edit-name-en').value.trim(),
        title: $('edit-title').value.trim(),
        institution: $('edit-institution').value.trim(),
        field: $('edit-field').value.trim(),
        aliases: $('edit-aliases').value.split(/[,，]/).map((s) => s.trim()).filter(Boolean),
        editorial_roles: splitLines('edit-editorial'),
        honors: splitLines('edit-honors'),
        public: $('edit-public').checked,
        notes_private: $('edit-notes').value.trim(),
      }),
    });
    renderPersonDetails(updated.person);
    await loadLineage(personId, state.up, state.down);
  } catch (error) {
    $('detail-content').innerHTML = `<p class="status error">保存失败：${escapeHtml(error.message)}</p>`;
  }
}

async function showNodeDetails(node) {
  const person = node.data();
  renderPersonDetails(person);
  state.centerId = person.id;
}

async function showEdgeDetails(edge) {
  $('detail-title').textContent = '关系详情（加载中…）';
  try {
    const data = await api(`/api/mentorships/${edge.id()}`);
    const m = data.mentorship;
    const years = [m.start_year, m.end_year].filter(Boolean).join(' – ');
    $('detail-title').textContent = `关系：${REL_TYPE_ZH[m.relationship_type] || m.relationship_type}`;
    $('detail-content').innerHTML = `
      <dl class="detail-list">
        <dt>导师</dt><dd>${escapeHtml(m.mentor_name)}</dd>
        <dt>学生</dt><dd>${escapeHtml(m.student_name)}</dd>
        <dt>类型</dt><dd>${REL_TYPE_ZH[m.relationship_type] || m.relationship_type}</dd>
        <dt>年份</dt><dd>${years || '未填写'}</dd>
        ${m.institution ? `<dt>机构</dt><dd>${escapeHtml(m.institution)}</dd>` : ''}
        ${m.student_placement ? `<dt>学生毕业去向</dt><dd>${escapeHtml(m.student_placement)}</dd>` : ''}
        <dt>状态</dt><dd>${STATUS_ZH[m.status] || m.status}</dd>
        <dt>可信度</dt><dd>${CONFIDENCE_ZH[m.confidence] || m.confidence}</dd>
        <dt>公开</dt><dd>${m.public ? '是' : '否（仅本地）'}</dd>
        <dt>证据 URL</dt><dd><a href="${escapeHtml(m.evidence_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(m.evidence_url)}</a></dd>
        ${m.evidence_text ? `<dt>证据说明</dt><dd>${escapeHtml(m.evidence_text)}</dd>` : ''}
        ${m.notes_private ? `<dt>私有备注</dt><dd>${escapeHtml(m.notes_private)}</dd>` : ''}
      </dl>
    `;
  } catch (error) {
    $('detail-title').textContent = '关系详情';
    $('detail-content').innerHTML = `<p class="status error">加载失败：${escapeHtml(error.message)}</p>`;
  }
}

function bindDetailActions() {
  $('detail-content').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'expand-up') expandUp();
    if (action === 'expand-down') expandDown();
    if (action === 'reset-view') ensureCy().fit(undefined, 45);
    if (action === 'edit-person' && detailPerson) renderPersonEditForm(detailPerson);
    if (action === 'save-person' && detailPerson) savePersonEdit(detailPerson.id);
    if (action === 'cancel-edit' && detailPerson) renderPersonDetails(detailPerson);
  });
}

/* ---------- 导出 ---------- */

async function exportPublic() {
  const button = $('export-btn');
  const status = $('export-status');
  button.disabled = true;
  status.textContent = '导出中…';
  try {
    const result = await api('/api/export/public', { method: 'POST' });
    status.textContent = `已导出：${result.people} 位学者 / ${result.relationships} 条关系 → public/data/`;
  } catch (error) {
    status.textContent = `导出失败：${error.message}`;
  } finally {
    button.disabled = false;
  }
}

/* ---------- 初始化 ---------- */

function initApp() {
  $('preview-mentor').addEventListener('click', () => previewRole('mentor'));
  $('preview-student').addEventListener('click', () => previewRole('student'));
  $('confirm-btn').addEventListener('click', confirmEntry);
  $('expand-up').addEventListener('click', expandUp);
  $('expand-down').addEventListener('click', expandDown);
  $('reset-view').addEventListener('click', () => ensureCy().fit(undefined, 45));
  $('export-btn').addEventListener('click', exportPublic);
  bindSearch();
  bindDetailActions();
}

if (typeof cytoscape === 'undefined') {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js';
  script.onload = () => {
    if (typeof cytoscape !== 'undefined') initApp();
    else $('cy').innerHTML = '<p class="muted" style="padding:20px">图谱库加载失败，请检查网络连接。</p>';
  };
  script.onerror = () => {
    $('cy').innerHTML = '<p class="muted" style="padding:20px">图谱库加载失败，请检查网络连接。</p>';
  };
  document.head.appendChild(script);
} else {
  initApp();
}
