let cy;
let selectedNodeId = null;

document.addEventListener('DOMContentLoaded', function () {
    initCytoscape();
    refreshGraph();

    // Enter key support
    document.getElementById('chat-input').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') sendMessage();
    });
    document.getElementById('search-input').addEventListener('keypress', function (e) {
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

async function fetchGraph(seedId = null, merge = false) {
    showLoading(true);
    try {
        let url = '/api/graph';
        if (seedId) {
            url += `?seed_id=${encodeURIComponent(seedId)}&depth=1`;
        }

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
    const layoutName = (typeof cytoscape('core', 'fcose') === 'function') ? 'fcose' : 'cose';
    cy.layout({
        name: layoutName,
        animate: true,
        animationDuration: 800,
        randomize: false,
        fit: true,
        padding: 50
    }).run();
}

function refreshGraph() {
    selectedNodeId = null;
    document.getElementById('chat-header').innerText = 'Chat (Global)';
    fetchGraph();
}

function searchGraph() {
    const query = document.getElementById('search-input').value;
    if (query) {
        fetchGraph(query);
    }
}

async function uploadFile() {
    const fileInput = document.getElementById('file-upload');
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    showLoading(true);
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            // Handle error response
            alert('Upload failed: ' + (result.error || 'Unknown error'));
            console.error('Upload error:', result);
        } else {
            // Handle success response
            const count = result.triples_count || 0;
            alert(`Upload complete. Triples extracted: ${count}`);
            console.log('Upload success:', result);
            refreshGraph();
        }
    } catch (error) {
        console.error('Upload failed:', error);
        alert('Upload failed: ' + error.message);
    } finally {
        showLoading(false);
        fileInput.value = '';
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
