'use strict';

/* 学术谱系本地管理：侧边栏多页面 */

const state = {
  previews: { mentor: null, student: null },
  graphMode: 'overview', // 'overview' | 'lineage'
  centerId: null,
  up: 3,
  down: 2,
  selectedId: null,
};

const detail = {
  person: null,
  personContainer: 'graph',
  mentorship: null,
  mentorshipContainer: 'graph',
};
let editingMode = null; // null | 'person' | 'relationship'

const REL_TYPE_ZH = {
  phd: '博士导师',
  master: '硕士导师',
  postdoc: '博士后合作导师',
  informal: '非正式指导',
  other: '其他',
};
const STATUS_ZH = { draft: '草稿', verified: '已确认', rejected: '已拒绝' };
const CONFIDENCE_ZH = { confirmed: 'confirmed 已确认', probable: 'probable 很可能', uncertain: 'uncertain 不确定' };

const PAGE_TITLES = {
  graph: '学术谱系总览',
  entry: '录入关系',
  scholars: '学者库',
  relationships: '关系库',
  export: '公开导出',
};

const DETAIL_CONTAINERS = {
  graph: { title: 'graph-detail-title', content: 'graph-detail-content' },
  scholar: { title: 'scholar-detail-title', content: 'scholar-detail-content' },
  relationship: { title: 'relationship-detail-title', content: 'relationship-detail-content' },
};

const GRAPH_DETAIL_HINT = '点击节点或边查看详情。<br>在筛选栏调整条件，图谱会实时更新。<br>点击节点后可用「以该学者为中心」查看上下游谱系。';
const SCHOLAR_DETAIL_HINT = '点击左侧学者查看详情，可编辑职称、机构、编委会任职、荣誉等。';
const RELATIONSHIP_DETAIL_HINT = '点击左侧关系查看详情，可编辑状态、年份、毕业去向、证据等。';

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
    error.body = body;
    throw error;
  }
  return body;
}

function setDetail(container, title, html) {
  const ids = DETAIL_CONTAINERS[container];
  $(ids.title).textContent = title;
  $(ids.content).innerHTML = html;
}

/* ================= 页面切换 ================= */

function switchPage(page) {
  document.querySelectorAll('.page').forEach((el) => {
    el.classList.toggle('active', el.id === `page-${page}`);
  });
  document.querySelectorAll('.nav-item').forEach((el) => {
    el.classList.toggle('active', el.dataset.page === page);
  });
  $('page-title').textContent = PAGE_TITLES[page] || '';
  if (page === 'graph') {
    if (state.graphMode === 'overview') loadNetwork();
    else if (state.centerId) loadLineage(state.centerId, state.up, state.down);
  }
  if (page === 'scholars') refreshScholarList();
  if (page === 'relationships') refreshRelationshipList();
}

/* ================= 统计与筛选选项 ================= */

async function refreshStats() {
  try {
    const data = await api('/api/stats');
    $('db-stats').textContent = `数据库：${data.persons} 位学者 / ${data.mentorships} 条关系`;
  } catch (error) {
    $('db-stats').textContent = '';
  }
}

function fillSelect(id, values, placeholder, labels = null) {
  const select = $(id);
  const current = select.value;
  select.innerHTML = '';
  const first = document.createElement('option');
  first.value = '';
  first.textContent = placeholder;
  select.appendChild(first);
  for (const value of values) {
    const option = document.createElement('option');
    option.value = String(value);
    option.textContent = labels && labels[value] ? labels[value] : String(value);
    select.appendChild(option);
  }
  if ([...select.options].some((option) => option.value === current)) {
    select.value = current;
  }
}

async function refreshFilterOptions() {
  try {
    const options = await api('/api/filters');
    const years = ['g-start-year', 'g-end-year', 's-start-year', 's-end-year'];
    fillSelect('g-institution', options.institutions, '全部机构');
    fillSelect('g-title', options.titles, '全部职称');
    fillSelect('g-honor', options.honors, '全部荣誉');
    fillSelect('g-type', options.relationship_types, '全部关系类型', REL_TYPE_ZH);
    fillSelect('s-institution', options.institutions, '全部机构');
    fillSelect('s-title', options.titles, '全部职称');
    fillSelect('r-type', options.relationship_types, '全部关系类型', REL_TYPE_ZH);
    fillSelect('r-status', ['draft', 'verified', 'rejected'], '全部状态', STATUS_ZH);
    fillSelect('g-start-year', options.start_years, '入学年份不限');
    fillSelect('g-end-year', options.end_years, '毕业年份不限');
    fillSelect('s-start-year', options.start_years, '入学年份不限');
    fillSelect('s-end-year', options.end_years, '毕业年份不限');
    void years;
  } catch (error) {
    /* 选项加载失败时保持现状 */
  }
}

/* ================= 图谱页 ================= */

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
          color: '#2b2623',
          'background-color': '#a9bcd4',
          width: 38,
          height: 38,
          'border-width': 1.5,
          'border-color': '#6f89ab',
          'text-wrap': 'wrap',
          'text-max-width': 96,
        },
      },
      {
        selector: 'node[type = "mentor"]',
        style: { 'background-color': '#d8a09b', 'border-color': '#b3362c' },
      },
      {
        selector: 'node.center',
        style: {
          width: 52,
          height: 52,
          'background-color': '#e6b93c',
          'border-color': '#b98a12',
          'border-width': 3,
          'font-size': 12,
        },
      },
      {
        selector: 'node.selected',
        style: {
          'border-width': 3,
          'border-color': '#b3362c',
          width: 48,
          height: 48,
        },
      },
      {
        selector: 'edge',
        style: {
          width: 1.8,
          'line-color': '#c6bcb4',
          'target-arrow-color': '#a99c92',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 1.05,
        },
      },
    ],
    layout: { name: 'preset' },
    wheelSensitivity: 0.25,
  });
  cy.on('tap', 'node', (event) => {
    const person = event.target.data();
    if (state.graphMode === 'overview') {
      state.selectedId = person.id;
      cy.elements().removeClass('selected');
      event.target.addClass('selected');
      renderPersonDetails(person, 'graph');
    } else {
      state.selectedId = person.id;
      loadLineage(person.id, 3, 2);
    }
  });
  cy.on('tap', 'edge', (event) => showMentorshipDetails(event.target.id(), 'graph'));
  window.__cy = cy;
  return cy;
}

function renderGraph(nodes, edges) {
  const cyGraph = ensureCy();
  const sourceIds = new Set(edges.map((e) => e.mentor_id));
  const elements = [
    ...nodes.map((n) => {
      const classes = [
        state.graphMode === 'lineage' && n.id === state.centerId ? 'center' : '',
        state.graphMode === 'overview' && n.id === state.selectedId ? 'selected' : '',
      ].join(' ').trim();
      return {
        data: { id: n.id, label: n.name, type: sourceIds.has(n.id) ? 'mentor' : 'student', ...n },
        classes,
      };
    }),
    ...edges.map((e) => ({
      data: { id: e.id, source: e.mentor_id, target: e.student_id, ...e },
    })),
  ];
  cyGraph.elements().remove();
  cyGraph.add(elements);
  const layout = state.graphMode === 'overview'
    ? { name: 'cose', padding: 45, animate: false, nodeRepulsion: 9000 }
    : { name: 'breadthfirst', directed: true, roots: `#${state.centerId}`, padding: 45, spacingFactor: 1.2 };
  cyGraph.layout(layout).run();
  cyGraph.fit(undefined, 55);
}

function graphFilterParams() {
  const params = new URLSearchParams();
  [
    ['g-institution', 'institution'],
    ['g-title', 'title'],
    ['g-honor', 'honor'],
    ['g-type', 'relationship_type'],
    ['g-start-year', 'start_year'],
    ['g-end-year', 'end_year'],
  ].forEach(([id, key]) => {
    const value = $(id).value;
    if (value) params.set(key, value);
  });
  if ($('g-public').checked) params.set('public', '1');
  return params;
}

async function loadNetwork() {
  try {
    const data = await api(`/api/network?${graphFilterParams()}`);
    state.graphMode = 'overview';
    renderGraph(data.nodes, data.edges);
    $('back-overview').hidden = true;
    $('graph-info').textContent = `总览：${data.nodes.length} 个节点 / ${data.edges.length} 条边 · 点击节点或边查看详情`;
    if (!state.selectedId || !data.nodes.some((n) => n.id === state.selectedId)) {
      state.selectedId = null;
      setDetail('graph', '详情', GRAPH_DETAIL_HINT);
    }
  } catch (error) {
    $('graph-info').textContent = `加载失败：${error.message}`;
  }
}

async function loadLineage(personId, up, down) {
  try {
    const data = await api(
      `/api/persons/${encodeURIComponent(personId)}/lineage?up=${up}&down=${down}`
    );
    state.graphMode = 'lineage';
    state.centerId = data.center_id;
    state.up = data.up;
    state.down = data.down;
    state.selectedId = data.center_id;
    renderGraph(data.nodes, data.edges);
    $('back-overview').hidden = false;
    const center = data.nodes.find((n) => n.id === data.center_id);
    $('graph-info').textContent =
      `以 ${center ? center.name : data.center_id} 为中心 · 向上 ${data.up} 代 · 向下 ${data.down} 代 · ` +
      `${data.nodes.length} 个节点 / ${data.edges.length} 条边`;
    if (center) renderPersonDetails(center, 'graph');
  } catch (error) {
    $('graph-info').textContent = `加载失败：${error.message}`;
  }
}

function centerOnPerson(personId) {
  switchPage('graph');
  loadLineage(personId, 3, 2);
}

function expandUp() {
  if (state.graphMode !== 'lineage' || state.up >= 10 || !state.centerId) return;
  state.up += 1;
  loadLineage(state.centerId, state.up, state.down);
}

function expandDown() {
  if (state.graphMode !== 'lineage' || state.down >= 10 || !state.centerId) return;
  state.down += 1;
  loadLineage(state.centerId, state.up, state.down);
}

function refreshGraphAfterChange() {
  if (state.graphMode === 'overview' || !state.centerId) loadNetwork();
  else loadLineage(state.centerId, state.up, state.down);
}

/* ================= 删除 ================= */

async function deletePerson() {
  const person = detail.person;
  if (!window.confirm(`确定删除学者「${person.name}」？\n与其相关的所有导师—学生关系将一并删除，此操作不可恢复。`)) return;
  try {
    const result = await api(`/api/persons/${encodeURIComponent(person.id)}`, { method: 'DELETE' });
    state.graphMode = 'overview';
    if (state.centerId === person.id) state.centerId = null;
    if (state.selectedId === person.id) state.selectedId = null;
    detail.person = null;
    editingMode = null;
    setDetail('graph', '详情', GRAPH_DETAIL_HINT);
    setDetail('scholar', '学者详情', SCHOLAR_DETAIL_HINT);
    refreshGraphAfterChange();
    refreshScholarList();
    refreshRelationshipList();
    refreshFilterOptions();
    refreshStats();
    // eslint-disable-next-line no-console
    console.log(`已删除学者，连带删除 ${result.relationships_removed} 条关系`);
  } catch (error) {
    setDetail(detail.personContainer, '删除失败', `<p class="status error">${escapeHtml(error.message)}</p>`);
  }
}

async function deleteRelationship() {
  const m = detail.mentorship;
  const label = `${m.student_name || '学生'} ← ${m.mentor_name || '导师'}（${REL_TYPE_ZH[m.relationship_type] || m.relationship_type}）`;
  if (!window.confirm(`确定删除关系「${label}」？此操作不可恢复。`)) return;
  try {
    await api(`/api/mentorships/${encodeURIComponent(m.id)}`, { method: 'DELETE' });
    detail.mentorship = null;
    editingMode = null;
    setDetail('graph', '详情', GRAPH_DETAIL_HINT);
    setDetail('relationship', '关系详情', RELATIONSHIP_DETAIL_HINT);
    refreshGraphAfterChange();
    refreshRelationshipList();
    refreshStats();
  } catch (error) {
    setDetail(detail.mentorshipContainer, '删除失败', `<p class="status error">${escapeHtml(error.message)}</p>`);
  }
}

/* ================= 学者详情与编辑 ================= */

function renderPersonDetails(person, container) {
  detail.person = person;
  detail.personContainer = container;
  const actions = `
    <div class="detail-actions">
      <button class="btn btn-primary btn-small" data-action="center-person">以该学者为中心</button>
      <button class="btn btn-small" data-action="edit-person">编辑学者信息</button>
      <button class="btn btn-danger btn-small" data-action="delete-person">删除学者</button>
      ${container === 'graph'
        ? `<button class="btn btn-small" data-action="expand-up">↑ 向上展开一代</button>
           <button class="btn btn-small" data-action="expand-down">↓ 向下展开一代</button>
           <button class="btn btn-small" data-action="reset-view">重置视图</button>`
        : ''}
    </div>`;
  setDetail(container, `学者：${person.name}`, `
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
    ${actions}
  `);
}

function renderPersonEditForm(person) {
  editingMode = 'person';
  setDetail(detail.personContainer, `编辑：${person.name}`, `
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
  `);
}

function splitLines(id) {
  return $(id).value.split('\n').map((s) => s.trim()).filter(Boolean);
}

async function savePersonEdit() {
  const personId = detail.person.id;
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
    editingMode = null;
    detail.person = updated.person;
    renderPersonDetails(updated.person, detail.personContainer);
    refreshGraphAfterChange();
    refreshScholarList();
    refreshFilterOptions();
  } catch (error) {
    setDetail(detail.personContainer, '编辑失败', `<p class="status error">保存失败：${escapeHtml(error.message)}</p>`);
  }
}

/* ================= 关系详情与编辑 ================= */

async function showMentorshipDetails(mentorshipId, container) {
  setDetail(container, '关系详情（加载中…）', '<p class="muted">正在加载…</p>');
  try {
    const data = await api(`/api/mentorships/${mentorshipId}`);
    renderMentorshipDetails(data.mentorship, container);
  } catch (error) {
    setDetail(container, '关系详情', `<p class="status error">加载失败：${escapeHtml(error.message)}</p>`);
  }
}

function renderMentorshipDetails(m, container) {
  detail.mentorship = m;
  detail.mentorshipContainer = container;
  const years = [m.start_year, m.end_year].filter(Boolean).join(' – ');
  setDetail(container, `关系：${REL_TYPE_ZH[m.relationship_type] || m.relationship_type}`, `
    <dl class="detail-list">
      <dt>导师</dt><dd>${escapeHtml(m.mentor_name || m.mentor_id)}</dd>
      <dt>学生</dt><dd>${escapeHtml(m.student_name || m.student_id)}</dd>
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
    <div class="detail-actions">
      <button class="btn btn-primary btn-small" data-action="edit-relationship">编辑关系</button>
      <button class="btn btn-danger btn-small" data-action="delete-relationship">删除关系</button>
    </div>
  `);
}

function renderRelationshipEditForm(m) {
  editingMode = 'relationship';
  detail.mentorship = m;
  const title = `编辑关系：${m.student_name || '学生'} ← ${m.mentor_name || '导师'}`;
  setDetail(detail.mentorshipContainer, title, `
    <div class="edit-form">
      <p class="muted">导师与学生固定；如需反向，请删除后在「录入关系」重新创建。</p>
      <label>状态
        <select id="edit-rel-status">
          <option value="draft" ${m.status === 'draft' ? 'selected' : ''}>草稿</option>
          <option value="verified" ${m.status === 'verified' ? 'selected' : ''}>已确认</option>
          <option value="rejected" ${m.status === 'rejected' ? 'selected' : ''}>已拒绝</option>
        </select>
      </label>
      <label>可信度
        <select id="edit-rel-confidence">
          <option value="confirmed" ${m.confidence === 'confirmed' ? 'selected' : ''}>confirmed 已确认</option>
          <option value="probable" ${m.confidence === 'probable' ? 'selected' : ''}>probable 很可能</option>
          <option value="uncertain" ${m.confidence === 'uncertain' ? 'selected' : ''}>uncertain 不确定</option>
        </select>
      </label>
      <label>入学年份 <input id="edit-rel-start" type="number" min="1900" max="2100" value="${escapeHtml(m.start_year)}"></label>
      <label>毕业年份 <input id="edit-rel-end" type="number" min="1900" max="2100" value="${escapeHtml(m.end_year)}"></label>
      <label>机构 <input id="edit-rel-institution" type="text" value="${escapeHtml(m.institution)}"></label>
      <label>学生毕业去向 <input id="edit-rel-placement" type="text" value="${escapeHtml(m.student_placement)}"></label>
      <label>证据 URL <input id="edit-rel-evidence" type="url" value="${escapeHtml(m.evidence_url)}"></label>
      <label>证据说明 <input id="edit-rel-evidence-text" type="text" value="${escapeHtml(m.evidence_text)}"></label>
      <label class="checkbox-row"><input id="edit-rel-public" type="checkbox" ${m.public ? 'checked' : ''}> 公开</label>
      <label>私有备注 <input id="edit-rel-notes" type="text" value="${escapeHtml(m.notes_private)}"></label>
      <div class="detail-actions">
        <button class="btn btn-primary btn-small" data-action="save-relationship">保存</button>
        <button class="btn btn-small" data-action="cancel-edit">取消</button>
      </div>
    </div>
  `);
}

async function saveRelationshipEdit() {
  const mentorshipId = detail.mentorship.id;
  try {
    const updated = await api(`/api/mentorships/${mentorshipId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status: $('edit-rel-status').value,
        confidence: $('edit-rel-confidence').value,
        start_year: $('edit-rel-start').value ? parseInt($('edit-rel-start').value, 10) : null,
        end_year: $('edit-rel-end').value ? parseInt($('edit-rel-end').value, 10) : null,
        institution: $('edit-rel-institution').value.trim(),
        student_placement: $('edit-rel-placement').value.trim(),
        evidence_url: $('edit-rel-evidence').value.trim(),
        evidence_text: $('edit-rel-evidence-text').value.trim(),
        public: $('edit-rel-public').checked,
        notes_private: $('edit-rel-notes').value.trim(),
      }),
    });
    editingMode = null;
    detail.mentorship = updated.mentorship;
    renderMentorshipDetails(updated.mentorship, detail.mentorshipContainer);
    refreshGraphAfterChange();
    refreshRelationshipList();
  } catch (error) {
    setDetail(detail.mentorshipContainer, '编辑失败', `<p class="status error">保存失败：${escapeHtml(error.message)}</p>`);
  }
}

/* ================= 录入页 ================= */

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
  $(`${role}-name`).addEventListener('input', () => { updateSentence(); updateConfirmEnabled(); });
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

function entryFormValues() {
  return {
    status: $('rel-status').value,
    confidence: $('confidence').value,
    start_year: $('start-year').value ? parseInt($('start-year').value, 10) : null,
    end_year: $('end-year').value ? parseInt($('end-year').value, 10) : null,
    institution: $('rel-institution').value.trim(),
    student_placement: $('student-placement').value.trim(),
    evidence_url: $('evidence-url').value.trim(),
    evidence_text: $('evidence-text').value.trim(),
    notes_private: $('notes-private').value.trim(),
    public: $('public-flag').checked,
  };
}

const MERGE_KEYS = ['status', 'confidence', 'start_year', 'end_year', 'institution',
  'student_placement', 'evidence_url', 'evidence_text', 'notes_private'];

function mergeMentorship(existing, form) {
  const merged = { ...existing };
  for (const key of MERGE_KEYS) {
    const value = form[key];
    if (value !== null && value !== undefined && value !== '') merged[key] = value;
  }
  merged.public = form.public ? true : existing.public;
  return merged;
}

async function confirmEntry() {
  const mentorName = currentName('mentor');
  const studentName = currentName('student');
  if (!mentorName || !studentName || !state.previews.mentor || !state.previews.student) return;

  const publicFlag = $('public-flag').checked;
  const payload = {
    relationship_type: $('relationship-type').value,
    ...entryFormValues(),
    evidence_url: $('evidence-url').value.trim() || state.previews.student.normalized_url,
    public: publicFlag,
  };
  if (!payload.start_year) delete payload.start_year;
  if (!payload.end_year) delete payload.end_year;

  const confirmBtn = $('confirm-btn');
  confirmBtn.disabled = true;
  setEntryStatus('正在保存…');
  let studentPerson = null;
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
    studentPerson = student.person;
    await api('/api/mentorships', {
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
    refreshStats();
    refreshFilterOptions();
    refreshScholarList();
    refreshRelationshipList();
  } catch (error) {
    if (error.status === 409 && error.body && error.body.existing) {
      const merged = mergeMentorship(error.body.existing, entryFormValues());
      setEntryStatus('关系已存在（同导师 + 同学生 + 同类型），未重复创建。已打开编辑表单，并自动填入你本次新填的内容，核对后保存即可更新。');
      if (studentPerson) {
        await loadLineage(studentPerson.id, 1, 0);
      }
      switchPage('relationships');
      renderRelationshipEditForm(merged);
    } else if (error.status === 409) {
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

/* ================= 学者库页 ================= */

let scholarTimer = null;

function scholarParams() {
  const params = new URLSearchParams({ limit: '100' });
  const q = $('s-search').value.trim();
  if (q) params.set('q', q);
  [
    ['s-institution', 'institution'],
    ['s-title', 'title'],
    ['s-start-year', 'start_year'],
    ['s-end-year', 'end_year'],
  ].forEach(([id, key]) => {
    const value = $(id).value;
    if (value) params.set(key, value);
  });
  return params;
}

async function refreshScholarList() {
  try {
    const data = await api(`/api/persons?${scholarParams()}`);
    const list = $('person-list');
    list.innerHTML = '';
    if (!data.persons.length) {
      list.innerHTML = '<li class="muted" style="padding:12px">没有符合条件的学者，试试调整筛选</li>';
      return;
    }
    for (const person of data.persons) {
      const item = document.createElement('li');
      const selected = detail.person && detail.person.id === person.id && detail.personContainer === 'scholar';
      item.className = 'list-item' + (selected ? ' selected' : '');
      item.innerHTML = `
        <div class="li-main">
          <div class="li-title">${escapeHtml(person.name)}</div>
          <div class="li-meta">${escapeHtml([person.title, person.institution].filter(Boolean).join(' · ')) || '—'}</div>
        </div>
        ${person.honors && person.honors.length ? `<span class="badge badge-ok">${escapeHtml(person.honors[0])}</span>` : ''}
        ${person.public ? '<span class="badge badge-verified">公开</span>' : '<span class="badge badge-priv">私有</span>'}`;
      item.addEventListener('click', () => {
        document.querySelectorAll('#person-list .list-item').forEach((el) => el.classList.remove('selected'));
        item.classList.add('selected');
        renderPersonDetails(person, 'scholar');
      });
      list.appendChild(item);
    }
  } catch (error) {
    $('person-list').innerHTML = `<li class="status error">${escapeHtml(error.message)}</li>`;
  }
}

/* ================= 关系库页 ================= */

let relationshipTimer = null;

function relationshipParams() {
  const params = new URLSearchParams();
  const q = $('r-q').value.trim();
  if (q) params.set('q', q);
  if ($('r-status').value) params.set('status', $('r-status').value);
  if ($('r-type').value) params.set('relationship_type', $('r-type').value);
  return params;
}

async function refreshRelationshipList() {
  try {
    const data = await api(`/api/mentorships?${relationshipParams()}`);
    const list = $('relationship-list');
    list.innerHTML = '';
    if (!data.mentorships.length) {
      list.innerHTML = '<li class="muted" style="padding:12px">没有符合条件的关系</li>';
      return;
    }
    for (const m of data.mentorships) {
      const item = document.createElement('li');
      const selected = detail.mentorship && detail.mentorship.id === m.id && detail.mentorshipContainer === 'relationship';
      item.className = 'list-item' + (selected ? ' selected' : '');
      const years = [m.start_year, m.end_year].filter(Boolean).join(' – ');
      item.innerHTML = `
        <div class="li-main">
          <div class="li-title">${escapeHtml(m.student_name)} ← ${escapeHtml(m.mentor_name)}</div>
          <div class="li-meta">${escapeHtml([REL_TYPE_ZH[m.relationship_type] || m.relationship_type, years].filter(Boolean).join(' · ')) || '—'}</div>
        </div>
        <span class="badge badge-${m.status}">${STATUS_ZH[m.status] || m.status}</span>
        ${m.public ? '<span class="badge badge-verified">公开</span>' : '<span class="badge badge-priv">私有</span>'}`;
      item.addEventListener('click', () => {
        document.querySelectorAll('#relationship-list .list-item').forEach((el) => el.classList.remove('selected'));
        item.classList.add('selected');
        renderMentorshipDetails(m, 'relationship');
      });
      list.appendChild(item);
    }
  } catch (error) {
    $('relationship-list').innerHTML = `<li class="status error">${escapeHtml(error.message)}</li>`;
  }
}

/* ================= 导出页 ================= */

async function exportPublic() {
  const button = $('export-btn');
  const status = $('export-status');
  button.disabled = true;
  status.textContent = '导出中…';
  status.className = 'status';
  try {
    const result = await api('/api/export/public', { method: 'POST' });
    status.textContent = `已导出：${result.people} 位学者 / ${result.relationships} 条关系 → public/data/`;
    status.className = 'status ok';
  } catch (error) {
    status.textContent = `导出失败：${error.message}`;
    status.className = 'status error';
  } finally {
    button.disabled = false;
  }
}

/* ================= 事件绑定 ================= */

function bindNav() {
  document.querySelectorAll('.nav-item').forEach((button) => {
    button.addEventListener('click', () => switchPage(button.dataset.page));
  });
}

function bindEntry() {
  $('preview-mentor').addEventListener('click', () => previewRole('mentor'));
  $('preview-student').addEventListener('click', () => previewRole('student'));
  $('confirm-btn').addEventListener('click', confirmEntry);
}

function bindGraphControls() {
  ['g-institution', 'g-title', 'g-honor', 'g-type', 'g-start-year', 'g-end-year'].forEach((id) => {
    $(id).addEventListener('change', loadNetwork);
  });
  $('g-public').addEventListener('change', loadNetwork);
  $('g-clear').addEventListener('click', () => {
    ['g-institution', 'g-title', 'g-honor', 'g-type', 'g-start-year', 'g-end-year'].forEach((id) => { $(id).value = ''; });
    $('g-public').checked = false;
    loadNetwork();
  });
  $('back-overview').addEventListener('click', () => {
    state.selectedId = state.centerId;
    loadNetwork();
  });
  $('expand-up').addEventListener('click', expandUp);
  $('expand-down').addEventListener('click', expandDown);
  $('reset-view').addEventListener('click', () => ensureCy().fit(undefined, 55));
}

function bindScholarControls() {
  $('s-search').addEventListener('input', () => {
    clearTimeout(scholarTimer);
    scholarTimer = setTimeout(refreshScholarList, 250);
  });
  ['s-institution', 's-title', 's-start-year', 's-end-year'].forEach((id) => {
    $(id).addEventListener('change', refreshScholarList);
  });
  $('s-clear').addEventListener('click', () => {
    $('s-search').value = '';
    ['s-institution', 's-title', 's-start-year', 's-end-year'].forEach((id) => { $(id).value = ''; });
    refreshScholarList();
  });
}

function bindRelationshipControls() {
  $('r-q').addEventListener('input', () => {
    clearTimeout(relationshipTimer);
    relationshipTimer = setTimeout(refreshRelationshipList, 250);
  });
  $('r-status').addEventListener('change', refreshRelationshipList);
  $('r-type').addEventListener('change', refreshRelationshipList);
  $('r-clear').addEventListener('click', () => {
    $('r-q').value = '';
    $('r-status').value = '';
    $('r-type').value = '';
    refreshRelationshipList();
  });
}

function bindDetailActions() {
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'center-person' && detail.person) centerOnPerson(detail.person.id);
    if (action === 'edit-person' && detail.person) renderPersonEditForm(detail.person);
    if (action === 'save-person') savePersonEdit();
    if (action === 'edit-relationship' && detail.mentorship) renderRelationshipEditForm(detail.mentorship);
    if (action === 'save-relationship') saveRelationshipEdit();
    if (action === 'delete-person' && detail.person) deletePerson();
    if (action === 'delete-relationship' && detail.mentorship) deleteRelationship();
    if (action === 'cancel-edit') {
      editingMode = null;
      if (detail.mentorship) renderMentorshipDetails(detail.mentorship, detail.mentorshipContainer);
      else if (detail.person) renderPersonDetails(detail.person, detail.personContainer);
    }
    if (action === 'expand-up') expandUp();
    if (action === 'expand-down') expandDown();
    if (action === 'reset-view') ensureCy().fit(undefined, 55);
  });
}

function initApp() {
  bindNav();
  bindEntry();
  bindGraphControls();
  bindScholarControls();
  bindRelationshipControls();
  bindDetailActions();
  $('export-btn').addEventListener('click', exportPublic);
  refreshStats();
  refreshFilterOptions();
  loadNetwork();
  refreshScholarList();
  refreshRelationshipList();
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

