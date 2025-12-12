// Overwrite entire file with a clean implementation
let cy;
let selectedNodeId = null;
let currentMinConfidence = null;

document.addEventListener('DOMContentLoaded', () => {
  initCytoscape();
  // Ensure Cytoscape resizes to container changes
  window.addEventListener('resize', () => reevaluateViewport());

  const dropZone = document.getElementById('drop-zone');
  const showDrop = () => { if (dropZone) dropZone.classList.add('active'); };
  const hideDrop = () => { if (dropZone) dropZone.classList.remove('active'); };
  ['dragenter','dragover'].forEach(evt => document.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); showDrop(); }));
  ['dragleave','drop'].forEach(evt => document.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); if (evt === 'drop') { const files = e.dataTransfer && e.dataTransfer.files; if (files && files.length) uploadFiles(files); } hideDrop(); }));

  const urlParams = new URLSearchParams(window.location.search);
  const sourceParam = urlParams.get('source');
  if (sourceParam) { const sel = document.getElementById('source-filter'); if (sel) sel.value = sourceParam; }

  const gSearch = document.getElementById('global-search');
  if (gSearch) gSearch.addEventListener('keypress', (e) => { if (e.key === 'Enter') localSearch(gSearch.value.trim()); });
  const sInput = document.getElementById('search-input');
  if (sInput) sInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') localSearch(sInput.value.trim()); });
  const minConf = document.getElementById('min-conf');
  if (minConf) minConf.addEventListener('change', () => { const v = minConf.value; if (v === '') currentMinConfidence = null; else { const n = Number(v); currentMinConfidence = isNaN(n) ? null : n; } refreshGraph(); });
  const srcSel = document.getElementById('source-filter');
  if (srcSel) srcSel.addEventListener('change', () => refreshGraph());

  refreshGraph();
});

function initCytoscape() {
  cy = cytoscape({
    container: document.getElementById('cy'),
    style: [
      { selector: 'node', style: { 'background-color': '#6aa2ff', 'label': 'data(label)', 'color': '#e6edf3', 'text-valign': 'center', 'text-halign': 'center', 'font-size': '12px', 'width': 'label', 'height': 'label', 'padding': '10px', 'text-background-color': '#0f1420', 'text-background-opacity': 0.6, 'text-background-padding': '3px', 'border-width': 1, 'border-color': '#1e2636' }},
      { selector: 'edge', style: { 'width': 2, 'line-color': '#2a3550', 'target-arrow-color': '#2a3550', 'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'label': 'data(label)', 'font-size': '10px', 'text-rotation': 'autorotate', 'color': '#9aa4b2' }},
      { selector: ':selected', style: { 'background-color': '#22d3ee', 'line-color': '#22d3ee', 'target-arrow-color': '#22d3ee' }},
      { selector: '.cy-highlight', style: { 'background-color': '#f1c40f', 'line-color': '#e67e22', 'target-arrow-color': '#e67e22' }},
      { selector: '.cy-path', style: { 'background-color': '#2ecc71', 'line-color': '#2ecc71', 'target-arrow-color': '#27ae60' }},
      { selector: '.cy-neighbor', style: { 'background-color': '#a78bfa', 'line-color': '#a78bfa', 'target-arrow-color': '#a78bfa' }},
    ],
    layout: { name: 'cose', animate: true }
  });

  cy.on('tap', 'node', (evt) => { const node = evt.target; selectedNodeId = node.id(); openDetailPanel(node); });
  cy.on('tap', (evt) => { if (evt.target === cy) selectedNodeId = null; });
}

function clearGraph() { if (cy) cy.elements().remove(); selectedNodeId = null; }

async function fetchGraph() {
  showLoading(true);
  try {
    let url = '/api/graph';
    const params = new URLSearchParams();
    const source = document.getElementById('source-filter').value;
    if (source) params.append('source', source);
    if (currentMinConfidence !== null) params.append('min_confidence', String(currentMinConfidence));
    const qs = params.toString(); if (qs) url += `?${qs}`;
    const res = await fetch(url); const data = await res.json();
    cy.elements().remove(); cy.add(data.nodes || []); cy.add(data.edges || []);
    applyLayout('fcose'); populateSourceOptionsFromGraph();
    reevaluateViewport();
  } catch (e) { console.error('fetchGraph failed', e); }
  finally { showLoading(false); }
}
function reevaluateViewport() {
  if (!cy) return;
  cy.resize();
  if (cy.elements().length) {
    cy.fit(cy.elements(), 60);
  }
}

function applyLayout(name) { const use = (name === 'fcose' && typeof cytoscape('core','fcose') === 'function') ? 'fcose' : (name || 'cose'); cy.layout({ name: use, animate: true, animationDuration: 700, fit: true, padding: 50 }).run(); }

function refreshGraph() { fetchGraph(); }

function localSearch(q) { if (!q) { cy.elements().removeClass('cy-highlight'); return; } const m = cy.nodes().filter(n => (n.data('label')||'').toLowerCase().includes(q.toLowerCase())); cy.elements().removeClass('cy-highlight'); if (m.length) { m.addClass('cy-highlight'); cy.fit(m, 80); } }

function populateSourceOptionsFromGraph() { const sel = document.getElementById('source-filter'); if (!sel) return; const values = new Set(); cy.edges().forEach(e => { const v = e.data('source_doc'); if (v) values.add(v); }); const current = sel.value; sel.innerHTML = '<option value="">All Sources</option>' + Array.from(values).sort().map(v => `<option value="${v}">${v}</option>`).join(''); if (current && values.has(current)) sel.value = current; }

async function exportSubgraph() { const seed = document.getElementById('export-seed').value.trim(); const depth = Number(document.getElementById('export-depth').value || '1'); const source = document.getElementById('source-filter').value || null; const fmt = document.getElementById('export-format').value; try { const res = await fetch('/api/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seed_id: seed || null, depth, source, format: fmt }) }); const blob = await res.blob(); const a = document.createElement('a'); const url = window.URL.createObjectURL(blob); a.href = url; a.download = `subgraph.${fmt==='json'?'json':fmt==='csv'?'csv':'graphml'}`; a.click(); window.URL.revokeObjectURL(url); } catch (err) { alert('导出失败: ' + err.message); } }

async function shortestPath() { const s = document.getElementById('sp-source').value.trim(); const t = document.getElementById('sp-target').value.trim(); if (!s || !t) { alert('请输入两个节点名称'); return; } try { const q = "MATCH p=shortestPath((a:Entity {name: $s})-[:REL*..10]-(b:Entity {name: $t})) RETURN nodes(p) AS nodes, relationships(p) AS rels"; const res = await fetch('/api/cypher', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q, parameters: { s, t } }) }); const data = await res.json(); cy.elements().removeClass('cy-path'); if (!data.success || !Array.isArray(data.result) || data.result.length === 0) { alert('未找到路径'); return; } const row = data.result[0]; const nodeNames = (row.nodes || []).map(n => (n.properties && n.properties.name) || n.name).filter(Boolean); const rels = row.rels || []; await fetchGraph(); cy.nodes().forEach(n => { const label = n.data('label'); if (nodeNames.includes(label) || nodeNames.includes(n.id())) n.addClass('cy-path'); }); rels.forEach(rel => { const start = rel.start?.properties?.name; const end = rel.end?.properties?.name; if (!start || !end) return; cy.edges().forEach(e => { const sL = e.source().data('label') || e.source().id(); const tL = e.target().data('label') || e.target().id(); if (sL === start && tL === end) e.addClass('cy-path'); }); }); } catch (err) { alert('最短路径失败: ' + err.message); } }

async function uploadFile() { const el = document.getElementById('file-upload'); if (!el || !el.files || !el.files.length) return; await uploadFiles(el.files); el.value=''; }

async function uploadFiles(files) { if (!files || files.length === 0) return; const formData = new FormData(); for (let i=0;i<files.length;i++) formData.append('files', files[i]); showLoading(true); try { const response = await fetch('/api/upload', { method: 'POST', body: formData }); const result = await response.json(); if (!response.ok) { alert('Upload failed: ' + (result.error || 'Unknown error')); } else { const count = result.triples_count || 0; alert(`Upload complete. Triples: ${count}`); refreshGraph(); setTimeout(()=>location.reload(), 800); } } catch (error) { alert('Upload failed: ' + error.message); } finally { showLoading(false); } }

function triggerFileSelect() { const el = document.getElementById('file-upload'); if (el) el.click(); }

async function processUrl() { const el = document.getElementById('url-input'); const url = el.value.trim(); if (!url) return; showLoading(true); try { const response = await fetch('/api/url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) }); const result = await response.json(); if (!response.ok) alert('URL processing failed: ' + (result.error || 'Unknown error')); else { alert(`URL processed. Triples: ${result.triples_count}`); refreshGraph(); setTimeout(()=>location.reload(), 800); } } catch (e) { alert('Error: ' + e.message); } finally { showLoading(false); el.value=''; } }

function openDetailPanel(node) { const panel = document.getElementById('detail-panel'); if (!panel) return; panel.classList.add('open'); const layout = document.querySelector('.layout'); if (layout) layout.classList.add('detail-open'); document.getElementById('detail-title').innerText = node.data('label') || node.id(); const attrs = node.data(); const attrsEl = document.getElementById('detail-attrs'); attrsEl.innerHTML = ''; Object.keys(attrs).forEach(k => { const v = attrs[k]; const div = document.createElement('div'); div.className = 'kv'; div.innerHTML = `<div>${escapeHtml(k)}</div><div>${escapeHtml(String(v))}</div>`; attrsEl.appendChild(div); }); const outEl = document.getElementById('detail-out'); outEl.innerHTML = ''; node.outgoers('edge').forEach(e => { const t = e.target(); const pred = e.data('label') || e.data('predicate') || ''; const div = document.createElement('div'); div.className = 'relation'; div.innerHTML = `<div><span class=\"pill\">${escapeHtml(pred)}</span> → ${escapeHtml(t.data('label')||t.id())}</div>`; outEl.appendChild(div); }); const inEl = document.getElementById('detail-in'); inEl.innerHTML = ''; node.incomers('edge').forEach(e => { const s = e.source(); const pred = e.data('label') || e.data('predicate') || ''; const div = document.createElement('div'); div.className = 'relation'; div.innerHTML = `<div>${escapeHtml(s.data('label')||s.id())} → <span class=\"pill\">${escapeHtml(pred)}</span></div>`; inEl.appendChild(div); }); }

function closeDetailPanel() {
  const panel = document.getElementById('detail-panel');
  if (panel) panel.classList.remove('open');
  reevaluateViewport();
}
  function closeDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (panel) panel.classList.remove('open');
}

function toggleDetailPanel() {
  const panel = document.getElementById('detail-panel');
  if (!panel) return;
  panel.classList.toggle('open');
  reevaluateViewport();
}
  function toggleDetailPanel() {
    const panel = document.getElementById('detail-panel');
    if (!panel) return;
    panel.classList.toggle('open');
function openDetailPanel(node) { const panel = document.getElementById('detail-panel'); if (!panel) return; panel.classList.add('open'); document.getElementById('detail-title').innerText = node.data('label') || node.id(); const attrs = node.data(); const attrsEl = document.getElementById('detail-attrs'); attrsEl.innerHTML = ''; Object.keys(attrs).forEach(k => { const v = attrs[k]; const div = document.createElement('div'); div.className = 'kv'; div.innerHTML = `<div>${escapeHtml(k)}</div><div>${escapeHtml(String(v))}</div>`; attrsEl.appendChild(div); }); const outEl = document.getElementById('detail-out'); outEl.innerHTML = ''; node.outgoers('edge').forEach(e => { const t = e.target(); const pred = e.data('label') || e.data('predicate') || ''; const div = document.createElement('div'); div.className = 'relation'; div.innerHTML = `<div><span class=\"pill\">${escapeHtml(pred)}</span> → ${escapeHtml(t.data('label')||t.id())}</div>`; outEl.appendChild(div); }); const inEl = document.getElementById('detail-in'); inEl.innerHTML = ''; node.incomers('edge').forEach(e => { const s = e.source(); const pred = e.data('label') || e.data('predicate') || ''; const div = document.createElement('div'); div.className = 'relation'; div.innerHTML = `<div>${escapeHtml(s.data('label')||s.id())} → <span class=\"pill\">${escapeHtml(pred)}</span></div>`; inEl.appendChild(div); }); reevaluateViewport(); }
}

function highlightNeighborhood() { if (!selectedNodeId) return; cy.elements().removeClass('cy-neighbor'); const node = cy.$id(selectedNodeId); node.addClass('cy-neighbor'); const neigh = node.closedNeighborhood(); neigh.addClass('cy-neighbor'); cy.fit(neigh, 80); }

function deleteSelectedNode() { if (!selectedNodeId) return; cy.$id(selectedNodeId).remove(); selectedNodeId = null; closeDetailPanel(); }

function showLoading(show) { const el = document.getElementById('loading'); if (el) el.style.display = show ? 'block' : 'none'; }

function escapeHtml(str) { return str.replace(/[&<>\"']/g, s => ({ '&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;','\'':'&#39;' }[s])); }
