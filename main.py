from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
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
import subprocess
import asyncio
import threading
import concurrent.futures
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool


# Session storage
sessions = {}
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123456"

def load_sessions():
    """Load sessions from PostgreSQL"""
    global sessions
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT session_id, username, created_at, expires_at FROM sessions WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP")
        rows = cur.fetchall()
        cur.close()
        sessions = {row[0]: {"username": row[1], "created_at": row[2].isoformat()} for row in rows}
    except Exception as e:
        print(f"Error loading sessions: {e}")
        sessions = {}
    finally:
        if conn:
            return_db_connection(conn)

def save_sessions():
    """Save sessions to PostgreSQL - kept for compatibility"""
    pass  # Sessions are saved individually

def save_session(session_id, username):
    """Save a single session to PostgreSQL"""
    global sessions
    conn = None
    try:
        from datetime import timedelta
        expires_at = datetime.datetime.now() + timedelta(days=30)
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (session_id, username, created_at, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (session_id) DO UPDATE
            SET expires_at = EXCLUDED.expires_at
        """, (session_id, username, datetime.datetime.now(), expires_at))
        conn.commit()
        cur.close()
        sessions[session_id] = {"username": username, "created_at": datetime.datetime.now().isoformat()}
    except Exception as e:
        print(f"Error saving session: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def delete_session(session_id):
    """Delete a session from PostgreSQL"""
    global sessions
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
        conn.commit()
        cur.close()
        if session_id in sessions:
            del sessions[session_id]
    except Exception as e:
        print(f"Error deleting session: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def check_session(request: Request):
    session_id = request.cookies.get("session_id")
    return session_id and session_id in sessions

def require_auth(request: Request):
    """Require authentication - raises HTTPException for API requests"""
    if not check_session(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return True

app = FastAPI(title="API Management System")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# PostgreSQL Database Configuration
DB_CONFIG = {
    'dbname': 'api_management',
    'user': 'api_user',
    'password': 'api_password_123',
    'host': 'localhost',
    'port': '5432'
}

# Connection pool for PostgreSQL
db_pool = None

def get_db_connection():
    """Get database connection from pool"""
    global db_pool
    if db_pool is None:
        db_pool = ThreadedConnectionPool(1, 20, **DB_CONFIG)
    return db_pool.getconn()

def return_db_connection(conn):
    """Return connection to pool"""
    if db_pool:
        db_pool.putconn(conn)

# Store dynamic routes
dynamic_routes = {}

# Load database (APIs)
def load_db():
    """Load APIs from PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM apis ORDER BY created_at DESC")
        apis = cur.fetchall()
        cur.close()
        # Convert to list of dicts
        return {"apis": [dict(api) for api in apis]}
    except Exception as e:
        print(f"Error loading database: {e}")
        return {"apis": []}
    finally:
        if conn:
            return_db_connection(conn)

# Save database (APIs) - now handled by individual operations
def save_db(data):
    """Save APIs to PostgreSQL - this is now handled by individual insert/update operations"""
    pass  # Individual operations handle saving

# Load logs
def load_logs():
    """Load logs from PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM api_logs ORDER BY timestamp DESC LIMIT 1000")
        logs = cur.fetchall()
        cur.close()
        # Convert to list of dicts and handle JSONB fields
        result_logs = []
        for log in logs:
            log_dict = dict(log)
            # Convert timestamp to ISO format string if it's a datetime object
            if isinstance(log_dict.get('timestamp'), datetime.datetime):
                log_dict['timestamp'] = log_dict['timestamp'].isoformat()
            # Parse JSONB fields if they're strings
            if isinstance(log_dict.get('query_params'), str):
                try:
                    log_dict['query_params'] = json.loads(log_dict['query_params'])
                except:
                    log_dict['query_params'] = {}
            if isinstance(log_dict.get('headers'), str):
                try:
                    log_dict['headers'] = json.loads(log_dict['headers'])
                except:
                    log_dict['headers'] = {}
            result_logs.append(log_dict)
        return {"logs": result_logs}
    except Exception as e:
        print(f"Error loading logs: {e}")
        return {"logs": []}
    finally:
        if conn:
            return_db_connection(conn)

# Save logs (individual log entry) - now handled by individual operations
def save_logs(data):
    """Save logs to PostgreSQL - this is now handled by individual insert/update operations"""
    pass  # Individual operations handle saving

def save_log_entry(log_entry):
    """Save a single log entry to PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO api_logs (
                id, timestamp, method, path, query_params, headers, client_ip,
                status_code, status, response_body, stdout, prints, response_time_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                status_code = EXCLUDED.status_code,
                status = EXCLUDED.status,
                response_body = EXCLUDED.response_body,
                stdout = EXCLUDED.stdout,
                prints = EXCLUDED.prints,
                response_time_ms = EXCLUDED.response_time_ms
        """, (
            log_entry['id'],
            datetime.datetime.fromisoformat(log_entry['timestamp']) if isinstance(log_entry['timestamp'], str) else log_entry['timestamp'],
            log_entry['method'],
            log_entry['path'],
            json.dumps(log_entry.get('query_params', {})),
            json.dumps(log_entry.get('headers', {})),
            log_entry.get('client_ip'),
            log_entry.get('status_code'),
            log_entry.get('status', 'completed'),
            log_entry.get('response_body', ''),
            log_entry.get('stdout', ''),
            log_entry.get('prints', ''),
            log_entry.get('response_time_ms', 0)
        ))
        conn.commit()
        cur.close()
        
        # Keep only last 1000 logs
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM api_logs
            WHERE id NOT IN (
                SELECT id FROM (
                    SELECT id FROM api_logs ORDER BY timestamp DESC LIMIT 1000
                ) AS keep_logs
            )
        """)
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error saving log entry: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def update_log_entry(log_id, updates):
    """Update a log entry in PostgreSQL"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        set_clauses = []
        params = []
        for key, value in updates.items():
            if key == 'query_params' or key == 'headers':
                set_clauses.append(f"{key} = %s")
                params.append(json.dumps(value) if isinstance(value, dict) else value)
            elif key == 'timestamp' and isinstance(value, str):
                set_clauses.append(f"{key} = %s")
                params.append(datetime.datetime.fromisoformat(value))
            else:
                set_clauses.append(f"{key} = %s")
                params.append(value)
        
        params.append(log_id)
        cur.execute(f"UPDATE api_logs SET {', '.join(set_clauses)} WHERE id = %s", params)
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating log entry: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.datetime.now()
    
    # Process request
    response = await call_next(request)
    
    path = request.url.path
    method = request.method
    
    # Skip logging for system endpoints, static files, and auth pages
    excluded_paths = [
        "/api/manage",  # Management APIs
        "/api/logs",    # Logs API
        "/static",      # Static files
        "/",            # Dashboard
        "/logs",        # Logs page
        "/login",       # Login page
        "/logout",      # Logout
        "/ping",        # Ping endpoint
    ]
    
    # Check if path should be excluded
    should_exclude = False
    for excluded in excluded_paths:
        if path.startswith(excluded):
            should_exclude = True
            break
    
    if should_exclude:
        return response
    
    # Skip middleware logging for user-created APIs (they log themselves in the handler)
    # Check if path matches any API in database
    db = load_db()
    is_user_api = False
    
    for api in db.get("apis", []):
        api_path = api.get("path", "")
        api_method = api.get("method", "").upper()
        # Match path and method exactly
        if api_path == path and api_method == method.upper():
            # Skip /ping endpoint
            if api_path == "/ping":
                break
            # Check if it's a user API
            if api.get("enabled", True):
                is_user_api = True
                break
    
    # Skip middleware logging for user APIs (they handle their own logging)
    if is_user_api:
        return response
    
    # Read response body
    try:
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Decode response body for logging
        try:
            response_body_text = response_body.decode('utf-8', errors='ignore')[:1000]
            response_body_json = json.loads(response_body_text) if response_body_text else {}
        except:
            response_body_text = response_body.decode('utf-8', errors='ignore')[:1000]
            response_body_json = {}
        
        # Log the request
        log_entry = {
            "id": str(uuid.uuid4()),
            "timestamp": start_time.isoformat(),
            "method": method,
            "path": path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
            "status_code": response.status_code,
            "response_body": response_body_text,
            "response_time_ms": (datetime.datetime.now() - start_time).total_seconds() * 1000
        }
        
        # Save log entry to PostgreSQL
        save_log_entry(log_entry)
        
        # Return the response with the same body
        return JSONResponse(
            content=response_body_json,
            status_code=response.status_code,
            headers=dict(response.headers)
        )
    except Exception as e:
        # If logging fails, just return the original response
        import traceback
        print(f"Error in logging middleware: {e}")
        print(traceback.format_exc())
        return response

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

# Custom StringIO that updates logs in real-time
class LoggingStringIO(StringIO):
    def __init__(self, log_id=None):
        super().__init__()
        self.log_id = log_id
        self.lock = threading.Lock()
        self.last_update_time = 0
    
    def write(self, s):
        super().write(s)
        # Update log entry with stdout in real-time
        if self.log_id and s:  # Only update if we have content
            try:
                import time
                current_time = time.time()
                # Update more frequently for real-time feel (every 50ms or immediately for non-empty content)
                should_update = (current_time - self.last_update_time) > 0.05 or len(s.strip()) > 0
                
                if should_update:
                    # Update prints in PostgreSQL directly using atomic append with proper locking
                    conn = None
                    try:
                        with self.lock:  # Use lock to prevent race conditions and ensure ordering
                            conn = get_db_connection()
                            cur = conn.cursor()
                            
                            # Lock the row and get current prints in one atomic operation
                            cur.execute("SELECT prints FROM api_logs WHERE id = %s FOR UPDATE", (self.log_id,))
                            row = cur.fetchone()
                            current_prints = row[0] if row and row[0] else ""
                            
                            # Process string to ensure each print statement is on its own line
                            processed_s = s
                            
                            # If current prints doesn't end with newline and we have new content, add separator
                            if current_prints and not current_prints.rstrip().endswith('\n') and s.strip():
                                processed_s = '\n' + s
                            
                            # Ensure each non-empty print statement ends with newline for readability
                            if processed_s.strip() and not processed_s.endswith('\n'):
                                processed_s = processed_s + '\n'
                            
                            # Use PostgreSQL's atomic string concatenation to append (ensures ordering)
                            cur.execute("UPDATE api_logs SET prints = COALESCE(prints, '') || %s WHERE id = %s", 
                                      (processed_s, self.log_id))
                            conn.commit()
                            cur.close()
                            self.last_update_time = current_time
                    except Exception as e:
                        print(f"Error updating prints in log: {e}")
                        import traceback
                        traceback.print_exc()
                        if conn:
                            conn.rollback()
                    finally:
                        if conn:
                            return_db_connection(conn)
            except Exception as e:
                pass  # Don't fail if logging fails

# Execute Python code safely
def execute_python_code(code: str, request_data: Dict = None, log_id: str = None) -> Dict[str, Any]:
    """Execute Python code and return result"""
    output = LoggingStringIO(log_id=log_id)
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
        
        # Execute code with unbuffered output for real-time prints
        import builtins
        original_print = builtins.print
        
        def print_with_flush(*args, **kwargs):
            """Custom print that flushes immediately"""
            original_print(*args, **kwargs)
            if hasattr(sys.stdout, 'flush'):
                sys.stdout.flush()
        
        builtins.print = print_with_flush
        
        try:
            exec(code, context)
        finally:
            # Restore original print
            builtins.print = original_print
        
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
        
        # Create log entry and return immediately
        start_time = datetime.datetime.now()
        log_id = str(uuid.uuid4())
        
        # Create initial log entry showing execution started
        try:
            log_entry = {
                "id": log_id,
                "timestamp": start_time.isoformat(),
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "headers": dict(request.headers),
                "client_ip": request.client.host if request.client else None,
                "status_code": None,  # Will be updated when complete
                "status": "executing",  # executing, completed, error
                "response_body": "",
                "stdout": "",  # Print statements will go here (for backward compatibility)
                "prints": "",  # Separate field for real-time print statements display
                "response_time_ms": 0
            }
            
            # Save log entry to PostgreSQL
            save_log_entry(log_entry)
        except Exception as e:
            print(f"Error creating log entry: {e}")
        
        # Execute code in background thread but wait for result
        def execute_in_thread():
            try:
                exec_result = execute_python_code(code, request_data, log_id=log_id)
                response_time = (datetime.datetime.now() - start_time).total_seconds() * 1000
                
                # Update log entry with results (for logging only, not in API response)
                response_body = json.dumps({
                    "result": exec_result.get("result"),
                    "error": exec_result.get("stderr") if not exec_result["success"] else None
                }, default=str)[:1000]
                
                # Update log entry in PostgreSQL
                update_log_entry(log_id, {
                    "status_code": 200 if exec_result["success"] else 500,
                    "status": "completed" if exec_result["success"] else "error",
                    "response_body": response_body,
                    "stdout": exec_result.get("stdout", ""),
                    "response_time_ms": response_time
                })
                
                # Ensure prints field is set if not already updated
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT prints FROM api_logs WHERE id = %s", (log_id,))
                row = cur.fetchone()
                if row and (not row[0] or row[0].strip() == ""):
                    cur.execute("UPDATE api_logs SET prints = %s WHERE id = %s", 
                               (exec_result.get("stdout", ""), log_id))
                    conn.commit()
                cur.close()
                return_db_connection(conn)
                return exec_result, response_time
            except Exception as e:
                print(f"Error in background execution: {e}")
                # Update log with error
                try:
                    update_log_entry(log_id, {
                        "status_code": 500,
                        "status": "error",
                        "response_body": json.dumps({"error": str(e)}, default=str)
                    })
                except:
                    pass
                return None, 0
        
        # Execute in thread pool executor (non-blocking for other requests, but wait for this one)
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        try:
            exec_result, response_time = await loop.run_in_executor(executor, execute_in_thread)
        finally:
            executor.shutdown(wait=False)
        
        # Return the actual result when execution completes
        if exec_result and exec_result["success"]:
            return JSONResponse(content={
                "result": exec_result["result"]
            })
        elif exec_result:
            return JSONResponse(
                content={
                    "error": exec_result["stderr"]
                },
                status_code=500
            )
        else:
            return JSONResponse(
                content={"error": "Execution failed"},
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
        save_session(session_id, username)  # Save session to PostgreSQL
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=86400*30)  # 30 days
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
    if session_id:
        delete_session(session_id)  # Delete session from PostgreSQL
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_id")
    return response

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main UI"""
    if not check_session(request):
        return RedirectResponse(url="/login", status_code=303)
    with open("templates/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Serve the logs page"""
    if not check_session(request):
        return RedirectResponse(url="/login", status_code=303)
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
    conn = None
    try:
        # Check if path already exists
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM apis WHERE path = %s AND method = %s", (api.path, api.method.upper()))
        if cur.fetchone():
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=400, detail="API with this path and method already exists")
        
        # Create API
        api_id = str(uuid.uuid4())
        now = datetime.datetime.now()
        api_def = {
            "id": api_id,
            "name": api.name,
            "path": api.path,
            "method": api.method.upper(),
            "python_code": api.python_code,
            "description": api.description,
            "enabled": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        # Insert into PostgreSQL
        cur.execute("""
            INSERT INTO apis (id, name, path, method, python_code, description, enabled, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            api_id, api.name, api.path, api.method.upper(), api.python_code,
            api.description, True, now, now
        ))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        # Register route
        try:
            create_dynamic_route(api_def)
            return {"message": "API created successfully", "api": api_def}
        except Exception as e:
            return JSONResponse(
                content={"error": f"Failed to create route: {str(e)}"},
                status_code=500
            )
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            return_db_connection(conn)
        return JSONResponse(
            content={"error": f"Failed to create API: {str(e)}"},
            status_code=500
        )

@app.put("/api/manage/{api_id}")
async def update_api(api_id: str, update: APIUpdate, request: Request, auth: bool = Depends(require_auth)):
    """Update an API"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find API
        cur.execute("SELECT * FROM apis WHERE id = %s", (api_id,))
        api_row = cur.fetchone()
        if not api_row:
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="API not found")
        
        api_def = dict(api_row)
        
        # Build update query
        updates = []
        params = []
        if update.name is not None:
            updates.append("name = %s")
            params.append(update.name)
            api_def["name"] = update.name
        if update.path is not None:
            updates.append("path = %s")
            params.append(update.path)
            api_def["path"] = update.path
        if update.method is not None:
            updates.append("method = %s")
            params.append(update.method.upper())
            api_def["method"] = update.method.upper()
        if update.python_code is not None:
            updates.append("python_code = %s")
            params.append(update.python_code)
            api_def["python_code"] = update.python_code
        if update.description is not None:
            updates.append("description = %s")
            params.append(update.description)
            api_def["description"] = update.description
        if update.enabled is not None:
            updates.append("enabled = %s")
            params.append(update.enabled)
            api_def["enabled"] = update.enabled
        
        updates.append("updated_at = %s")
        params.append(datetime.datetime.now())
        params.append(api_id)
        
        # Execute update
        cur.execute(f"UPDATE apis SET {', '.join(updates)} WHERE id = %s", params)
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        api_def["updated_at"] = datetime.datetime.now().isoformat()
        
        # Reload route
        # Note: FastAPI doesn't support route removal, so we need to restart
        return {"message": "API updated. Server restart required for changes.", "api": api_def}
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            return_db_connection(conn)
        raise HTTPException(status_code=500, detail=f"Failed to update API: {str(e)}")

@app.delete("/api/manage/{api_id}")
async def delete_api(api_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Delete an API"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find API
        cur.execute("SELECT * FROM apis WHERE id = %s", (api_id,))
        api_row = cur.fetchone()
        if not api_row:
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="API not found")
        
        # Delete API
        cur.execute("DELETE FROM apis WHERE id = %s", (api_id,))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        
        return {"message": "API deleted. Server restart required."}
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            return_db_connection(conn)
        raise HTTPException(status_code=500, detail=f"Failed to delete API: {str(e)}")

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

@app.get("/api/logs/stream")
async def stream_logs(request: Request, auth: bool = Depends(require_auth)):
    """Stream logs in real-time using Server-Sent Events"""
    import asyncio
    import time
    
    async def event_generator():
        last_count = 0
        last_executing_ids = set()
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            logs = load_logs()
            current_count = len(logs.get("logs", []))
            
            # Send update if logs changed
            if current_count != last_count:
                yield f"data: {json.dumps({'logs': logs['logs'][:100], 'count': current_count})}\n\n"
                last_count = current_count
            
            # Always send updates for executing logs to show real-time prints
            executing_logs = [log for log in logs.get("logs", []) if log.get("status") == "executing"]
            current_executing_ids = {log.get("id") for log in executing_logs}
            
            # Send update if there are executing logs (always refresh to show latest prints)
            if executing_logs:
                yield f"data: {json.dumps({'executing': executing_logs})}\n\n"
                last_executing_ids = current_executing_ids
            elif last_executing_ids:
                # No longer executing, clear the set
                last_executing_ids = set()
            
            await asyncio.sleep(0.1)  # Check every 100ms for faster real-time updates
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.delete("/api/logs")
async def clear_logs(request: Request, auth: bool = Depends(require_auth)):
    """Clear all logs"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE api_logs")
        conn.commit()
        cur.close()
        return_db_connection(conn)
        return {"message": "Logs cleared"}
    except Exception as e:
        if conn:
            conn.rollback()
            return_db_connection(conn)
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {str(e)}")

@app.post("/api/manage/restart")
async def restart_server(request: Request, auth: bool = Depends(require_auth)):
    """Restart the FastAPI server"""
    try:
        # Get the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        restart_script = os.path.join(script_dir, "restart_server.sh")
        
        # Execute restart script in background
        subprocess.Popen(
            ["/bin/bash", restart_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=script_dir
        )
        
        return {"message": "Server restart initiated", "status": "success"}
    except Exception as e:
        return JSONResponse(
            content={"error": str(e), "status": "error"},
            status_code=500
        )

# Load APIs on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database connections and load sessions on startup"""
    load_sessions()
    # Test database connection
    try:
        conn = get_db_connection()
        return_db_connection(conn)
        print("Database connection successful")
    except Exception as e:
        print(f"Warning: Database connection failed: {e}")
    
    # Original startup code:
    # Load sessions from file
    load_sessions()
    
    # Add /ping to database if not exists
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM apis WHERE path = %s AND method = %s", ("/ping", "GET"))
        if not cur.fetchone():
            ping_id = str(uuid.uuid4())
            now = datetime.datetime.now()
            cur.execute("""
                INSERT INTO apis (id, name, path, method, python_code, description, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                ping_id, "Ping", "/ping", "GET",
                'result = {"status": "ok", "service": "API Management System"}',
                "Health check endpoint", True, now, now
            ))
            conn.commit()
        cur.close()
        return_db_connection(conn)
    except Exception as e:
        print(f"Error checking/creating ping API: {e}")
        if conn:
            return_db_connection(conn)
    
    load_apis()

# Default endpoints
@app.get("/ping")
async def ping():
    return {"status": "ok", "service": "API Management System"}
