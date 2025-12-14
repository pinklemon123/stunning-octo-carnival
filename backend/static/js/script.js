let cy = null;
let selectedNodeId = null;
let currentMinConfidence = null;

document.addEventListener('DOMContentLoaded', () => {
  initCytoscape();
  wireUi();
  refreshGraph();
});

function wireUi() {
  window.addEventListener('resize', () => {
    if (cy) {
      cy.resize();
    }
  });

  const urlParams = new URLSearchParams(window.location.search);
  const sourceParam = urlParams.get('source');
  if (sourceParam) {
    const sel = document.getElementById('source-filter');
    if (sel) sel.value = sourceParam;
  }

  const gSearch = document.getElementById('global-search');
  if (gSearch) {
    gSearch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') localSearch(gSearch.value.trim());
    });
  }

  const sInput = document.getElementById('search-input');
  if (sInput) {
    sInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') localSearch(sInput.value.trim());
    });
  }

  const minConf = document.getElementById('min-conf');
  if (minConf) {
    minConf.addEventListener('change', () => {
      const v = minConf.value;
      if (v === '') {
        currentMinConfidence = null;
      } else {
        const n = Number(v);
        currentMinConfidence = Number.isFinite(n) ? n : null;
      }
      refreshGraph();
    });
  }

  const srcSel = document.getElementById('source-filter');
  if (srcSel) {
    srcSel.addEventListener('change', () => refreshGraph());
  }

  const dropZone = document.getElementById('drop-zone');
  const showDrop = () => { if (dropZone) dropZone.classList.add('active'); };
  const hideDrop = () => { if (dropZone) dropZone.classList.remove('active'); };
  ['dragenter', 'dragover'].forEach((evt) => {
    document.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      showDrop();
    });
  });
  ['dragleave', 'drop'].forEach((evt) => {
    document.addEventListener(evt, (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (evt === 'drop') {
        const files = e.dataTransfer && e.dataTransfer.files;
        if (files && files.length) uploadFiles(files);
      }
      hideDrop();
    });
  });
}

function initCytoscape() {
  const container = document.getElementById('cy');
  cy = cytoscape({
    container,
    style: [
      {
        selector: 'node',
        style: {
          'shape': 'round-rectangle',
          'background-color': 'data(color)',
          'background-opacity': 0.95,
          'label': 'data(label)',
          'color': '#f8fafc',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '12px',
          'text-wrap': 'wrap',
          'text-max-width': '140px',
          'text-outline-width': 2,
          'text-outline-color': '#0b1220',
          'width': 'label',
          'height': 'label',
          'padding': '12px',
          'corner-radius': 8,
          'border-width': 1,
          'border-color': '#1e293b'
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#334155',
          'target-arrow-color': '#334155',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '10px',
          'text-rotation': 'autorotate',
          'color': '#94a3b8',
          'text-background-color': '#0b1220',
          'text-background-opacity': 0.55,
          'text-background-padding': '2px'
        }
      },
      { selector: ':selected', style: { 'background-color': '#22d3ee', 'line-color': '#22d3ee', 'target-arrow-color': '#22d3ee' } },
      { selector: '.cy-highlight', style: { 'background-color': '#f59e0b', 'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b' } },
      { selector: '.cy-path', style: { 'background-color': '#22c55e', 'line-color': '#22c55e', 'target-arrow-color': '#22c55e' } },
      { selector: '.cy-neighbor', style: { 'background-color': '#a78bfa', 'line-color': '#a78bfa', 'target-arrow-color': '#a78bfa' } },
    ],
    layout: { name: 'cose', animate: true, padding: 50 }
  });

  cy.on('tap', 'node', (evt) => {
    const node = evt.target;
    selectedNodeId = node.id();
    openDetailPanel(node);
  });

  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      selectedNodeId = null;
    }
  });
}

function clearGraph() {
  if (!cy) return;
  cy.elements().remove();
  selectedNodeId = null;
  closeDetailPanel();
}

function fitGraph() {
  if (!cy) return;
  if (cy.elements().length) cy.fit(cy.elements(), 60);
}

function zoomIn() {
  if (!cy) return;
  cy.zoom({ level: cy.zoom() * 1.2, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
}

function zoomOut() {
  if (!cy) return;
  cy.zoom({ level: cy.zoom() / 1.2, renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 } });
}

function applyLayout(name) {
  if (!cy) return;
  const useFcose = name === 'fcose' && typeof cytoscape('core', 'fcose') === 'function';
  const use = useFcose ? 'fcose' : (name || 'cose');
  const common = {
    name: use,
    animate: true,
    animationDuration: 650,
    fit: true,
    padding: 60
  };
  const options = use === 'fcose'
    ? {
      ...common,
      quality: 'default',
      randomize: true,
      nodeRepulsion: 8000,
      idealEdgeLength: 120,
      edgeElasticity: 0.2,
      gravity: 0.25
    }
    : {
      ...common,
      randomize: true
    };
  cy.layout(options).run();
}

function refreshGraph() {
  fetchGraph();
}

async function fetchGraph() {
  showLoading(true);
  try {
    const params = new URLSearchParams();
    const seedId = (document.getElementById('seed-id')?.value || '').trim();
    const depthRaw = (document.getElementById('depth')?.value || '1').trim();
    const depth = Math.max(1, Math.min(4, Number(depthRaw) || 1));
    const source = document.getElementById('source-filter')?.value || '';

    if (seedId) params.set('seed_id', seedId);
    params.set('depth', String(depth));
    if (source) params.set('source', source);
    if (currentMinConfidence !== null) params.set('min_confidence', String(currentMinConfidence));

    const res = await fetch(`/api/graph?${params.toString()}`);
    const data = await res.json();

    cy.elements().remove();

    const nodes = (data.nodes || []).map((n) => {
      const dn = n.data || {};
      if (!dn.color) dn.color = '#6366f1';
      return { data: dn };
    });
    const edges = (data.edges || []).map((e) => ({ data: (e.data || {}) }));

    cy.add(nodes);
    cy.add(edges);
    applyLayout('fcose');
    fitGraph();
  } catch (e) {
    console.error('fetchGraph failed', e);
    alert('加载图谱失败：' + (e?.message || e));
  } finally {
    showLoading(false);
  }
}

function localSearch(q) {
  if (!cy) return;
  cy.elements().removeClass('cy-highlight');
  if (!q) return;

  const query = q.toLowerCase();
  const matches = cy.nodes().filter((n) => ((n.data('label') || '').toLowerCase().includes(query)));
  if (matches.length) {
    matches.addClass('cy-highlight');
    cy.fit(matches, 80);
  }
}

async function exportSubgraph() {
  const seed = (document.getElementById('export-seed')?.value || '').trim();
  const depth = Math.max(1, Math.min(4, Number(document.getElementById('export-depth')?.value || '1') || 1));
  const source = document.getElementById('source-filter')?.value || null;
  const fmt = document.getElementById('export-format')?.value || 'json';
  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed_id: seed || null, depth, source: source || null, format: fmt })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const a = document.createElement('a');
    const url = window.URL.createObjectURL(blob);
    a.href = url;
    a.download = `subgraph.${fmt === 'json' ? 'json' : fmt}`;
    a.click();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert('导出失败：' + (err?.message || err));
  }
}

async function shortestPath() {
  const start = (document.getElementById('sp-source')?.value || '').trim();
  const end = (document.getElementById('sp-target')?.value || '').trim();
  if (!start || !end) {
    alert('请输入 source 和 target 节点名称');
    return;
  }

  showLoading(true);
  try {
    const res = await fetch('/api/path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start, end, max_depth: 10 })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);

    await fetchGraph();
    cy.elements().removeClass('cy-path');

    const nodeNames = data.nodes || [];
    const nodeSet = new Set(nodeNames);
    cy.nodes().forEach((n) => {
      const id = n.id();
      const label = n.data('label');
      if (nodeSet.has(id) || nodeSet.has(label)) n.addClass('cy-path');
    });

    // Highlight edges along the path if present
    if (Array.isArray(data.rels) && data.rels.length && nodeNames.length >= 2) {
      for (let i = 0; i < nodeNames.length - 1; i++) {
        const s = nodeNames[i];
        const t = nodeNames[i + 1];
        cy.edges().forEach((e) => {
          const es = e.data('source');
          const et = e.data('target');
          if ((es === s && et === t) || (es === t && et === s)) e.addClass('cy-path');
        });
      }
    }

    if (nodeNames.length) {
      const nodes = cy.nodes().filter((n) => nodeSet.has(n.id()) || nodeSet.has(n.data('label')));
      if (nodes.length) cy.fit(nodes, 90);
    }
  } catch (err) {
    alert('最短路径失败：' + (err?.message || err));
  } finally {
    showLoading(false);
  }
}

async function uploadFile() {
  const el = document.getElementById('file-upload');
  if (!el || !el.files || !el.files.length) return;
  await uploadFiles(el.files);
  el.value = '';
}

async function uploadFiles(files) {
  if (!files || files.length === 0) return;
  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }
  showLoading(true);
  try {
    const response = await fetch('/api/upload', { method: 'POST', body: formData });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || 'Unknown error');
    }
    alert(`上传完成：处理文件 ${result.processed_files?.length || 0} 个，三元组 ${result.triples_count || 0} 条`);
    await fetchGraph();
  } catch (error) {
    alert('Upload failed: ' + (error?.message || error));
  } finally {
    showLoading(false);
  }
}

function triggerFileSelect() {
  const el = document.getElementById('file-upload');
  if (el) el.click();
}

async function processUrl() {
  const el = document.getElementById('url-input');
  const url = (el?.value || '').trim();
  if (!url) return;
  showLoading(true);
  try {
    const response = await fetch('/api/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || 'Unknown error');
    }
    alert(`URL 导入完成：三元组 ${result.triples_count || 0} 条`);
    await fetchGraph();
  } catch (e) {
    alert('URL 处理失败：' + (e?.message || e));
  } finally {
    showLoading(false);
    if (el) el.value = '';
  }
}

function openDetailPanel(node) {
  const panel = document.getElementById('detail-panel');
  const layout = document.getElementById('layout');
  if (!panel) return;

  panel.classList.add('open');
  if (layout) layout.classList.add('detail-open');

  const title = document.getElementById('detail-title');
  if (title) title.innerText = node.data('label') || node.id();

  const attrsEl = document.getElementById('detail-attrs');
  const outEl = document.getElementById('detail-out');
  const inEl = document.getElementById('detail-in');

  if (attrsEl) {
    attrsEl.innerHTML = '';
    const attrs = node.data() || {};
    Object.keys(attrs).sort().forEach((k) => {
      const v = attrs[k];
      const div = document.createElement('div');
      div.className = 'kv';
      div.innerHTML = `<span class="k">${escapeHtml(k)}</span><span class="v">${escapeHtml(String(v))}</span>`;
      attrsEl.appendChild(div);
    });
  }

  if (outEl) {
    outEl.innerHTML = '';
    node.outgoers('edge').forEach((e) => {
      const t = e.target();
      const pred = e.data('label') || e.data('predicate') || '';
      const div = document.createElement('div');
      div.className = 'relation';
      div.innerHTML = `<span class="pill">${escapeHtml(pred)}</span><span class="to">→ ${escapeHtml(t.data('label') || t.id())}</span>`;
      outEl.appendChild(div);
    });
  }

  if (inEl) {
    inEl.innerHTML = '';
    node.incomers('edge').forEach((e) => {
      const s = e.source();
      const pred = e.data('label') || e.data('predicate') || '';
      const div = document.createElement('div');
      div.className = 'relation';
      div.innerHTML = `<span class="from">${escapeHtml(s.data('label') || s.id())} →</span><span class="pill">${escapeHtml(pred)}</span>`;
      inEl.appendChild(div);
    });
  }
}

function closeDetailPanel() {
  const panel = document.getElementById('detail-panel');
  const layout = document.getElementById('layout');
  if (panel) panel.classList.remove('open');
  if (layout) layout.classList.remove('detail-open');
}

function toggleDetailPanel() {
  const panel = document.getElementById('detail-panel');
  const layout = document.getElementById('layout');
  if (!panel) return;
  const willOpen = !panel.classList.contains('open');
  panel.classList.toggle('open');
  if (layout) layout.classList.toggle('detail-open', willOpen);
}

function highlightNeighborhood() {
  if (!cy || !selectedNodeId) return;
  cy.elements().removeClass('cy-neighbor');
  const node = cy.$id(selectedNodeId);
  const neigh = node.closedNeighborhood();
  neigh.addClass('cy-neighbor');
  cy.fit(neigh, 90);
}

function deleteSelectedNode() {
  if (!cy || !selectedNodeId) return;
  cy.$id(selectedNodeId).remove();
  selectedNodeId = null;
  closeDetailPanel();
}

function showLoading(show) {
  const el = document.getElementById('loading');
  if (!el) return;
  el.style.display = show ? 'flex' : 'none';
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (s) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[s]));
}
