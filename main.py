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
import requests
import smtplib
from email.message import EmailMessage
from fastapi import BackgroundTasks


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

# Global background task queue
background_task_queue = []

# === BACKGROUND JOB TRACKING FUNCTIONS ===
def add_progress_log(job_id: str, message: str, log_level: str = "info", step_number: int = None):
    """Add a progress log entry for a background job"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO job_progress_logs (job_id, log_level, message, step_number)
            VALUES (%s, %s, %s, %s)
        """, (job_id, log_level, message, step_number))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error adding progress log: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def update_job_status(job_id: str, status: str, error_message: str = None, result_summary: str = None):
    """Update the status of a background job"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if status == "completed":
            cur.execute("""
                UPDATE background_jobs 
                SET status = %s, completed_at = %s, result_summary = %s
                WHERE id = %s
            """, (status, datetime.datetime.now(), result_summary, job_id))
        elif status == "failed":
            cur.execute("""
                UPDATE background_jobs 
                SET status = %s, completed_at = %s, error_message = %s
                WHERE id = %s
            """, (status, datetime.datetime.now(), error_message, job_id))
        else:
            cur.execute("""
                UPDATE background_jobs 
                SET status = %s
                WHERE id = %s
            """, (status, job_id))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Error updating job status: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            return_db_connection(conn)

def check_job_running(job_type: str) -> bool:
    """Check if a job of this type is currently running"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM background_jobs 
            WHERE job_type = %s AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """, (job_type,))
        result = cur.fetchone()
        cur.close()
        return result is not None
    except Exception as e:
        print(f"Error checking job status: {e}")
        return False
    finally:
        if conn:
            return_db_connection(conn)

# Background job helper functions (available in Python code execution context)
def start_background_job(job_type: str, job_function):
    """Start a background job - available in Python code execution context"""
    global background_task_queue
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Atomic check-and-create: Check if running and create in one transaction
        # First, try to find a running job
        cur.execute("""
            SELECT id FROM background_jobs 
            WHERE job_type = %s AND status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
            FOR UPDATE
        """, (job_type,))
        existing_job = cur.fetchone()
        
        if existing_job:
            cur.close()
            return_db_connection(conn)
            conn = None
            return {"status": "already_running", "message": f"{job_type} already started"}
        
        # Create new job atomically
        job_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO background_jobs (id, job_type, status, started_at)
            VALUES (%s, %s, %s, %s)
        """, (job_id, job_type, "running", datetime.datetime.now()))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        conn = None
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
            try:
                return_db_connection(conn)
            except:
                pass
            conn = None
        return {"status": "error", "message": f"Failed to create job: {str(e)}"}
    finally:
        if conn:
            try:
                return_db_connection(conn)
            except:
                pass
    
    # Schedule background execution
    def run_job():
        try:
            job_function(job_id)
        except Exception as e:
            update_job_status(job_id, "failed", error_message=str(e))
    
    # Start in background thread
    thread = threading.Thread(target=run_job, daemon=True)
    thread.start()
    background_task_queue.append(thread)
    
    return {"status": "started", "job_id": job_id, "message": f"{job_type} started"}

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
        
        # ===== Clean up protobuf modules in thread context to avoid conflicts =====
        # This is critical when code executes in threads and protobuf modules
        # might already be loaded in the main process
        # IMPORTANT: Only remove protobuf/rpc modules, NOT google.generativeai modules
        # Removing generativeai breaks the package structure
        import importlib
        import gc
        
        # Only remove protobuf and rpc modules, NOT generativeai
        modules_to_remove = []
        for module_name in list(sys.modules.keys()):
            if any(module_name.startswith(prefix) for prefix in [
                'google.protobuf',
                'google.rpc',
                'google._upb',
                'google._message'
            ]) and not module_name.startswith('google.generativeai'):
                modules_to_remove.append(module_name)
        
        # Remove modules in reverse order (dependencies first)
        for mod in sorted(modules_to_remove, reverse=True):
            if mod in sys.modules:
                try:
                    # Clear any references
                    module_obj = sys.modules[mod]
                    if hasattr(module_obj, '__dict__'):
                        module_obj.__dict__.clear()
                    del sys.modules[mod]
                except:
                    pass
        
        # Force garbage collection to clean up references
        gc.collect()
        
        # Invalidate import caches to ensure fresh imports
        try:
            importlib.invalidate_caches()
        except:
            pass
        # ===== End protobuf cleanup =====
        
        # Create execution context with helper functions
        context = {
            "request_data": request_data or {},
            "json": json,
            "datetime": datetime,
            "result": None,
            "start_background_job": start_background_job,
            "add_progress_log": add_progress_log,
            "update_job_status": update_job_status,
            "check_job_running": check_job_running,
            "threading": threading,
            "asyncio": asyncio,
            "requests": requests,
            "smtplib": smtplib,
            "EmailMessage": EmailMessage,
            "psycopg2": psycopg2,
            "traceback": traceback
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
        except Exception as exec_error:
            # If execution fails, capture the error
            error_output.write(f"Execution error: {str(exec_error)}\n")
            error_output.write(traceback.format_exc())
            # Don't set result here, let it be handled below
        finally:
            # Restore original print
            builtins.print = original_print
        
        # Get result if set
        result = context.get("result")
        # If result is None or not set, provide a default
        if result is None:
            # Check if result was ever set in context
            if "result" not in context:
                # Result was never set - code didn't execute result assignment
                result = {"message": "Code executed but did not set result variable", "warning": "Code may be incomplete"}
            else:
                # Result was explicitly set to None - this shouldn't happen with our code
                stdout_text_preview = output.getvalue()[:500] if hasattr(output, 'getvalue') else ""
                result = {"message": "Code executed but result was None", "warning": "Check code execution", "stdout_preview": stdout_text_preview}
        
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
            api_result = exec_result.get("result")
            # If result is None, provide a default message
            if api_result is None:
                api_result = {"message": "API executed successfully but returned no result"}
            return JSONResponse(content={
                "result": api_result
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

# === BACKGROUND JOBS API ENDPOINTS ===
@app.get("/api/background-jobs/list")
async def list_background_jobs(request: Request, auth: bool = Depends(require_auth)):
    """List all background jobs"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, job_type, status, started_at, completed_at, error_message, result_summary
            FROM background_jobs
            ORDER BY started_at DESC
            LIMIT 100
        """)
        jobs = cur.fetchall()
        cur.close()
        return {"jobs": [dict(job) for job in jobs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting jobs: {str(e)}")
    finally:
        if conn:
            return_db_connection(conn)

@app.delete("/api/background-jobs/{job_id}")
async def delete_background_job(job_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Delete a background job and all its logs"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Verify job exists
        cur.execute("SELECT id FROM background_jobs WHERE id = %s", (job_id,))
        if not cur.fetchone():
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Delete job (logs will be deleted automatically due to CASCADE)
        cur.execute("DELETE FROM background_jobs WHERE id = %s", (job_id,))
        conn.commit()
        cur.close()
        return_db_connection(conn)
        conn = None
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={"message": "Job and all its logs deleted successfully"}
        )
    except HTTPException:
        if conn:
            try:
                return_db_connection(conn)
            except:
                pass
        raise
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except:
                pass
            try:
                return_db_connection(conn)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error deleting job: {str(e)}")

@app.get("/api/background-jobs/{job_id}/logs")
async def get_job_logs(job_id: str, limit: int = 1000, request: Request = None, auth: bool = Depends(require_auth)):
    """Get logs for a specific background job"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify job exists
        cur.execute("SELECT id FROM background_jobs WHERE id = %s", (job_id,))
        if not cur.fetchone():
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get logs
        cur.execute("""
            SELECT id, timestamp, log_level, message, step_number
            FROM job_progress_logs
            WHERE job_id = %s
            ORDER BY timestamp ASC, step_number ASC
            LIMIT %s
        """, (job_id, limit))
        logs = cur.fetchall()
        cur.close()
        
        return {
            "job_id": job_id,
            "logs": [dict(log) for log in logs]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting logs: {str(e)}")
    finally:
        if conn:
            return_db_connection(conn)

@app.get("/api/background-jobs/{job_id}/logs/stream")
async def stream_job_logs(job_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Stream logs for a specific background job in real-time using Server-Sent Events"""
    import asyncio
    
    # Verify job exists
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM background_jobs WHERE id = %s", (job_id,))
        if not cur.fetchone():
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="Job not found")
        cur.close()
        return_db_connection(conn)
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            return_db_connection(conn)
        raise HTTPException(status_code=500, detail=f"Error verifying job: {str(e)}")
    
    async def event_generator():
        last_log_id = None
        error_count = 0
        max_errors = 10
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            try:
                conn = get_db_connection()
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # Get new logs since last check
                if last_log_id:
                    cur.execute("""
                        SELECT id, timestamp, log_level, message, step_number
                        FROM job_progress_logs
                        WHERE job_id = %s AND id > %s
                        ORDER BY timestamp ASC, step_number ASC
                    """, (job_id, last_log_id))
                else:
                    # First time - get all logs
                    cur.execute("""
                        SELECT id, timestamp, log_level, message, step_number
                        FROM job_progress_logs
                        WHERE job_id = %s
                        ORDER BY timestamp ASC, step_number ASC
                    """, (job_id,))
                
                new_logs = cur.fetchall()
                cur.close()
                return_db_connection(conn)
                conn = None
                
                # Reset error count on success
                error_count = 0
                
                # Send new logs
                if new_logs:
                    logs_data = [dict(log) for log in new_logs]
                    # Update last_log_id to the last log's id
                    last_log_id = logs_data[-1].get('id')
                    
                    yield f"data: {json.dumps({'logs': logs_data})}\n\n"
                else:
                    # Send keep-alive ping to prevent connection timeout
                    yield f": keep-alive\n\n"
                
                # Check if job is still running
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT status FROM background_jobs WHERE id = %s", (job_id,))
                job_status = cur.fetchone()
                cur.close()
                return_db_connection(conn)
                conn = None
                
                if job_status and job_status[0] not in ['running']:
                    # Job completed or failed, send final update and close
                    yield f"data: {json.dumps({'status': 'completed', 'job_status': job_status[0]})}\n\n"
                    break
                
            except Exception as e:
                error_count += 1
                print(f"Error in log stream: {e}")
                
                # Send error but don't break unless too many errors
                try:
                    yield f"data: {json.dumps({'error': str(e), 'error_count': error_count})}\n\n"
                except:
                    pass
                
                if error_count >= max_errors:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Too many errors, closing connection'})}\n\n"
                    break
                
                # Clean up connection on error
                if conn:
                    try:
                        return_db_connection(conn)
                    except:
                        pass
                    conn = None
            
            await asyncio.sleep(0.5)  # Check every 500ms for real-time updates
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/background-jobs/{job_id}/stop")
async def stop_background_job(job_id: str, request: Request, auth: bool = Depends(require_auth)):
    """Stop a running background job"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get job info
        cur.execute("""
            SELECT id, job_type, status FROM background_jobs WHERE id = %s
        """, (job_id,))
        job = cur.fetchone()
        
        if not job:
            cur.close()
            return_db_connection(conn)
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_dict = dict(job)
        
        if job_dict["status"] != "running":
            cur.close()
            return_db_connection(conn)
            return JSONResponse(content={"message": f"Job is not running (status: {job_dict['status']})", "status": job_dict["status"]})
        
        # Update job status to cancelled
        cur.execute("""
            UPDATE background_jobs 
            SET status = 'failed', completed_at = %s, error_message = %s
            WHERE id = %s
        """, (datetime.datetime.now(), "Job stopped by user", job_id))
        conn.commit()
        
        # Add log entry
        add_progress_log(job_id, "Job stopped by user", "warning")
        
        cur.close()
        return_db_connection(conn)
        
        return JSONResponse(content={"message": "Job stop request processed", "job_id": job_id})
    except HTTPException:
        raise
    except Exception as e:
        if conn:
            conn.rollback()
            return_db_connection(conn)
        raise HTTPException(status_code=500, detail=f"Error stopping job: {str(e)}")
    finally:
        if conn:
            return_db_connection(conn)

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
    
    # Add utilization sync API to database if not exists
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM apis WHERE path = %s AND method = %s", ("/api/utilization/sync", "POST"))
        if not cur.fetchone():
            utilization_sync_code = '''# Utilization Sync API - Runs in background
job_type = "utilization_sync"

# Configuration
DB_HOST = "odoo-marketing-cluster-instance-1.cvm3ri1wjhhb.us-east-1.rds.amazonaws.com"
DB_NAME = "beyond"
DB_USER = "odoo"
DB_PASSWORD = "PBLBOIq9HR0YVslM"
EMAIL_SENDER = "emaiiiltestt@gmail.com"
EMAIL_PASSWORD = "hkll zhrd zoia noos"
EMAIL_RECEIVER = "utilization@beyond-solution.com"
TOKEN_URL = "https://api-third-party.beyond-solution.com/api/v1/obtain-service-token"
BQ_URL = "https://bigquery.googleapis.com/bigquery/v2/projects/beyond-438113/queries"
BATCH_SIZE = 10000

def run_utilization_sync(job_id):
    """Run the utilization sync process"""
    def send_email(subject, body):
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = EMAIL_SENDER
            msg["To"] = EMAIL_RECEIVER
            msg.set_content(body)
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
                smtp.send_message(msg)
        except Exception as e:
            add_progress_log(job_id, f"Error sending email: {e}", "error")
    
    try:
        add_progress_log(job_id, "Utilization update process started", "info", 1)
        send_email("Utilization Update Started", "The utilization update process has started...")
        
        # Get token from TOKEN_URL (original logic - no bearer token needed)
        add_progress_log(job_id, "Fetching authentication token from TOKEN_URL...", "info", 2)
        response = requests.get(TOKEN_URL)
        response.raise_for_status()
        token = response.json().get("token")
        add_progress_log(job_id, "Token received successfully", "success", 3)
        
        # Connect to DB
        add_progress_log(job_id, "Connecting to PostgreSQL database...", "info", 4)
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        add_progress_log(job_id, "Connected to database successfully", "success", 5)
        
        # Delete old data
        add_progress_log(job_id, "Deleting existing records from custom_policy_utilization...", "info", 6)
        cur.execute("DELETE FROM custom_policy_utilization;")
        conn.commit()
        add_progress_log(job_id, "Old data cleared", "success", 7)
        
        # Load valid policy IDs
        add_progress_log(job_id, "Loading valid policy IDs from custom_policy...", "info", 8)
        cur.execute("SELECT id FROM custom_policy;")
        valid_policy_ids = {str(row[0]) for row in cur.fetchall()}
        add_progress_log(job_id, f"Loaded {len(valid_policy_ids)} valid policy IDs", "success", 9)
        
        def escape_sql_value(val):
            if isinstance(val, str):
                return "'" + val.replace("'", "''") + "'"
            elif val is None:
                return 'NULL'
            else:
                return str(val)
        
        columns = [
            'policy_id', 'tpa', 'account', 'claim_date', 'member_id',
            'member_name', 'relation', 'age', 'chronic', 'disease_category',
            'provider', 'provider_type', 'claim_id', 'show_button', 'amount',
            'risk_carrier', 'month', 'services_group', 'icd_code', 'disease',
            'total_amount', '"order"'
        ]
        
        # Use fetched token for BigQuery requests
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        query_body = {
            "query": "SELECT * FROM `beyond-438113.Utlization.Utilization_Data`",
            "useLegacySql": False,
            "maxResults": BATCH_SIZE
        }
        
        page_token = None
        total_records_bq = 0
        total_inserted_records = 0
        total_neglected_records = 0
        neglected_policies = {}
        batch_number = 0
        
        # Fetch + Insert loop
        while True:
            batch_number += 1
            if page_token:
                query_body["pageToken"] = page_token
            else:
                query_body.pop("pageToken", None)
            
            add_progress_log(job_id, f"Fetching batch #{batch_number} from BigQuery...", "info", 10 + batch_number)
            response = requests.post(BQ_URL, headers=headers, json=query_body)
            response.raise_for_status()
            data = response.json()
            
            rows = data.get("rows", [])
            if not rows:
                add_progress_log(job_id, "No more rows to process. Completed successfully.", "success")
                break
            
            schema = [f["name"] for f in data["schema"]["fields"]]
            records = [dict(zip(schema, [c["v"] for c in row["f"]])) for row in rows]
            
            values_sql = []
            batch_insert_count = 0
            
            for r in records:
                total_records_bq += 1
                raw_policy_id = r.get("Odoo_id")
                policy_id_str = str(raw_policy_id) if raw_policy_id is not None else None
                
                if not policy_id_str or policy_id_str not in valid_policy_ids:
                    total_neglected_records += 1
                    key = policy_id_str or "NULL"
                    if key not in neglected_policies:
                        neglected_policies[key] = {
                            "odoo_ref": r.get("Odoo_Ref"),
                            "count": 1,
                        }
                    else:
                        neglected_policies[key]["count"] += 1
                    continue
                
                row = [
                    raw_policy_id,
                    r.get("TPA", ""),
                    r.get("ACCOUNT", ""),
                    r.get("CLAIM_DATE", ""),
                    r.get("MEMBER_ID", ""),
                    r.get("MEMBER_NAME", ""),
                    r.get("RELATION", ""),
                    int(r.get("AGE", 0) or 0),
                    r.get("CHRONIC", ""),
                    r.get("Disease_category", ""),
                    r.get("PROVIDER", ""),
                    r.get("Provider_Type", ""),
                    r.get("CLAIM_ID", ""),
                    False,
                    float(r.get("TOTAL_AMOUNT") or 0),
                    r.get("RISK_CARRIER", ""),
                    r.get("MONTH", ""),
                    r.get("SERVICES_GROUP", ""),
                    r.get("ICD_CODE", ""),
                    r.get("DISEASE", ""),
                    float(r.get("TOTAL_AMOUNT") or 0),
                    "Auto"
                ]
                
                escaped = [escape_sql_value(v) for v in row]
                values_sql.append(f"({', '.join(escaped)})")
                batch_insert_count += 1
            
            if values_sql:
                insert_query = f"""
                    INSERT INTO custom_policy_utilization (
                        {', '.join(columns)}
                    ) VALUES 
                    {", ".join(values_sql)};
                """
                try:
                    add_progress_log(job_id, f"Inserting {batch_insert_count} records from batch #{batch_number}...", "info")
                    cur.execute(insert_query)
                    conn.commit()
                    total_inserted_records += batch_insert_count
                    add_progress_log(job_id, f"Inserted batch #{batch_number}. Total inserted: {total_inserted_records}", "success")
                except Exception as e:
                    add_progress_log(job_id, f"Error during insert batch #{batch_number}: {e}", "error")
                    conn.rollback()
            
            page_token = data.get("pageToken")
            if not page_token:
                add_progress_log(job_id, "Finished processing all batches.", "success")
                break
        
        # Cleanup
        cur.close()
        conn.close()
        
        total_neglected_unique_ids = len(neglected_policies)
        
        # Build summary
        summary_lines = []
        summary_lines.append("Utilization Sync Summary")
        summary_lines.append("====================================")
        summary_lines.append(f"Total records in BigQuery: {total_records_bq}")
        summary_lines.append(f"Total inserted records in Odoo: {total_inserted_records}")
        summary_lines.append(f"Total neglected records from BigQuery (policy not found in Odoo): {total_neglected_records}")
        summary_lines.append(f"Total neglected unique Odoo_id values: {total_neglected_unique_ids}")
        summary_lines.append("")
        summary_lines.append("Neglected policy IDs (Odoo_id) with Odoo_Ref and neglected row count:")
        summary_lines.append("Odoo_id | Odoo_Ref | Neglected_Rows")
        summary_lines.append("------------------------------------")
        for policy_id_str, info in neglected_policies.items():
            odoo_ref = info.get("odoo_ref")
            count = info.get("count", 0)
            summary_lines.append(f"{policy_id_str} | {odoo_ref} | {count}")
        
        summary_text = "\\n".join(summary_lines)
        add_progress_log(job_id, summary_text, "info")
        add_progress_log(job_id, "Process completed successfully", "success")
        
        send_email("Utilization Update Done", summary_text)
        update_job_status(job_id, "completed", result_summary=summary_text)
        
    except Exception as e:
        error_msg = f"Error in utilization sync: {str(e)}\\n{traceback.format_exc()}"
        add_progress_log(job_id, error_msg, "error")
        update_job_status(job_id, "failed", error_message=error_msg)
        send_email("Utilization Update Failed", error_msg)
    
# Start background job (this function checks if already running internally)
# Initialize result with a default dict - never None
result = {"status": "pending", "message": "Initializing"}

try:
    # Call start_background_job and ensure we get a result
    job_result = start_background_job(job_type, run_utilization_sync)
    
    # If already running, return that message, otherwise return the job result
    if job_result and isinstance(job_result, dict) and job_result.get("status") == "already_running":
        result = {"message": "Utilization update already started", "status": "running"}
    elif job_result and isinstance(job_result, dict):
        result = job_result
    else:
        # Fallback if job_result is None or empty
        result = {"message": "Utilization update started", "status": "started", "note": "job_result was invalid", "job_result_received": str(job_result)}
except Exception as e:
    # Ensure result is always set even if there's an error
    import traceback
    error_trace = traceback.format_exc()
    result = {"message": f"Error starting utilization update: {str(e)}", "status": "error", "error": str(e), "traceback": error_trace[:500]}

# Final safety check - ensure result is always a dict, never None
if result is None:
    result = {"message": "Utilization update started", "status": "started", "note": "result was None after all checks"}

# CRITICAL: Ensure result is always set - exec() will capture this assignment
# Direct assignment is what exec() needs - globals()/vars() don't work in exec() context
if not isinstance(result, dict):
    result = {"status": "started", "message": "utilization_sync started", "note": "result was not a dict"}

# Ensure result has required fields
if "status" not in result:
    result["status"] = "started"
if "message" not in result:
    result["message"] = "utilization_sync started"
# job_id is optional, keep it if present
    
# Final explicit assignment - this is what exec() will capture
# CRITICAL: This must be the last line - exec() captures this assignment
# Force a new dict assignment to ensure exec() sees it
if not isinstance(result, dict) or result is None:
    result = {"status": "started", "message": "utilization_sync started"}
else:
    # Create explicit new dict to ensure exec() captures the assignment
    result = {
        "status": result.get("status", "started"),
        "message": result.get("message", "utilization_sync started"),
        "job_id": result.get("job_id")
    }
# Remove None values
result = {k: v for k, v in result.items() if v is not None}'''
            
            utilization_sync_id = str(uuid.uuid4())
            now = datetime.datetime.now()
            api_def = {
                "id": utilization_sync_id,
                "name": "Utilization Sync",
                "path": "/api/utilization/sync",
                "method": "POST",
                "python_code": utilization_sync_code,
                "description": "Asynchronous utilization sync from BigQuery to Odoo. Returns immediately and runs in background.",
                "enabled": True,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            cur.execute("""
                INSERT INTO apis (id, name, path, method, python_code, description, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                utilization_sync_id, "Utilization Sync", "/api/utilization/sync", "POST",
                utilization_sync_code,
                "Asynchronous utilization sync from BigQuery to Odoo. Returns immediately and runs in background.",
                True, now, now
            ))
            conn.commit()
            print("Utilization Sync API added to database")
            # Register the route immediately after creating it
            try:
                create_dynamic_route(api_def)
                print("Utilization Sync API route registered")
            except Exception as e:
                print(f"Error registering Utilization Sync API route: {e}")
        cur.close()
        return_db_connection(conn)
    except Exception as e:
        print(f"Error checking/creating utilization sync API: {e}")
        if conn:
            return_db_connection(conn)
    
    # Add/Update audio transcription API in database
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM apis WHERE path = %s AND method = %s", ("/api/audio/transcribe", "POST"))
        existing_api = cur.fetchone()
        
        transcription_code = '''import sys
import os
import tempfile

# -----------------------------
# FIX protobuf conflict - MUST be done before any google imports
# -----------------------------
import gc
import importlib

# More aggressive cleanup - remove ONLY protobuf/rpc modules, NOT generativeai
# Removing generativeai breaks the package structure and causes ImportError
modules_to_remove = []
for module_name in list(sys.modules.keys()):
    if any(module_name.startswith(prefix) for prefix in [
        'google.protobuf',
        'google.rpc',
        'google._upb',
        'google._message'
    ]) and not module_name.startswith('google.generativeai'):
        modules_to_remove.append(module_name)

# Remove modules in reverse order (dependencies first)
for mod in sorted(modules_to_remove, reverse=True):
    if mod in sys.modules:
        try:
            # Clear any references
            module_obj = sys.modules[mod]
            if hasattr(module_obj, '__dict__'):
                module_obj.__dict__.clear()
            del sys.modules[mod]
        except:
            pass

# Force garbage collection
gc.collect()

# Reorder sys.path to prioritize venv packages over system packages
venv_path = None
for p in sys.path:
    if 'venv' in p and 'site-packages' in p:
        venv_path = p
        break

if venv_path:
    # Move venv site-packages to front
    sys.path = [venv_path] + [p for p in sys.path if p != venv_path]

# Remove system dist-packages from path to avoid conflicts
sys.path = [p for p in sys.path if '/usr/lib/python3/dist-packages' not in p]

# Invalidate import caches
importlib.invalidate_caches()

# -----------------------------
# IMPORT GEMINI SDK (after protobuf fix)
# -----------------------------
# Import generativeai - it will handle protobuf imports internally
# Don't pre-import protobuf as it may cause conflicts
import google.generativeai as genai

# -----------------------------
# CONFIG
# -----------------------------
GEMINI_API_KEY = "AIzaSyDmr5DDqIqzsoYGFtQhFIc8Scr08qDnYQI"
MASTER_PROMPT = """
Transcribe the audio with maximum accuracy.
- If audio is Arabic: write perfect Modern Standard Arabic unless dialect is clear.
- Preserve meaning faithfully.
- Do NOT add explanations or notes.
- Output ONLY the transcription.
"""

# -----------------------------
# SETUP
# -----------------------------
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3-pro-preview")  # Best Arabic model

# -----------------------------
# GET AUDIO URL FROM REQUEST
# -----------------------------
body = request_data.get("body", {})
audio_url = body.get("audio_url") or body.get("url")
bearer_token = body.get("bearer_token") or body.get("token") or "EAASCfixWPU0BPHxtlgq0KfyOuB8gFSy5Um15IBcOwBhad25ZB29Bq05nIEiBhkWtFNHC4rUs7fJPQ2GNUwiDZAfrKOy1dOyzH6NPJxAHSBkNIYJIL9Agbvbgiyxddyz4iBbJcZAXZA0mPUHN8leQbZAetn1SxYraUY2YFu84r8HZBG182ZBkxttwoS8u40Lr5ejMAZDZD"

if not audio_url:
    result = {"error": "Missing audio_url parameter. Please provide audio_url in request body."}
else:
    try:
        # Download audio file with Bearer token authentication
        import tempfile
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        
        response_download = requests.get(audio_url, headers=headers, timeout=300)
        
        # Check if response is JSON error (WhatsApp API returns JSON errors)
        content_type = response_download.headers.get('Content-Type', '').lower()
        if 'application/json' in content_type or response_download.text.strip().startswith('{'):
            try:
                error_data = response_download.json()
                error_msg = error_data.get('detail') or error_data.get('title') or error_data.get('message', 'Unknown error')
                result = {
                    "error": f"Media download failed: {error_msg}",
                    "status": "error",
                    "http_status": response_download.status_code,
                    "error_details": error_data
                }
            except:
                result = {
                    "error": f"Failed to download audio file: HTTP {response_download.status_code} - {response_download.text[:200]}",
                    "status": "error",
                    "http_status": response_download.status_code
                }
        else:
            # Check HTTP status
            response_download.raise_for_status()
            
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ogg')
            temp_file.write(response_download.content)
            temp_file.close()
            audio_path = temp_file.name
        
            try:
                # Upload audio to Gemini
                audio_file = genai.upload_file(audio_path)
                
                # Transcribe
                response = model.generate_content(
                    [MASTER_PROMPT, audio_file],
                    request_options={"timeout": 600}
                )
                
                transcription = response.text.strip()
                result = {
                    "transcription": transcription,
                    "audio_url": audio_url,
                    "status": "success"
                }
            finally:
                # Clean up temporary file
                try:
                    os.unlink(audio_path)
                except:
                    pass
    except requests.exceptions.RequestException as e:
        result = {"error": f"Failed to download audio file: {str(e)}", "status": "error"}
    except Exception as e:
        result = {"error": f"Transcription failed: {str(e)}", "status": "error"}'''
            
        now = datetime.datetime.now()
        
        if existing_api:
            # Update existing API
            api_id = existing_api[0]
            cur.execute("""
                UPDATE apis 
                SET python_code = %s, description = %s, updated_at = %s
                WHERE id = %s
            """, (
                transcription_code,
                "Transcribe audio files from URLs using Google Gemini API. Supports Arabic and other languages. Supports Bearer token authentication.",
                now,
                api_id
            ))
            conn.commit()
            print("Audio Transcription API updated in database")
            
            # Get updated API definition
            cur.close()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM apis WHERE id = %s", (api_id,))
            api_row = cur.fetchone()
            if api_row:
                api_def = dict(api_row)
                # Register the route immediately after updating it
                try:
                    create_dynamic_route(api_def)
                    print("Audio Transcription API route updated")
                except Exception as e:
                    print(f"Error updating Audio Transcription API route: {e}")
        else:
            # Create new API
            transcription_id = str(uuid.uuid4())
            api_def = {
                "id": transcription_id,
                "name": "Audio Transcription",
                "path": "/api/audio/transcribe",
                "method": "POST",
                "python_code": transcription_code,
                "description": "Transcribe audio files from URLs using Google Gemini API. Supports Arabic and other languages. Supports Bearer token authentication. Note: WhatsApp Business API media URLs may require signed requests - ensure your access token has proper permissions.",
                "enabled": True,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            cur.execute("""
                INSERT INTO apis (id, name, path, method, python_code, description, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transcription_id, "Audio Transcription", "/api/audio/transcribe", "POST",
                transcription_code,
                "Transcribe audio files from URLs using Google Gemini API. Supports Arabic and other languages. Supports Bearer token authentication.",
                True, now, now
            ))
            conn.commit()
            print("Audio Transcription API added to database")
            # Register the route immediately after creating it
            try:
                create_dynamic_route(api_def)
                print("Audio Transcription API route registered")
            except Exception as e:
                print(f"Error registering Audio Transcription API route: {e}")
        cur.close()
        return_db_connection(conn)
    except Exception as e:
        print(f"Error checking/creating audio transcription API: {e}")
        if conn:
            return_db_connection(conn)


# Default endpoints
@app.get("/ping")
async def ping():
    return {"status": "ok", "service": "API Management System"}
