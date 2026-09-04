'use strict';

/* 公开静态图谱：只读 data/*.json，无后端 */

const state = {
  people: [],
  relationships: [],
  byId: new Map(),
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
      $('manifest-info').textContent =
        `更新于 ${manifest.generated_at.replace('T', ' ').slice(0, 16)} UTC · ` +
        `${manifest.people_count} 位学者 / ${manifest.relationship_count} 条关系`;
    }
    renderPersonList();
  } catch (error) {
    showErrorBanner(error.message);
  }
}

function renderPersonList() {
  const list = $('person-list');
  list.innerHTML = '';
  for (const person of state.people) {
    const item = document.createElement('li');
    item.className = 'result-item';
    item.innerHTML = `
      <span class="result-name">${escapeHtml(person.name)}</span>
      ${person.institution ? `<span class="result-meta">${escapeHtml(person.institution)}</span>` : ''}`;
    item.addEventListener('click', () => selectPerson(person.id));
    list.appendChild(item);
  }
  if (!state.people.length) {
    list.innerHTML = '<li class="muted">暂无公开数据（本地管理页导出后生成）</li>';
  }
}

/* ---------- 搜索 ---------- */

let searchTimer = null;

function runSearch() {
  const q = $('search-input').value.trim().toLowerCase();
  const list = $('search-results');
  if (!q) { list.innerHTML = ''; return; }
  const results = state.people.filter((person) => {
    const haystack = [
      person.name,
      person.name_en,
      person.institution,
      person.field,
      ...(person.aliases || []),
    ].filter(Boolean).join(' ').toLowerCase();
    return haystack.includes(q);
  }).slice(0, 50);

  list.innerHTML = '';
  if (!results.length) {
    list.innerHTML = '<li class="muted">没有匹配的学者</li>';
    return;
  }
  for (const person of results) {
    const item = document.createElement('li');
    item.className = 'result-item';
    item.innerHTML = `
      <span class="result-name">${escapeHtml(person.name)}</span>
      ${person.institution ? `<span class="result-meta">${escapeHtml(person.institution)}</span>` : ''}`;
    item.addEventListener('click', () => selectPerson(person.id));
    list.appendChild(item);
  }
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
  cy.on('tap', 'node', (event) => showPersonDetails(event.target.data()));
  cy.on('tap', 'edge', (event) => showRelationshipDetails(event.target.data()));
  return cy;
}

function selectPerson(personId) {
  state.centerId = personId;
  state.up = 3;
  state.down = 2;
  loadLineage(personId, state.up, state.down);
}

function loadLineage(personId, up, down) {
  const mentorOf = new Map();   // student_id -> [relationships]
  const studentsOf = new Map(); // mentor_id -> [relationships]
  for (const rel of state.relationships) {
    if (!mentorOf.has(rel.student_id)) mentorOf.set(rel.student_id, []);
    mentorOf.get(rel.student_id).push(rel);
    if (!studentsOf.has(rel.mentor_id)) studentsOf.set(rel.mentor_id, []);
    studentsOf.get(rel.mentor_id).push(rel);
  }

  const nodeIds = new Set([personId]);
  const edgeIds = new Set();

  // 向上：导师
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

  // 向下：学生
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
  renderGraph(nodes, edges);
  $('graph-info').textContent =
    `中心：${state.byId.get(personId)?.name || personId} · 向上 ${up} 代 · 向下 ${down} 代 · ` +
    `${nodes.length} 个节点 / ${edges.length} 条边`;
  const center = state.byId.get(personId);
  if (center) showPersonDetails(center);
}

function renderGraph(nodes, edges) {
  const cyGraph = ensureCy();
  const sourceIds = new Set(edges.map((e) => e.mentor_id));
  const elements = [
    ...nodes.map((n) => ({
      data: { id: n.id, label: n.name, type: sourceIds.has(n.id) ? 'mentor' : 'student', ...n },
      classes: n.id === state.centerId ? 'center' : '',
    })),
    ...edges.map((e) => ({ data: { id: e.id, source: e.mentor_id, target: e.student_id, ...e } })),
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

/* ---------- 详情 ---------- */

function showPersonDetails(person) {
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
    </dl>
    <div class="detail-actions">
      <button class="btn btn-small" data-action="expand-up">↑ 向上展开一代</button>
      <button class="btn btn-small" data-action="expand-down">↓ 向下展开一代</button>
      <button class="btn btn-small" data-action="reset-view">重置视图</button>
    </div>
  `;
}

function showRelationshipDetails(rel) {
  const mentor = state.byId.get(rel.mentor_id);
  const student = state.byId.get(rel.student_id);
  const years = [rel.start_year, rel.end_year].filter(Boolean).join(' – ');
  $('detail-title').textContent = `关系：${REL_TYPE_ZH[rel.relationship_type] || rel.relationship_type}`;
  $('detail-content').innerHTML = `
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

/* ---------- 投稿 ---------- */

const REL_TYPE_ZH_PUB = {
  phd: '博士导师', master: '硕士导师', postdoc: '博士后合作导师',
  informal: '非正式指导', other: '其他',
};

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
}

async function copyContribution() {
  try {
    await navigator.clipboard.writeText($('c-output').value);
    $('c-status').textContent = '已复制到剪贴板，去粘贴发送给管理员吧。';
  } catch (error) {
    $('c-output').select();
    $('c-status').textContent = '复制失败，请手动全选复制（已为你选中）。';
  }
}

function bindContribution() {
  const modal = $('contribute-modal');
  $('contribute-btn').addEventListener('click', () => { modal.hidden = false; });
  $('contribute-close').addEventListener('click', () => { modal.hidden = true; });
  $('c-generate').addEventListener('click', generateContribution);
  $('c-copy').addEventListener('click', copyContribution);
}

/* ---------- 初始化 ---------- */

function initApp() {
  $('search-input').addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(runSearch, 250);
  });
  $('expand-up').addEventListener('click', () => {
    if (state.up >= 10 || !state.centerId) return;
    state.up += 1;
    loadLineage(state.centerId, state.up, state.down);
  });
  $('expand-down').addEventListener('click', () => {
    if (state.down >= 10 || !state.centerId) return;
    state.down += 1;
    loadLineage(state.centerId, state.up, state.down);
  });
  $('reset-view').addEventListener('click', () => ensureCy().fit(undefined, 45));
  $('detail-content').addEventListener('click', (event) => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const action = button.dataset.action;
    if (action === 'expand-up') { state.up = Math.min(10, state.up + 1); loadLineage(state.centerId, state.up, state.down); }
    if (action === 'expand-down') { state.down = Math.min(10, state.down + 1); loadLineage(state.centerId, state.up, state.down); }
    if (action === 'reset-view') ensureCy().fit(undefined, 45);
  });
}

function start() {
  initApp();
  bindContribution();
  loadData();
  if (typeof cytoscape !== 'undefined') ensureCy();
}

if (typeof cytoscape === 'undefined') {
  const script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js';
  script.onload = () => { if (typeof cytoscape !== 'undefined') start(); };
  script.onerror = () => {
    $('cy').innerHTML = '<p class="muted" style="padding:20px">图谱库加载失败，请检查网络连接。</p>';
  };
  document.head.appendChild(script);
} else {
  start();
}
