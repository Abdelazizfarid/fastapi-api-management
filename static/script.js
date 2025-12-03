// API Management JavaScript

let currentApiId = null;

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
    apiList.innerHTML = apis.map(api => `
        <div class="api-item ${!api.enabled ? "disabled" : ""}" onclick="editAPI(\"${api.id}\")">
            <div class="api-item-header">
                <span class="api-item-name">${escapeHtml(api.name)}</span>
                <span class="api-item-method method-${api.method}">${api.method}</span>
            </div>
            <div class="api-item-path">${escapeHtml(api.path)}</div>
        </div>
    `).join("");
}

function showCreateForm() {
    document.getElementById("createForm").style.display = "block";
    document.getElementById("editForm").style.display = "none";
    document.getElementById("emptyState").style.display = "none";
    document.getElementById("createApiForm").reset();
}

function hideCreateForm() {
    document.getElementById("createForm").style.display = "none";
    loadAPIs();
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
        document.getElementById("emptyState").style.display = "none";
    } catch (error) {
        alert("Error: " + error.message);
    }
}

function hideEditForm() {
    document.getElementById("editForm").style.display = "none";
    currentApiId = null;
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

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}
