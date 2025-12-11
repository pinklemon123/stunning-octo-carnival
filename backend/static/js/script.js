let cy;
let selectedNodeId = null;
let currentLayout = 'fcose';

document.addEventListener('DOMContentLoaded', function () {
    initCytoscape();

    // Drag & drop upload wiring
    const dropZone = document.getElementById('drop-zone');
    const showDrop = () => { if (dropZone) dropZone.classList.remove('hidden'); };
    const hideDrop = () => { if (dropZone) dropZone.classList.add('hidden'); };
    ['dragenter','dragover'].forEach(evtName => {
        document.addEventListener(evtName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            showDrop();
        });
    });
    ['dragleave','drop'].forEach(evtName => {
        document.addEventListener(evtName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (evtName === 'drop') {
                const files = e.dataTransfer && e.dataTransfer.files;
                if (files && files.length) {
                    uploadFiles(files);
                }
            }
            hideDrop();
        });
    });

    // Check for URL parameters (e.g. ?source=test.txt)
    const urlParams = new URLSearchParams(window.location.search);
    const sourceParam = urlParams.get('source');

    if (sourceParam) {
        document.getElementById('source-filter').value = sourceParam;
        // We can call fetchGraph directly, which will read the input we just set
        fetchGraph();
    } else {
        refreshGraph();
    }

    // Enter key support
    document.getElementById('chat-input').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') sendMessage();
    });
    document.getElementById('search-input').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') searchGraph();
    });
    // Also allow Enter on source filter
    document.getElementById('source-filter').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') searchGraph();
    });
});

function initCytoscape() {
    cy = cytoscape({
        container: document.getElementById('cy'),
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': '#3498db',
                    'label': 'data(label)',
                    'color': '#333',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '12px',
                    'width': 'label',
                    'height': 'label',
                    'padding': '12px',
                    'text-background-color': '#fff',
                    'text-background-opacity': 0.7,
                    'text-background-padding': '2px'
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#ccc',
                    'target-arrow-color': '#ccc',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'label': 'data(label)',
                    'font-size': '10px',
                    'text-rotation': 'autorotate',
                    'color': '#999'
                }
            },
            {
                selector: ':selected',
                style: {
                    'background-color': '#e74c3c',
                    'line-color': '#e74c3c',
                    'target-arrow-color': '#e74c3c',
                    'source-arrow-color': '#e74c3c'
                }
            }
        ],
        layout: {
            name: 'cose', // Fallback if fcose fails to load
            animate: true
        }
    });

    cy.on('tap', 'node', function (evt) {
        const node = evt.target;
        selectedNodeId = node.id();
        document.getElementById('chat-header').innerText = 'Chatting about: ' + node.data('label');
        console.log('Selected ' + selectedNodeId);

        // Optional: Expand graph on click
        fetchGraph(selectedNodeId, true);
    });

    cy.on('tap', function (evt) {
        if (evt.target === cy) {
            selectedNodeId = null;
            document.getElementById('chat-header').innerText = 'Chat (Global)';
        }
    });
}

function clearGraph() {
    if (cy) {
        cy.elements().remove();
    }
    document.getElementById('chat-header').innerText = 'Chat (Global)';
    selectedNodeId = null;
}

async function fetchGraph(seedId = null, merge = false) {
    showLoading(true);
    try {
        let url = '/api/graph';
        const params = new URLSearchParams();

        if (seedId) params.append('seed_id', seedId);

        const sourceFilter = document.getElementById('source-filter').value.trim();
        if (sourceFilter) params.append('source', sourceFilter);

        if (seedId) params.append('depth', '1');

        const queryString = params.toString();
        if (queryString) url += `?${queryString}`;

        const response = await fetch(url);
        const data = await response.json();

        if (merge && seedId) {
            cy.add(data.nodes);
            cy.add(data.edges);
        } else {
            cy.elements().remove();
            cy.add(data.nodes);
            cy.add(data.edges);
        }

        runLayout();
    } catch (error) {
        console.error('Error fetching graph:', error);
    } finally {
        showLoading(false);
    }
}

function runLayout() {
    let layoutName = currentLayout;
    // Fallback if fcose not available
    if (layoutName === 'fcose' && typeof cytoscape('core', 'fcose') !== 'function') {
        layoutName = 'cose';
    }
    const optionsByLayout = {
        fcose: { name: 'fcose', animate: true, animationDuration: 800, fit: true, padding: 50 },
        cose: { name: 'cose', animate: true, animationDuration: 800, fit: true, padding: 50 },
        grid: { name: 'grid', fit: true, padding: 50 },
        concentric: { name: 'concentric', fit: true, padding: 50 }
    };
    const opts = optionsByLayout[layoutName] || optionsByLayout['cose'];
    cy.layout(opts).run();
}

function applyLayoutFromSelect() {
    const select = document.getElementById('layout-select');
    if (!select) return;
    currentLayout = select.value;
    runLayout();
}

function refreshGraph() {
    selectedNodeId = null;
    document.getElementById('chat-header').innerText = 'Chat (Global)';
    fetchGraph();
}

function searchGraph() {
    const query = document.getElementById('search-input').value;
    // We call fetchGraph, which will pick up both the search input (as seedId if passed) 
    // and the source filter.
    // Note: fetchGraph logic above treats the first arg as seedId.
    // Let's adjust usage.
    // If query is empty, refresh; else try to highlight existing nodes first.
    if (!query) {
        refreshGraph();
        return;
    }
    const matches = cy.nodes().filter(n => (n.data('label') || '').includes(query));
    if (matches.length > 0) {
        cy.elements().removeClass('highlight');
        matches.addClass('highlight');
        cy.fit(matches, 60);
    } else {
        // If no local match, fetch as seed to expand neighborhood
        fetchGraph(query);
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const files = fileInput.files;
    if (!files || files.length === 0) return;
    await uploadFiles(files);

    // Style for highlight
    cy.style().selector('.highlight').style({
        'background-color': '#f1c40f',
        'border-color': '#e67e22',
        'line-color': '#e67e22',
        'target-arrow-color': '#e67e22'
    }).update();
    fileInput.value = '';
}

async function uploadFiles(files) {
    if (!files || files.length === 0) return;
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) formData.append('files', files[i]);

    showLoading(true);
    try {
        const response = await fetch('/api/upload', { method: 'POST', body: formData });
        const result = await response.json();
        if (!response.ok) {
            alert('Upload failed: ' + (result.error || 'Unknown error'));
            console.error('Upload error:', result);
        } else {
            const count = result.triples_count || 0;
            const processed = result.processed_files ? result.processed_files.join(', ') : 'files';
            alert(`Upload complete. Processed: ${processed}\nTriples extracted: ${count}`);
            refreshGraph();
            setTimeout(() => location.reload(), 1000);
        }
    } catch (error) {
        console.error('Upload failed:', error);
        alert('Upload failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

function triggerFileSelect() {
    const fileInput = document.getElementById('file-upload');
    if (fileInput) fileInput.click();
}

async function processUrl() {
    const urlInput = document.getElementById('url-input');
    const url = urlInput.value.trim();
    if (!url) return;

    showLoading(true);
    try {
        const response = await fetch('/api/url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url })
        });

        const result = await response.json();

        if (!response.ok) {
            alert('URL processing failed: ' + (result.error || 'Unknown error'));
        } else {
            alert(`URL processed successfully.\nTriples extracted: ${result.triples_count}`);
            refreshGraph();
            setTimeout(() => location.reload(), 1000);
        }
    } catch (error) {
        console.error('URL processing failed:', error);
        alert('Error: ' + error.message);
    } finally {
        showLoading(false);
        urlInput.value = '';
    }
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    addMessage('user', message);
    input.value = '';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                node_id: selectedNodeId,
                message: message
            })
        });
        const data = await response.json();
        addMessage('assistant', data.reply);
    } catch (error) {
        console.error('Chat error:', error);
        addMessage('assistant', 'Error: Could not reach the assistant.');
    }
}

function addMessage(role, text) {
    const history = document.getElementById('chat-history');
    const div = document.createElement('div');
    div.className = `message ${role}`;
    div.innerText = text;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

function showLoading(show) {
    document.getElementById('loading').style.display = show ? 'block' : 'none';
}
