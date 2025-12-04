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

