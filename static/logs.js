// Logs Viewer JavaScript
let autoRefreshInterval = null;

document.addEventListener("DOMContentLoaded", () => { loadLogs(); });

async function loadLogs() {
    try {
        const response = await fetch("/api/logs?limit=100");
        const data = await response.json();
        displayLogs(data.logs);
    } catch (error) {
        console.error("Error:", error);
    }
}

function displayLogs(logs) {
    const logsList = document.getElementById("logsList");
    const emptyLogs = document.getElementById("emptyLogs");
    
    if (logs.length === 0) {
        logsList.innerHTML = "";
        emptyLogs.style.display = "block";
        return;
    }
    
    emptyLogs.style.display = "none";
    
    logsList.innerHTML = logs.map((log, index) => {
        const date = new Date(log.timestamp);
        const statusClass = log.status_code >= 500 ? "status-5xx" : 
                           log.status_code >= 400 ? "status-4xx" : "status-2xx";
        
        return `<div class="log-item">
            <div class="log-header" onclick="toggleLogDetails(${index})" style="cursor: pointer;">
                <span class="log-method method-${log.method}">${log.method}</span>
                <span class="log-path">${escapeHtml(log.path)}</span>
                <span class="log-status ${statusClass}">${log.status_code}</span>
                <span class="log-timestamp">${date.toLocaleString()}</span>
                <span class="log-toggle" id="toggle-${index}">▼</span>
            </div>
            <div class="log-details" id="details-${index}" style="display: none;">
                <div class="log-section"><div class="log-section-title">Query:</div><div class="log-section-content">${escapeHtml(JSON.stringify(log.query_params, null, 2))}</div></div>
                <div class="log-section"><div class="log-section-title">Headers:</div><div class="log-section-content">${escapeHtml(JSON.stringify(log.headers, null, 2))}</div></div>
                <div class="log-section"><div class="log-section-title">Response:</div><div class="log-section-content">${escapeHtml(log.response_body)}</div></div>
                <div class="log-section"><div class="log-section-title">IP:</div><div class="log-section-content">${escapeHtml(log.client_ip || "N/A")}</div></div>
                <div class="log-section"><div class="log-section-title">Time:</div><div class="log-section-content">${log.response_time_ms.toFixed(2)} ms</div></div>
            </div>
        </div>`;
    }).join("");
}

function toggleLogDetails(index) {
    const details = document.getElementById(`details-${index}`);
    const toggle = document.getElementById(`toggle-${index}`);
    if (details.style.display === "none") {
        details.style.display = "block";
        toggle.textContent = "▲";
    } else {
        details.style.display = "none";
        toggle.textContent = "▼";
    }
}
function refreshLogs() { loadLogs(); }

async function clearLogs() {
    if (!confirm("Clear all logs?")) return;
    try {
        const response = await fetch("/api/logs", { method: "DELETE" });
        if (response.ok) loadLogs();
    } catch (error) { alert("Error: " + error.message); }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById("autoRefresh");
    if (checkbox.checked) {
        autoRefreshInterval = setInterval(() => { loadLogs(); }, 5000);
    } else {
        if (autoRefreshInterval) { clearInterval(autoRefreshInterval); autoRefreshInterval = null; }
    }
}

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}


function toggleLogDetails(index) {
    const details = document.getElementById(`details-${index}`);
    const toggle = document.getElementById(`toggle-${index}`);
    if (details.style.display === "none") {
        details.style.display = "block";
        toggle.textContent = "▲";
    } else {
        details.style.display = "none";
        toggle.textContent = "▼";
    }
}