from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import os
import datetime
import importlib.util
import sys
from io import StringIO
import traceback
import uuid
import secrets


# Session storage
sessions = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456"

def check_session(request: Request):
    session_id = request.cookies.get("session_id")
    return session_id and session_id in sessions

def require_auth(request: Request = None):
    if request and not check_session(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True

app = FastAPI(title="API Management System")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database files
DB_FILE = "api_db.json"
LOG_FILE = "api_logs.json"

# Store dynamic routes
dynamic_routes = {}

# Load database
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {"apis": []}

# Save database
def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Load logs
def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            return json.load(f)
    return {"logs": []}

# Save logs
def save_logs(data):
    with open(LOG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.datetime.now()
    
    # Process request
    response = await call_next(request)
    
    # Skip logging for management endpoints, static files, and auth pages
    if (request.url.path.startswith("/api/manage") or 
        request.url.path.startswith("/static") or 
        request.url.path == "/" or 
        request.url.path == "/logs" or
        request.url.path == "/login" or
        request.url.path == "/logout"):
        return response
    
    # Get response body
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
    
    # Log the request
    log_entry = {
        "id": str(uuid.uuid4()),
        "timestamp": start_time.isoformat(),
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
        "headers": dict(request.headers),
        "client_ip": request.client.host if request.client else None,
        "status_code": response.status_code,
        "response_body": response_body.decode('utf-8', errors='ignore')[:1000],  # Limit size
        "response_time_ms": (datetime.datetime.now() - start_time).total_seconds() * 1000
    }
    
    logs = load_logs()
    logs["logs"].insert(0, log_entry)
    # Keep only last 1000 logs
    if len(logs["logs"]) > 1000:
        logs["logs"] = logs["logs"][:1000]
    save_logs(logs)
    
    return JSONResponse(
        content=json.loads(response_body.decode('utf-8', errors='ignore')) if response_body else {},
        status_code=response.status_code,
        headers=dict(response.headers)
    )

# API Models
class APIRequest(BaseModel):
    name: str
    path: str
    method: str = "GET"
    python_code: str
    description: Optional[str] = None

class APIUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    method: Optional[str] = None
    python_code: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None

# Execute Python code safely
def execute_python_code(code: str, request_data: Dict = None) -> Dict[str, Any]:
    """Execute Python code and return result"""
    output = StringIO()
    error_output = StringIO()
    result = None
    
    # Redirect stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        sys.stdout = output
        sys.stderr = error_output
        
        # Create execution context
        context = {
            "request_data": request_data or {},
            "json": json,
            "datetime": datetime,
            "result": None
        }
        
        # Execute code
        exec(code, context)
        
        # Get result if set
        result = context.get("result", "Code executed successfully")
        
    except Exception as e:
        error_output.write(str(e))
        error_output.write("\n")
        error_output.write(traceback.format_exc())
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    
    stdout_text = output.getvalue()
    stderr_text = error_output.getvalue()
    
    return {
        "result": result,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "success": len(stderr_text) == 0
    }

# Dynamic route handler
def create_dynamic_route(api_def: Dict):
    """Create a dynamic FastAPI route"""
    path = api_def["path"]
    method = api_def["method"].upper()
    code = api_def["python_code"]
    api_id = api_def["id"]
    
    async def dynamic_handler(request: Request):
        # Get request data
        request_data = {
            "path": str(request.url.path),
            "method": request.method,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
        }
        
        # Get body if POST/PUT/PATCH
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.json()
                request_data["body"] = body
            except:
                request_data["body"] = None
        
        # Execute Python code
        exec_result = execute_python_code(code, request_data)
        
        if exec_result["success"]:
            return JSONResponse(content={
                "result": exec_result["result"],
                "stdout": exec_result["stdout"]
            })
        else:
            return JSONResponse(
                content={
                    "error": exec_result["stderr"],
                    "stdout": exec_result["stdout"]
                },
                status_code=500
            )
    
    # Register route based on method
    if method == "GET":
        app.get(path)(dynamic_handler)
    elif method == "POST":
        app.post(path)(dynamic_handler)
    elif method == "PUT":
        app.put(path)(dynamic_handler)
    elif method == "DELETE":
        app.delete(path)(dynamic_handler)
    elif method == "PATCH":
        app.patch(path)(dynamic_handler)

# Load existing APIs
def load_apis():
    """Load and register all APIs from database"""
    db = load_db()
    for api in db["apis"]:
        if api.get("enabled", True):
            try:
                create_dynamic_route(api)
            except Exception as e:
                print(f"Error loading API {api['id']}: {e}")

# Management endpoints

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    with open("templates/login.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session_id = secrets.token_urlsafe(32)
        sessions[session_id] = {"username": username, "created_at": datetime.datetime.now().isoformat()}
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response
    else:
        with open("templates/login.html", "r") as f:
            html = f.read()
            error_html = "<div style=\"color: red; padding: 10px; background: #ffe6e6; border-radius: 4px; margin-bottom: 15px;\">Invalid username or password</div>"
            content = html.replace("<!-- ERROR -->", error_html)
            return HTMLResponse(content=content)

@app.get("/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, auth: bool = Depends(require_auth)):
    """Serve the main UI"""
    with open("templates/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, auth: bool = Depends(require_auth)):
    """Serve the logs page"""
    with open("templates/logs.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/manage/list")
async def list_apis(request: Request, auth: bool = Depends(require_auth)):
    """List all APIs"""
    db = load_db()
    return {"apis": db["apis"]}

@app.post("/api/manage/create")
async def create_api(api: APIRequest, request: Request, auth: bool = Depends(require_auth)):
    """Create a new API"""
    db = load_db()
    
    # Check if path already exists
    for existing in db["apis"]:
        if existing["path"] == api.path and existing["method"] == api.method:
            raise HTTPException(status_code=400, detail="API with this path and method already exists")
    
    # Create API
    api_def = {
        "id": str(uuid.uuid4()),
        "name": api.name,
        "path": api.path,
        "method": api.method.upper(),
        "python_code": api.python_code,
        "description": api.description,
        "enabled": True,
        "created_at": datetime.datetime.now().isoformat(),
        "updated_at": datetime.datetime.now().isoformat()
    }
    
    db["apis"].append(api_def)
    save_db(db)
    
    # Register route
    try:
        create_dynamic_route(api_def)
        return {"message": "API created successfully", "api": api_def}
    except Exception as e:
        return JSONResponse(
            content={"error": f"Failed to create route: {str(e)}"},
            status_code=500
        )

@app.put("/api/manage/{api_id}")
async def update_api(api_id: str, update: APIUpdate, request: Request, auth: bool = Depends(require_auth)):
    """Update an API"""
    db = load_db()
    
    # Find API
    api_def = None
    for i, api in enumerate(db["apis"]):
        if api["id"] == api_id:
            api_def = api
            break
    
    if not api_def:
        raise HTTPException(status_code=404, detail="API not found")
    
    # Update fields
    if update.name is not None:
        api_def["name"] = update.name
    if update.path is not None:
        api_def["path"] = update.path
    if update.method is not None:
        api_def["method"] = update.method.upper()
    if update.python_code is not None:
        api_def["python_code"] = update.python_code
    if update.description is not None:
        api_def["description"] = update.description
    if update.enabled is not None:
        api_def["enabled"] = update.enabled
    
    api_def["updated_at"] = datetime.datetime.now().isoformat()
    
    save_db(db)
    
    # Reload route
    # Note: FastAPI doesn't support route removal, so we need to restart
    return {"message": "API updated. Server restart required for changes.", "api": api_def}

@app.delete("/api/manage/{api_id}")
async def delete_api(api_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Delete an API"""
    db = load_db()
    
    # Find and remove API
    api_def = None
    for i, api in enumerate(db["apis"]):
        if api["id"] == api_id:
            api_def = api
            db["apis"].pop(i)
            break
    
    if not api_def:
        raise HTTPException(status_code=404, detail="API not found")
    
    save_db(db)
    
    return {"message": "API deleted. Server restart required."}

@app.post("/api/manage/{api_id}/toggle")
async def toggle_api(api_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Enable/disable an API"""
    db = load_db()
    
    api_def = None
    for api in db["apis"]:
        if api["id"] == api_id:
            api_def = api
            api["enabled"] = not api.get("enabled", True)
            break
    
    if not api_def:
        raise HTTPException(status_code=404, detail="API not found")
    
    save_db(db)
    return {"message": "API toggled. Server restart required.", "enabled": api_def["enabled"]}

@app.post("/api/manage/test")
async def test_code(request: APIRequest, req: Request, auth: bool = Depends(require_auth)):
    """Test Python code execution"""
    result = execute_python_code(request.python_code)
    return result

@app.get("/api/logs")
async def get_logs(limit: int = 100, request: Request = None, auth: bool = Depends(require_auth)):
    """Get API logs"""
    logs = load_logs()
    return {"logs": logs["logs"][:limit]}

@app.delete("/api/logs")
async def clear_logs(request: Request, auth: bool = Depends(require_auth)):
    """Clear all logs"""
    save_logs({"logs": []})
    return {"message": "Logs cleared"}

# Load APIs on startup
@app.on_event("startup")
async def startup_event():
    # Add /ping to database if not exists
    db = load_db()
    ping_exists = any(api.get("path") == "/ping" for api in db["apis"])
    if not ping_exists:
        ping_api = {
            "id": str(uuid.uuid4()),
            "name": "Ping",
            "path": "/ping",
            "method": "GET",
            "python_code": "result = {\"status\": \"ok\", \"service\": \"API Management System\"}",
            "description": "Health check endpoint",
            "enabled": True,
            "created_at": datetime.datetime.now().isoformat(),
            "updated_at": datetime.datetime.now().isoformat()
        }
        db["apis"].append(ping_api)
        save_db(db)
    load_apis()

# Default endpoints
@app.get("/ping")
async def ping():
    return {"status": "ok", "service": "API Management System"}
