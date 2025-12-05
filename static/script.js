// API Management JavaScript

let currentApiId = null;
let currentApiData = null;

document.addEventListener("DOMContentLoaded", () => {
    loadAPIs();
});

async function loadAPIs() {
    try {
        const response = await fetch("/api/manage/list");
        const data = await response.json();
        displayAPIs(data.apis);
    } catch (error) {
        console.error("Error loading APIs:", error);
    }
}

function displayAPIs(apis) {
    const apiList = document.getElementById("apiList");
    if (apis.length === 0) {
        apiList.innerHTML = "<p style=\"color: #666; text-align: center; padding: 20px;\">No APIs yet</p>";
        document.getElementById("emptyState").style.display = "block";
        return;
    }
    document.getElementById("emptyState").style.display = "none";
    
    // Clear existing content and use event delegation
    apiList.innerHTML = "";
    apis.forEach(api => {
        const apiId = api.id;
        const apiItem = document.createElement("div");
        apiItem.className = `api-item ${!api.enabled ? "disabled" : ""}`;
        apiItem.style.cursor = "pointer";
        apiItem.setAttribute("data-api-id", apiId);
        apiItem.innerHTML = `
            <div class="api-item-header">
                <span class="api-item-name">${escapeHtml(api.name)}</span>
                <span class="api-item-method method-${api.method}">${api.method}</span>
            </div>
            <div class="api-item-path">${escapeHtml(api.path)}</div>
        `;
        apiItem.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log("API item clicked, ID:", apiId);
            showApiDetails(apiId);
        });
        apiList.appendChild(apiItem);
    });
}

function showCreateForm() {
    document.getElementById("createForm").style.display = "block";
    document.getElementById("editForm").style.display = "none";
    document.getElementById("detailsView").style.display = "none";
    document.getElementById("emptyState").style.display = "none";
    document.getElementById("createApiForm").reset();
}

function hideCreateForm() {
    document.getElementById("createForm").style.display = "none";
    loadAPIs();
}

async function showApiDetails(apiId) {
    console.log("showApiDetails called with ID:", apiId);
    try {
        const response = await fetch("/api/manage/list");
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log("API data received:", data);
        const api = data.apis.find(a => a.id === apiId);
        if (!api) { 
            alert("API not found"); 
            return; 
        }
        
        console.log("Found API:", api);
        currentApiId = apiId;
        currentApiData = api;
        
        // Get all elements
        const detailsView = document.getElementById("detailsView");
        const detailsApiName = document.getElementById("detailsApiName");
        const detailsApiMethod = document.getElementById("detailsApiMethod");
        const detailsApiPath = document.getElementById("detailsApiPath");
        const detailsApiDescription = document.getElementById("detailsApiDescription");
        const detailsApiStatus = document.getElementById("detailsApiStatus");
        const detailsApiCreated = document.getElementById("detailsApiCreated");
        const detailsApiUpdated = document.getElementById("detailsApiUpdated");
        const detailsApiCode = document.getElementById("detailsApiCode");
        
        if (!detailsView) {
            console.error("detailsView element not found!");
            alert("Error: Details view element not found. Please refresh the page.");
            return;
        }
        
        // Populate details view
        if (detailsApiName) detailsApiName.textContent = api.name;
        if (detailsApiMethod) detailsApiMethod.innerHTML = `<span class="api-item-method method-${api.method}">${api.method}</span>`;
        if (detailsApiPath) detailsApiPath.textContent = api.path;
        if (detailsApiDescription) detailsApiDescription.textContent = api.description || "No description";
        if (detailsApiStatus) detailsApiStatus.innerHTML = api.enabled 
            ? '<span style="color: #27ae60; font-weight: bold;">✓ Enabled</span>' 
            : '<span style="color: #e74c3c; font-weight: bold;">✗ Disabled</span>';
        
        // Format dates
        const createdDate = api.created_at ? new Date(api.created_at).toLocaleString() : "N/A";
        const updatedDate = api.updated_at ? new Date(api.updated_at).toLocaleString() : "N/A";
        if (detailsApiCreated) detailsApiCreated.textContent = createdDate;
        if (detailsApiUpdated) detailsApiUpdated.textContent = updatedDate;
        
        // Show code
        if (detailsApiCode) detailsApiCode.textContent = api.python_code || "No code";
        
        // Show details view, hide others
        detailsView.style.display = "block";
        const createForm = document.getElementById("createForm");
        const editForm = document.getElementById("editForm");
        const emptyState = document.getElementById("emptyState");
        if (createForm) createForm.style.display = "none";
        if (editForm) editForm.style.display = "none";
        if (emptyState) emptyState.style.display = "none";
        
        console.log("Details view displayed");
    } catch (error) {
        console.error("Error loading API details:", error);
        alert("Error loading API details: " + error.message);
    }
}

function hideDetailsView() {
    document.getElementById("detailsView").style.display = "none";
    currentApiId = null;
    currentApiData = null;
    loadAPIs();
}

function showEditFromDetails() {
    if (!currentApiData) return;
    
    // Populate edit form with current API data
    document.getElementById("editApiId").value = currentApiId;
    document.getElementById("editApiName").value = currentApiData.name;
    document.getElementById("editApiPath").value = currentApiData.path;
    document.getElementById("editApiDescription").value = currentApiData.description || "";
    document.getElementById("editApiCode").value = currentApiData.python_code;
    
    const methodSelect = document.getElementById("editApiMethod");
    methodSelect.innerHTML = ["GET", "POST", "PUT", "DELETE", "PATCH"].map(m => 
        `<option value="${m}" ${m === currentApiData.method ? "selected" : ""}>${m}</option>`
    ).join("");
    
    // Show edit form, hide details view
    document.getElementById("editForm").style.display = "block";
    document.getElementById("detailsView").style.display = "none";
    document.getElementById("createForm").style.display = "none";
    document.getElementById("emptyState").style.display = "none";
}

document.getElementById("createApiForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const apiData = {
        name: document.getElementById("apiName").value,
        path: document.getElementById("apiPath").value,
        method: document.getElementById("apiMethod").value,
        description: document.getElementById("apiDescription").value,
        python_code: document.getElementById("apiCode").value
    };
    try {
        const response = await fetch("/api/manage/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(apiData)
        });
        const result = await response.json();
        if (response.ok) {
            alert("API created! Server restart may be required.");
            hideCreateForm();
            loadAPIs();
        } else {
            alert("Error: " + (result.detail || result.error || "Unknown error"));
        }
    } catch (error) {
        alert("Error: " + error.message);
    }
});

async function editAPI(apiId) {
    try {
        const response = await fetch("/api/manage/list");
        const data = await response.json();
        const api = data.apis.find(a => a.id === apiId);
        if (!api) { alert("API not found"); return; }
        currentApiId = apiId;
        currentApiData = api;
        document.getElementById("editApiId").value = apiId;
        document.getElementById("editApiName").value = api.name;
        document.getElementById("editApiPath").value = api.path;
        document.getElementById("editApiMethod").value = api.method;
        document.getElementById("editApiDescription").value = api.description || "";
        document.getElementById("editApiCode").value = api.python_code;
        const methodSelect = document.getElementById("editApiMethod");
        methodSelect.innerHTML = ["GET", "POST", "PUT", "DELETE", "PATCH"].map(m => 
            `<option value="${m}" ${m === api.method ? "selected" : ""}>${m}</option>`
        ).join("");
        document.getElementById("editForm").style.display = "block";
        document.getElementById("createForm").style.display = "none";
        document.getElementById("detailsView").style.display = "none";
        document.getElementById("emptyState").style.display = "none";
    } catch (error) {
        alert("Error: " + error.message);
    }
}

function hideEditForm() {
    document.getElementById("editForm").style.display = "none";
    currentApiId = null;
    currentApiData = null;
    loadAPIs();
}

document.getElementById("editApiForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const apiId = document.getElementById("editApiId").value;
    const updateData = {
        name: document.getElementById("editApiName").value,
        path: document.getElementById("editApiPath").value,
        method: document.getElementById("editApiMethod").value,
        description: document.getElementById("editApiDescription").value,
        python_code: document.getElementById("editApiCode").value
    };
    try {
        const response = await fetch(`/api/manage/${apiId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(updateData)
        });
        const result = await response.json();
        if (response.ok) {
            alert("API updated! Server restart required.");
            hideEditForm();
            loadAPIs();
        } else {
            alert("Error: " + (result.detail || result.error || "Unknown error"));
        }
    } catch (error) {
        alert("Error: " + error.message);
    }
});

async function deleteCurrentApi() {
    if (!currentApiId) return;
    if (!confirm("Delete this API?")) return;
    try {
        const response = await fetch(`/api/manage/${currentApiId}`, { method: "DELETE" });
        const result = await response.json();
        if (response.ok) {
            alert("API deleted! Server restart required.");
            hideEditForm();
            loadAPIs();
        } else {
            alert("Error: " + (result.detail || result.error || "Unknown error"));
        }
    } catch (error) {
        alert("Error: " + error.message);
    }
}

async function testCode() {
    const code = document.getElementById("apiCode").value;
    if (!code.trim()) { alert("Please enter code"); return; }
    const testData = { name: "test", path: "/test", method: "GET", python_code: code };
    try {
        const response = await fetch("/api/manage/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testData)
        });
        const result = await response.json();
        displayTestResult(result, "testResult");
    } catch (error) {
        displayTestResult({ success: false, stderr: error.message }, "testResult");
    }
}

async function testEditCode() {
    const code = document.getElementById("editApiCode").value;
    if (!code.trim()) { alert("Please enter code"); return; }
    const testData = { name: "test", path: "/test", method: "GET", python_code: code };
    try {
        const response = await fetch("/api/manage/test", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(testData)
        });
        const result = await response.json();
        displayTestResult(result, "editTestResult");
    } catch (error) {
        displayTestResult({ success: false, stderr: error.message }, "editTestResult");
    }
}

function displayTestResult(result, elementId) {
    const element = document.getElementById(elementId);
    if (result.success) {
        element.className = "test-result success";
        element.innerHTML = `<strong>✓ Success!</strong><br><strong>Result:</strong><br><pre>${escapeHtml(JSON.stringify(result.result, null, 2))}</pre>${result.stdout ? `<strong>Output:</strong><br><pre>${escapeHtml(result.stdout)}</pre>` : ""}`;
    } else {
        element.className = "test-result error";
        element.innerHTML = `<strong>✗ Error!</strong><br><strong>Error:</strong><br><pre>${escapeHtml(result.stderr)}</pre>${result.stdout ? `<strong>Output:</strong><br><pre>${escapeHtml(result.stdout)}</pre>` : ""}`;
    }
}

async function restartServer() {
    if (!confirm("Are you sure you want to restart the server? This will temporarily disconnect you.")) {
        return;
    }
    
    try {
        const response = await fetch("/api/manage/restart", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        
        if (response.ok) {
            alert("Server restart initiated! The page will reload in 5 seconds...");
            setTimeout(() => {
                window.location.reload();
            }, 5000);
        } else {
            alert("Error: " + (result.detail || result.error || "Unknown error"));
        }
    } catch (error) {
        // If request fails, it might be because server is restarting
        alert("Server restart initiated! Please wait a few seconds and refresh the page.");
        setTimeout(() => {
            window.location.reload();
        }, 5000);
    }
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// Async Logs functionality
let asyncLogsAutoRefreshInterval = null;

function showAPIsTab() {
    document.querySelector('nav a[href="/"]').classList.add('active');
    document.querySelector('.async-logs-tab').classList.remove('active');
    document.getElementById('asyncLogsView').style.display = 'none';
    document.getElementById('createForm').style.display = 'none';
    document.getElementById('editForm').style.display = 'none';
    document.getElementById('detailsView').style.display = 'none';
    if (document.getElementById('apiList').children.length > 0) {
        document.getElementById('emptyState').style.display = 'none';
    } else {
        document.getElementById('emptyState').style.display = 'block';
    }
    stopAsyncLogsAutoRefresh();
}

function showAsyncLogsTab() {
    document.querySelector('nav a[href="/"]').classList.remove('active');
    document.querySelector('.async-logs-tab').classList.add('active');
    document.getElementById('asyncLogsView').style.display = 'block';
    document.getElementById('createForm').style.display = 'none';
    document.getElementById('editForm').style.display = 'none';
    document.getElementById('detailsView').style.display = 'none';
    document.getElementById('emptyState').style.display = 'none';
    refreshAsyncLogs();
    if (document.getElementById('asyncAutoRefresh').checked) {
        startAsyncLogsAutoRefresh();
    }
}

async function refreshAsyncLogs() {
    try {
        const response = await fetch('/api/background-jobs/list');
        if (!response.ok) throw new Error('Failed to fetch async logs');
        const data = await response.json();
        displayAsyncLogs(data.jobs || []);
    } catch (error) {
        console.error('Error loading async logs:', error);
        document.getElementById('asyncLogsList').innerHTML = 
            '<div class="error-message">Error loading async logs. Please try again.</div>';
    }
}

function displayAsyncLogs(jobs) {
    const logsList = document.getElementById('asyncLogsList');
    const emptyLogs = document.getElementById('emptyAsyncLogs');
    
    if (jobs.length === 0) {
        logsList.innerHTML = '';
        emptyLogs.style.display = 'block';
        return;
    }
    
    emptyLogs.style.display = 'none';
    
    // Sort by started_at descending
    jobs.sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
    
    logsList.innerHTML = jobs.map(job => {
        const statusClass = job.status === 'running' ? 'status-running' : 
                           job.status === 'completed' ? 'status-completed' : 'status-failed';
        const statusIcon = job.status === 'running' ? '🔄' : 
                          job.status === 'completed' ? '✅' : '❌';
        const stopButton = job.status === 'running' ? 
            `<button class="btn btn-danger btn-sm" onclick="stopJob('${job.id}')" style="margin-left: 10px;">⏹️ Stop</button>` : '';
        
        const startedAt = new Date(job.started_at).toLocaleString();
        const completedAt = job.completed_at ? new Date(job.completed_at).toLocaleString() : 'N/A';
        
        return `
            <div class="async-log-item ${statusClass}">
                <div class="async-log-header">
                    <div class="async-log-title">
                        <span class="status-icon">${statusIcon}</span>
                        <strong>${escapeHtml(job.job_type || 'Unknown')}</strong>
                        <span class="status-badge ${statusClass}">${job.status}</span>
                        ${stopButton}
                    </div>
                    <div class="async-log-meta">
                        <span>Started: ${startedAt}</span>
                        ${job.completed_at ? `<span>Completed: ${completedAt}</span>` : ''}
                    </div>
                </div>
                ${job.error_message ? `<div class="async-log-error">Error: ${escapeHtml(job.error_message)}</div>` : ''}
                ${job.result_summary ? `<div class="async-log-summary"><pre>${escapeHtml(job.result_summary)}</pre></div>` : ''}
                <div class="async-log-actions">
                    <button class="btn btn-secondary btn-sm" onclick="viewJobLogs('${job.id}')">View Logs</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteJob('${job.id}')">🗑️ Delete</button>
                </div>
            </div>
        `;
    }).join('');
}

async function stopJob(jobId) {
    if (!confirm('Are you sure you want to stop this job?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/background-jobs/${jobId}/stop`, {
            method: 'POST'
        });
        
        const contentType = response.headers.get("content-type");
        if (!response.ok) {
            let error;
            if (contentType && contentType.includes("application/json")) {
                error = await response.json();
                throw new Error(error.detail || error.message || 'Failed to stop job');
            } else {
                const text = await response.text();
                throw new Error(text || 'Failed to stop job');
            }
        }
        
        // Parse response if it's JSON, otherwise just show success
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            alert(data.message || 'Job stop request sent. It may take a moment to stop.');
        } else {
            alert('Job stop request sent. It may take a moment to stop.');
        }
        refreshAsyncLogs();
    } catch (error) {
        alert('Error stopping job: ' + error.message);
    }
}

async function viewJobLogs(jobId) {
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    const logsContainer = document.createElement('pre');
    logsContainer.id = `logs-${jobId}`;
    logsContainer.style.cssText = 'white-space: pre-wrap; word-wrap: break-word; max-height: 60vh; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 4px; font-family: "Courier New", monospace; font-size: 12px;';
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 900px; max-height: 85vh;">
            <div class="modal-header">
                <h3>Job Logs</h3>
                <div style="float: right;">
                    <button class="btn btn-primary btn-sm" onclick="refreshJobLogs('${jobId}')" style="margin-right: 10px;">🔄 Refresh</button>
                    <button onclick="closeLogsModal('${jobId}')" style="background: none; border: none; font-size: 24px; cursor: pointer; color: #666;">&times;</button>
                </div>
            </div>
            <div class="modal-body">
                <div id="logs-container-${jobId}"></div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="refreshJobLogs('${jobId}')">🔄 Refresh Logs</button>
                <button class="btn btn-secondary" onclick="closeLogsModal('${jobId}')">Close</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    
    const container = document.getElementById(`logs-container-${jobId}`);
    container.appendChild(logsContainer);
    
    // Store jobId in modal for refresh function
    modal._jobId = jobId;
    
    // Initial load
    await refreshJobLogs(jobId);
    
    // Close handler
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeLogsModal(jobId);
        }
    });
}

async function refreshJobLogs(jobId) {
    const logsContainer = document.getElementById(`logs-${jobId}`);
    if (!logsContainer) return;
    
    // Show loading state
    const originalContent = logsContainer.innerHTML;
    logsContainer.innerHTML = '<div style="color: #888;">Loading logs...</div>';
    
    try {
        const response = await fetch(`/api/background-jobs/${jobId}/logs?limit=10000`);
        if (!response.ok) {
            throw new Error('Failed to fetch logs');
        }
        
        const data = await response.json();
        
        // Clear existing logs
        logsContainer.innerHTML = '';
        
        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(log => {
                const timestamp = new Date(log.timestamp).toLocaleString();
                const level = log.log_level.toUpperCase();
                const levelColor = log.log_level === 'error' ? '#e74c3c' : 
                                 log.log_level === 'success' ? '#2ecc71' : 
                                 log.log_level === 'warning' ? '#f39c12' : '#3498db';
                
                const logLine = document.createElement('div');
                logLine.style.cssText = 'margin-bottom: 2px;';
                logLine.innerHTML = `<span style="color: #888;">[${timestamp}]</span> <span style="color: ${levelColor}; font-weight: bold;">[${level}]</span> <span style="color: #d4d4d4;">${escapeHtml(log.message)}</span>`;
                logsContainer.appendChild(logLine);
            });
            
            // Auto-scroll to bottom
            logsContainer.scrollTop = logsContainer.scrollHeight;
        } else {
            logsContainer.innerHTML = '<div style="color: #888;">No logs available yet.</div>';
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        logsContainer.innerHTML = `<div style="color: #e74c3c;">Error loading logs: ${escapeHtml(error.message)}</div>`;
    }
}

function closeLogsModal(jobId) {
    const modal = document.querySelector('.modal-overlay');
    if (modal) {
        modal.remove();
    }
}

function toggleAsyncAutoRefresh() {
    const checkbox = document.getElementById('asyncAutoRefresh');
    if (checkbox.checked) {
        startAsyncLogsAutoRefresh();
    } else {
        stopAsyncLogsAutoRefresh();
    }
}

function startAsyncLogsAutoRefresh() {
    stopAsyncLogsAutoRefresh();
    asyncLogsAutoRefreshInterval = setInterval(refreshAsyncLogs, 3000);
}

function stopAsyncLogsAutoRefresh() {
    if (asyncLogsAutoRefreshInterval) {
        clearInterval(asyncLogsAutoRefreshInterval);
        asyncLogsAutoRefreshInterval = null;
    }
}

async function deleteJob(jobId) {
    if (!confirm('Are you sure you want to delete this job and all its logs? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/background-jobs/${jobId}`, {
            method: 'DELETE'
        });
        
        const contentType = response.headers.get("content-type");
        if (!response.ok) {
            let error;
            if (contentType && contentType.includes("application/json")) {
                error = await response.json();
                throw new Error(error.detail || error.message || 'Failed to delete job');
            } else {
                const text = await response.text();
                throw new Error(text || 'Failed to delete job');
            }
        }
        
        // Parse response if it's JSON
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            alert(data.message || 'Job deleted successfully');
        } else {
            alert('Job deleted successfully');
        }
        refreshAsyncLogs();
    } catch (error) {
        alert('Error deleting job: ' + error.message);
    }
}

