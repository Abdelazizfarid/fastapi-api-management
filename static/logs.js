// Logs Viewer JavaScript with Real-time Updates
let autoRefreshInterval = null;
let eventSource = null;
let logsMap = new Map(); // Track logs by ID

document.addEventListener("DOMContentLoaded", () => { 
    loadLogs();
    startRealTimeUpdates();
});

function startRealTimeUpdates() {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }
    
    // Start Server-Sent Events for real-time updates
    eventSource = new EventSource("/api/logs/stream");
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.logs) {
                // Update logs display
                displayLogs(data.logs);
            }
            if (data.executing) {
                // Update executing logs in real-time
                updateExecutingLogs(data.executing);
            }
        } catch (error) {
            console.error("Error parsing SSE data:", error);
        }
    };
    
    eventSource.onerror = function(error) {
        console.error("SSE error:", error);
        // Reconnect after 3 seconds
        setTimeout(() => {
            if (eventSource.readyState === EventSource.CLOSED) {
                startRealTimeUpdates();
            }
        }, 3000);
    };
}

function updateExecutingLogs(executingLogs) {
    executingLogs.forEach(log => {
        const logElement = document.querySelector(`[data-log-id="${log.id}"]`);
        if (logElement) {
            // Update the log item with new data
            const statusElement = logElement.querySelector('.log-status');
            if (statusElement) {
                statusElement.textContent = "Executing...";
                statusElement.className = "log-status status-executing";
            }
            
            // Update prints/output in real-time (use prints field if available, fallback to stdout)
            const prints = log.prints || log.stdout || "";
            
            // Always update prints section if it exists
            let printsSection = logElement.querySelector('.log-prints-output');
            if (printsSection) {
                printsSection.textContent = prints;
                // Auto-scroll to bottom to see latest prints
                printsSection.scrollTop = printsSection.scrollHeight;
            } else if (prints) {
                // Create prints section if it doesn't exist and we have prints
                const detailsDiv = logElement.querySelector('.log-details');
                if (detailsDiv) {
                    // Find where to insert (before Response section)
                    const sections = detailsDiv.querySelectorAll('.log-section');
                    let insertBefore = null;
                    sections.forEach(section => {
                        const title = section.querySelector('.log-section-title');
                        if (title && title.textContent.includes('Response')) {
                            insertBefore = section;
                        }
                    });
                    
                    const printsHTML = `<div class="log-section log-prints-section"><div class="log-section-title">📝 Print Output (Real-time):</div><div class="log-section-content log-prints-output" style="background: #f0f8ff; border-left: 3px solid #3498db; padding: 10px; font-family: monospace; white-space: pre-wrap; max-height: 300px; overflow-y: auto;">${escapeHtml(prints)}</div></div>`;
                    
                    if (insertBefore) {
                        insertBefore.insertAdjacentHTML('beforebegin', printsHTML);
                    } else {
                        detailsDiv.insertAdjacentHTML('afterbegin', printsHTML);
                    }
                    printsSection = logElement.querySelector('.log-prints-output');
                    if (printsSection) {
                        printsSection.scrollTop = printsSection.scrollHeight;
                    }
                }
            }
            
            // Show prints badge in header for executing logs
            if (log.status === "executing" && prints) {
                let printsBadge = logElement.querySelector('.log-prints-badge');
                if (!printsBadge) {
                    const header = logElement.querySelector('.log-header');
                    if (header) {
                        const badge = document.createElement('span');
                        badge.className = 'log-prints-badge';
                        badge.style.cssText = 'background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 10px;';
                        badge.textContent = '📝 Prints';
                        header.appendChild(badge);
                    }
                }
            }
        }
    });
}

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
        let statusClass = "status-2xx";
        let statusText = log.status_code || "Executing...";
        
        if (log.status === "executing") {
            statusClass = "status-executing";
            statusText = "Executing...";
        } else if (log.status_code >= 500) {
            statusClass = "status-5xx";
        } else if (log.status_code >= 400) {
            statusClass = "status-4xx";
        }
        
        const prints = log.prints || log.stdout || "";
        const hasPrints = prints.length > 0;
        const isExecuting = log.status === "executing";
        
        return `<div class="log-item" data-log-id="${log.id}">
            <div class="log-header" onclick="toggleLogDetails(${index})" style="cursor: pointer;">
                <span class="log-method method-${log.method}">${log.method}</span>
                <span class="log-path">${escapeHtml(log.path)}</span>
                <span class="log-status ${statusClass}">${statusText}</span>
                ${isExecuting && hasPrints ? '<span class="log-prints-badge" style="background: #3498db; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-left: 10px;">📝 Prints</span>' : ''}
                <span class="log-timestamp">${date.toLocaleString()}</span>
                <span class="log-toggle" id="toggle-${index}">▼</span>
            </div>
            <div class="log-details" id="details-${index}" style="display: ${isExecuting ? 'block' : 'none'};">
                <div class="log-section"><div class="log-section-title">Query:</div><div class="log-section-content">${escapeHtml(JSON.stringify(log.query_params, null, 2))}</div></div>
                <div class="log-section"><div class="log-section-title">Headers:</div><div class="log-section-content">${escapeHtml(JSON.stringify(log.headers, null, 2))}</div></div>
                <div class="log-section log-prints-section"><div class="log-section-title">📝 Print Output ${isExecuting ? '(Real-time)' : ''}:</div><div class="log-section-content log-prints-output" style="background: #f0f8ff; border-left: 3px solid #3498db; padding: 10px; font-family: monospace; white-space: pre-wrap; line-height: 1.6; max-height: 300px; overflow-y: auto;">${escapeHtml(prints)}</div></div>
                <div class="log-section"><div class="log-section-title">Response:</div><div class="log-section-content">${escapeHtml(log.response_body || 'Executing...')}</div></div>
                <div class="log-section"><div class="log-section-title">IP:</div><div class="log-section-content">${escapeHtml(log.client_ip || "N/A")}</div></div>
                <div class="log-section"><div class="log-section-title">Time:</div><div class="log-section-content">${log.response_time_ms ? log.response_time_ms.toFixed(2) + ' ms' : 'Executing...'}</div></div>
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
        // Auto-scroll prints section to bottom when expanded
        const printsSection = details.querySelector('.log-prints-output');
        if (printsSection) {
            setTimeout(() => {
                printsSection.scrollTop = printsSection.scrollHeight;
            }, 100);
        }
    } else {
        details.style.display = "none";
        toggle.textContent = "▼";
    }
}

function refreshLogs() { 
    loadLogs(); 
}

async function clearLogs() {
    if (!confirm("Clear all logs?")) return;
    try {
        const response = await fetch("/api/logs", { method: "DELETE" });
        if (response.ok) loadLogs();
    } catch (error) { 
        alert("Error: " + error.message); 
    }
}

function toggleAutoRefresh() {
    const checkbox = document.getElementById("autoRefresh");
    if (checkbox.checked) {
        // Real-time updates are already enabled via SSE
        checkbox.checked = true;
    } else {
        // Keep SSE running but disable auto-refresh button
        checkbox.checked = false;
    }
}

function escapeHtml(text) {
    if (text === null || text === undefined) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener("beforeunload", () => {
    if (eventSource) {
        eventSource.close();
    }
});

