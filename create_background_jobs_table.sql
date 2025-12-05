-- Background Jobs table for tracking async operations
CREATE TABLE IF NOT EXISTS background_jobs (
    id VARCHAR(255) PRIMARY KEY,
    job_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'running', -- running, completed, failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    progress_log TEXT,
    error_message TEXT,
    result_summary TEXT
);

-- Progress logs table for detailed step-by-step logging
CREATE TABLE IF NOT EXISTS job_progress_logs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(255) NOT NULL REFERENCES background_jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    log_level VARCHAR(20) NOT NULL, -- info, warning, error, success
    message TEXT NOT NULL,
    step_number INTEGER
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(status);
CREATE INDEX IF NOT EXISTS idx_background_jobs_type ON background_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_background_jobs_started ON background_jobs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_progress_logs_job_id ON job_progress_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_job_progress_logs_timestamp ON job_progress_logs(timestamp DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON background_jobs TO api_user;
GRANT ALL PRIVILEGES ON job_progress_logs TO api_user;
GRANT USAGE, SELECT ON SEQUENCE job_progress_logs_id_seq TO api_user;

