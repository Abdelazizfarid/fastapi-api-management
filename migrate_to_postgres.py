#!/usr/bin/env python3
"""
Migration script to move data from JSON files to PostgreSQL
"""
import json
import os
import psycopg2
from datetime import datetime

# Database connection
DB_CONFIG = {
    'dbname': 'api_management',
    'user': 'api_user',
    'password': 'api_password_123',
    'host': 'localhost',
    'port': '5432'
}

def connect_db():
    """Connect to PostgreSQL database"""
    return psycopg2.connect(**DB_CONFIG)

def migrate_apis():
    """Migrate APIs from api_db.json to PostgreSQL"""
    print("Migrating APIs...")
    if not os.path.exists('api_db.json'):
        print("  No api_db.json file found, skipping APIs migration")
        return
    
    with open('api_db.json', 'r') as f:
        data = json.load(f)
    
    conn = connect_db()
    cur = conn.cursor()
    
    migrated = 0
    skipped = 0
    
    for api in data.get('apis', []):
        try:
            cur.execute("""
                INSERT INTO apis (id, name, path, method, python_code, description, enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                api['id'],
                api['name'],
                api['path'],
                api['method'],
                api['python_code'],
                api.get('description', ''),
                api.get('enabled', True),
                datetime.fromisoformat(api.get('created_at', datetime.now().isoformat())),
                datetime.fromisoformat(api.get('updated_at', datetime.now().isoformat()))
            ))
            if cur.rowcount > 0:
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error migrating API {api.get('id', 'unknown')}: {e}")
            skipped += 1
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Migrated {migrated} APIs, skipped {skipped} duplicates")

def migrate_logs():
    """Migrate logs from api_logs.json to PostgreSQL"""
    print("Migrating logs...")
    if not os.path.exists('api_logs.json'):
        print("  No api_logs.json file found, skipping logs migration")
        return
    
    with open('api_logs.json', 'r') as f:
        data = json.load(f)
    
    conn = connect_db()
    cur = conn.cursor()
    
    migrated = 0
    skipped = 0
    
    for log in data.get('logs', []):
        try:
            cur.execute("""
                INSERT INTO api_logs (
                    id, timestamp, method, path, query_params, headers, client_ip,
                    status_code, status, response_body, stdout, prints, response_time_ms
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                log['id'],
                datetime.fromisoformat(log['timestamp']),
                log['method'],
                log['path'],
                json.dumps(log.get('query_params', {})),
                json.dumps(log.get('headers', {})),
                log.get('client_ip'),
                log.get('status_code'),
                log.get('status', 'completed'),
                log.get('response_body', ''),
                log.get('stdout', ''),
                log.get('prints', ''),
                log.get('response_time_ms', 0)
            ))
            if cur.rowcount > 0:
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error migrating log {log.get('id', 'unknown')}: {e}")
            skipped += 1
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Migrated {migrated} logs, skipped {skipped} duplicates")

def migrate_sessions():
    """Migrate sessions from sessions.json to PostgreSQL"""
    print("Migrating sessions...")
    if not os.path.exists('sessions.json'):
        print("  No sessions.json file found, skipping sessions migration")
        return
    
    with open('sessions.json', 'r') as f:
        sessions = json.load(f)
    
    conn = connect_db()
    cur = conn.cursor()
    
    migrated = 0
    skipped = 0
    
    for session_id, session_data in sessions.items():
        try:
            expires_at = None
            if 'created_at' in session_data:
                created = datetime.fromisoformat(session_data['created_at'])
                # Set expiration to 30 days from creation
                from datetime import timedelta
                expires_at = created + timedelta(days=30)
            
            cur.execute("""
                INSERT INTO sessions (session_id, username, created_at, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (session_id) DO NOTHING
            """, (
                session_id,
                session_data.get('username', ''),
                datetime.fromisoformat(session_data.get('created_at', datetime.now().isoformat())),
                expires_at
            ))
            if cur.rowcount > 0:
                migrated += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  Error migrating session {session_id}: {e}")
            skipped += 1
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Migrated {migrated} sessions, skipped {skipped} duplicates")

def main():
    print("Starting migration from JSON files to PostgreSQL...")
    print("=" * 60)
    print("Note: Tables should be created separately with proper permissions")
    print()
    
    # Migrate data
    migrate_apis()
    print()
    migrate_logs()
    print()
    migrate_sessions()
    print()
    
    print("=" * 60)
    print("Migration completed!")

if __name__ == '__main__':
    main()

