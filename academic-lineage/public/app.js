'use strict';

/* 公开静态图谱：只读 data/*.json，无后端。结构与本地管理页保持一致。 */

const state = {
  people: [],
  relationships: [],
  byId: new Map(),
  graphMode: 'overview', // 'overview' | 'lineage'
  centerId: null,
  up: 3,
  down: 2,
  selectedId: null,
};

const REL_TYPE_ZH = {
  phd: '博士导师',
  master: '硕士导师',
  postdoc: '博士后合作导师',
  informal: '非正式指导',
  other: '其他',
};

const PAGE_TITLES = { graph: '学术谱系总览', scholars: '学者库', contribute: '投稿关系' };

const GRAPH_DETAIL_HINT = '点击节点或边查看详情。<br>在筛选栏调整条件，图谱会实时更新。<br>点击节点后可用「以该学者为中心」查看上下游谱系。';
const SCHOLAR_DETAIL_HINT = '点击左侧学者查看详情。';

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function showErrorBanner(message) {
  const banner = document.createElement('div');
  banner.className = 'error-banner';
  banner.innerHTML = `
    <strong>数据加载失败：</strong>${escapeHtml(message)}<br>
    请不要直接以 <code>file://</code> 方式打开本页面。请通过静态服务器（如
    <code>python -m http.server 4173 --directory public</code>）访问，或部署到 GitHub Pages。
  `;
  document.body.prepend(banner);
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
}

/* ================= 数据加载 ================= */

async function loadData() {
  try {
    const [people, relationships, manifest] = await Promise.all([
      fetch('data/people.json').then((res) => {
        if (!res.ok) throw new Error(`people.json ${res.status}`);
        return res.json();
      }),
      fetch('data/relationships.json').then((res) => {
        if (!res.ok) throw new Error(`relationships.json ${res.status}`);
        return res.json();
      }),
      fetch('data/manifest.json').then((res) => (res.ok ? res.json() : null)).catch(() => null),
    ]);
    state.people = people;
    state.relationships = relationships;
    state.byId = new Map(people.map((p) => [p.id, p]));
    if (manifest) {
      $('pub-stats').textContent =
        `更新于 ${manifest.generated_at.replace('T', ' ').slice(0, 16)} UTC · ` +
        `${manifest.people_count} 位学者 / ${manifest.relationship_count} 条关系`;
    }
    populateFilterOptions();
    loadNetwork();
    refreshScholarList();
  } catch (error) {
    showErrorBanner(error.message);
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

function distinct(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

function populateFilterOptions() {
  const institutions = distinct(state.people.map((p) => p.institution));
  const titles = distinct(state.people.map((p) => p.title));
  const honors = distinct(state.people.flatMap((p) => p.honors || []));
  const types = distinct(state.relationships.map((r) => r.relationship_type));
  fillSelect('g-institution', institutions, '全部机构');
  fillSelect('g-title', titles, '全部职称');
  fillSelect('g-honor', honors, '全部荣誉');
  fillSelect('g-type', types, '全部关系类型', REL_TYPE_ZH);
  fillSelect('s-institution', institutions, '全部机构');
  fillSelect('s-title', titles, '全部职称');
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
  cy.on('tap', 'edge', (event) => {
    const rel = state.relationships.find((r) => r.id === event.target.id());
    if (rel) renderRelationshipDetails(rel);
  });
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
    ...edges.map((e) => ({ data: { id: e.id, source: e.mentor_id, target: e.student_id, ...e } })),
  ];
  cyGraph.elements().remove();
  cyGraph.add(elements);
  const layout = state.graphMode === 'overview'
    ? { name: 'cose', padding: 45, animate: false, nodeRepulsion: 9000 }
    : { name: 'breadthfirst', directed: true, roots: `#${state.centerId}`, padding: 45, spacingFactor: 1.2 };
  cyGraph.layout(layout).run();
  cyGraph.fit(undefined, 55);
}

function graphFilteredData() {
  const institution = $('g-institution').value;
  const title = $('g-title').value;
  const honor = $('g-honor').value;
  const type = $('g-type').value;
  const nodes = state.people.filter((p) =>
    (!institution || p.institution === institution) &&
    (!title || p.title === title) &&
    (!honor || (p.honors || []).includes(honor))
  );
  const nodeIds = new Set(nodes.map((n) => n.id));
  const edges = state.relationships.filter((r) =>
    (!type || r.relationship_type === type) &&
    nodeIds.has(r.mentor_id) && nodeIds.has(r.student_id)
  );
  return { nodes, edges };
}

function loadNetwork() {
  const { nodes, edges } = graphFilteredData();
  state.graphMode = 'overview';
  renderGraph(nodes, edges);
  $('back-overview').hidden = true;
  $('graph-info').textContent = `总览：${nodes.length} 个节点 / ${edges.length} 条边 · 点击节点或边查看详情`;
  if (!state.selectedId || !nodes.some((n) => n.id === state.selectedId)) {
    state.selectedId = null;
    $('graph-detail-title').textContent = '详情';
    $('graph-detail-content').innerHTML = GRAPH_DETAIL_HINT;
  }
}

function loadLineage(personId, up, down) {
  const mentorOf = new Map();
  const studentsOf = new Map();
  for (const rel of state.relationships) {
    if (!mentorOf.has(rel.student_id)) mentorOf.set(rel.student_id, []);
    mentorOf.get(rel.student_id).push(rel);
    if (!studentsOf.has(rel.mentor_id)) studentsOf.set(rel.mentor_id, []);
    studentsOf.get(rel.mentor_id).push(rel);
  }

  const nodeIds = new Set([personId]);
  const edgeIds = new Set();

  let frontier = new Set([personId]);
  for (let i = 0; i < up; i += 1) {
    const next = new Set();
    for (const id of frontier) {
      for (const rel of mentorOf.get(id) || []) {
        edgeIds.add(rel.id);
        if (!nodeIds.has(rel.mentor_id)) next.add(rel.mentor_id);
      }
    }
    frontier = next;
    next.forEach((id) => nodeIds.add(id));
    if (!frontier.size) break;
  }

  frontier = new Set([personId]);
  for (let i = 0; i < down; i += 1) {
    const next = new Set();
    for (const id of frontier) {
      for (const rel of studentsOf.get(id) || []) {
        edgeIds.add(rel.id);
        if (!nodeIds.has(rel.student_id)) next.add(rel.student_id);
      }
    }
    frontier = next;
    next.forEach((id) => nodeIds.add(id));
    if (!frontier.size) break;
  }

  const nodes = [...nodeIds].map((id) => state.byId.get(id)).filter(Boolean);
  const edges = [...edgeIds].map((id) => state.relationships.find((r) => r.id === id)).filter(Boolean);
  state.graphMode = 'lineage';
  state.centerId = personId;
  state.up = up;
  state.down = down;
  state.selectedId = personId;
  renderGraph(nodes, edges);
  $('back-overview').hidden = false;
  const center = state.byId.get(personId);
  $('graph-info').textContent =
    `以 ${center ? center.name : personId} 为中心 · 向上 ${up} 代 · 向下 ${down} 代 · ` +
    `${nodes.length} 个节点 / ${edges.length} 条边`;
  if (center) renderPersonDetails(center, 'graph');
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

/* ================= 详情 ================= */

const DETAIL_IDS = {
  graph: { title: 'graph-detail-title', content: 'graph-detail-content' },
  scholar: { title: 'scholar-detail-title', content: 'scholar-detail-content' },
};

function setDetail(container, title, html) {
  const ids = DETAIL_IDS[container];
  $(ids.title).textContent = title;
  $(ids.content).innerHTML = html;
}

function renderPersonDetails(person, container) {
  const actions = `
    <div class="detail-actions">
      <button class="btn btn-primary btn-small" data-action="center-person">以该学者为中心</button>
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
    </dl>
    ${actions}
  `);
}

function renderRelationshipDetails(rel) {
  const mentor = state.byId.get(rel.mentor_id);
  const student = state.byId.get(rel.student_id);
  const years = [rel.start_year, rel.end_year].filter(Boolean).join(' – ');
  $('graph-detail-title').textContent = `关系：${REL_TYPE_ZH[rel.relationship_type] || rel.relationship_type}`;
  $('graph-detail-content').innerHTML = `
    <dl class="detail-list">
      <dt>导师</dt><dd>${escapeHtml(mentor?.name || rel.mentor_id)}</dd>
      <dt>学生</dt><dd>${escapeHtml(student?.name || rel.student_id)}</dd>
      <dt>类型</dt><dd>${REL_TYPE_ZH[rel.relationship_type] || rel.relationship_type}</dd>
      <dt>年份</dt><dd>${years || '未填写'}</dd>
      ${rel.institution ? `<dt>机构</dt><dd>${escapeHtml(rel.institution)}</dd>` : ''}
      ${rel.student_placement ? `<dt>学生毕业去向</dt><dd>${escapeHtml(rel.student_placement)}</dd>` : ''}
      <dt>可信度</dt><dd>${escapeHtml(rel.confidence)}</dd>
      <dt>证据</dt><dd><a href="${escapeHtml(rel.evidence_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(rel.evidence_url)}</a></dd>
      ${rel.evidence_text ? `<dt>证据说明</dt><dd>${escapeHtml(rel.evidence_text)}</dd>` : ''}
    </dl>
  `;
}

/* ================= 学者库页 ================= */

let scholarTimer = null;

function refreshScholarList() {
  const q = $('s-search').value.trim().toLowerCase();
  const institution = $('s-institution').value;
  const title = $('s-title').value;
  const results = state.people.filter((person) => {
    const haystack = [
      person.name,
      person.name_en,
      person.institution,
      person.field,
      ...(person.aliases || []),
    ].filter(Boolean).join(' ').toLowerCase();
    return (!q || haystack.includes(q)) &&
      (!institution || person.institution === institution) &&
      (!title || person.title === title);
  });

  const list = $('person-list');
  list.innerHTML = '';
  if (!results.length) {
    list.innerHTML = state.people.length
      ? '<li class="muted" style="padding:12px">没有符合条件的学者，试试调整筛选</li>'
      : '<li class="muted" style="padding:12px">暂无公开数据（本地管理页导出后生成）</li>';
    return;
  }
  for (const person of results) {
    const item = document.createElement('li');
    item.className = 'list-item';
    item.innerHTML = `
      <div class="li-main">
        <div class="li-title">${escapeHtml(person.name)}</div>
        <div class="li-meta">${escapeHtml([person.title, person.institution].filter(Boolean).join(' · ')) || '—'}</div>
      </div>
      ${person.honors && person.honors.length ? `<span class="badge badge-ok">${escapeHtml(person.honors[0])}</span>` : ''}`;
    item.addEventListener('click', () => {
      document.querySelectorAll('#person-list .list-item').forEach((el) => el.classList.remove('selected'));
      item.classList.add('selected');
      renderPersonDetails(person, 'scholar');
    });
    list.appendChild(item);
  }
}

/* ================= 投稿页 ================= */

function generateContribution() {
  const required = [
    ['c-mentor-name', '导师姓名'],
    ['c-mentor-url', '导师主页 URL'],
    ['c-student-name', '学生姓名'],
    ['c-student-url', '学生主页 URL'],
  ];
  for (const [id, label] of required) {
    if (!$(id).value.trim()) {
      $('c-status').textContent = `请填写${label}`;
      $('c-status').className = 'status error';
      return;
    }
  }
  const payload = {
    mentor: {
      name: $('c-mentor-name').value.trim(),
      homepage_url: $('c-mentor-url').value.trim(),
      title: $('c-mentor-title').value.trim() || null,
    },
    student: {
      name: $('c-student-name').value.trim(),
      homepage_url: $('c-student-url').value.trim(),
      title: $('c-student-title').value.trim() || null,
    },
    relationship: {
      relationship_type: $('c-type').value,
      confidence: $('c-confidence').value,
      start_year: $('c-start').value ? parseInt($('c-start').value, 10) : null,
      end_year: $('c-end').value ? parseInt($('c-end').value, 10) : null,
      institution: $('c-institution').value.trim() || null,
      evidence_url: $('c-evidence').value.trim() || $('c-student-url').value.trim(),
      evidence_text: $('c-evidence-text').value.trim() || null,
    },
  };
  const envelope = {
    payload,
    submitter_note: $('c-note').value.trim() || null,
    submitted_at: new Date().toISOString(),
  };
  $('c-output').value = JSON.stringify(envelope, null, 2);
  $('c-copy').disabled = false;
  $('c-status').textContent = '已生成。复制后发送给管理员（微信 / 邮件等）。';
  $('c-status').className = 'status ok';
}

async function copyContribution() {
  try {
    await navigator.clipboard.writeText($('c-output').value);
    $('c-status').textContent = '已复制到剪贴板，去粘贴发送给管理员吧。';
    $('c-status').className = 'status ok';
  } catch (error) {
    $('c-output').select();
    $('c-status').textContent = '复制失败，请手动全选复制（已为你选中）。';
    $('c-status').className = 'status error';
  }
}

/* ================= 事件绑定 ================= */

function bindNav() {
  document.querySelectorAll('.nav-item').forEach((button) => {
    button.addEventListener('click', () => switchPage(button.dataset.page));
  });
}

function bindGraphControls() {
  ['g-institution', 'g-title', 'g-honor', 'g-type'].forEach((id) => {
    $(id).addEventListener('change', loadNetwork);
  });
  $('g-clear').addEventListener('click', () => {
    ['g-institution', 'g-title', 'g-honor', 'g-type'].forEach((id) => { $(id).value = ''; });
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
  $('s-institution').addEventListener('change', refreshScholarList);
  $('s-title').addEventListener('change', refreshScholarList);
  $('s-clear').addEventListener('click', () => {
    $('s-search').value = '';
    $('s-institution').value = '';
    $('s-title').value = '';
    refreshScholarList();
  });
}

function bindContributeControls() {
  $('c-generate').addEventListener('click', generateContribution);
  $('c-copy').addEventListener('click', copyContribution);
}

function bindDetailActions() {
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'center-person') centerOnPerson(state.selectedId || state.centerId);
    if (action === 'expand-up') expandUp();
    if (action === 'expand-down') expandDown();
    if (action === 'reset-view') ensureCy().fit(undefined, 55);
  });
}

/* ================= 初始化 ================= */

function initApp() {
  bindNav();
  bindGraphControls();
  bindScholarControls();
  bindContributeControls();
  bindDetailActions();
  loadData();
}

if (typeof cytoscape === 'undefined') {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js';
  script.onload = () => { if (typeof cytoscape !== 'undefined') initApp(); };
  script.onerror = () => {
    $('cy').innerHTML = '<p class="muted" style="padding:20px">图谱库加载失败，请检查网络连接。</p>';
  };
  document.head.appendChild(script);
} else {
  initApp();
}

