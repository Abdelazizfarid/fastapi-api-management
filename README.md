# FastAPI API Management System

## Server Information

- **Server**: `ubuntu@100.31.126.21`
- **Password**: `Abc123456!`
- **Production URL**: https://apisv1.beyond-solution.com/

---

A comprehensive web-based API management system built with FastAPI that allows you to create, modify, and manage APIs through a user-friendly web interface.

## Features

- 🚀 **Web UI for API Management**: Create, edit, and delete APIs through an intuitive web interface
- 🔐 **Authentication**: Secure login system with session management
- 📝 **Dynamic API Creation**: Write Python functions to create APIs on the fly
- 🧪 **Code Testing**: Test your Python code before deploying APIs
- 📊 **Logging System**: Comprehensive logging with detailed metadata for all API calls
- 🔍 **Log Viewer**: View and analyze API call logs with collapsible details
- ⚡ **Real-time Execution**: APIs execute Python code dynamically
- 🎨 **Modern UI**: Clean and responsive web interface

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Server**: Uvicorn
- **Authentication**: Session-based
- **Storage**: JSON files (api_db.json, api_logs.json)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Abdelazizfarid/fastapi-api-management.git
cd fastapi-api-management
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Usage

### Access the Web Interface

1. Open your browser and navigate to: `http://localhost:8000`
2. Login with credentials:
   - Username: `admin`
   - Password: `123456`

### Creating an API

1. Click "+ Create New API"
2. Fill in the API details:
   - **Name**: A descriptive name for your API
   - **Path**: The endpoint path (e.g., `/api/users`)
   - **Method**: HTTP method (GET, POST, PUT, DELETE, PATCH)
   - **Description**: Optional description
   - **Python Code**: Your Python function code

3. Click "Test Code" to verify your code works
4. Click "Create API" to deploy

### Python Code Structure

Your Python code should:
- Access request data via the `request_data` variable
- Set the `result` variable to return data

Example:
```python
# Access request data
query_params = request_data.get(query_params, {})
path = request_data.get(path)

# Set result
result = {
    message: Hello from API,
    query_params: query_params,
    path: path
}
```

### Viewing Logs

1. Navigate to the "Logs" page
2. View all API calls with:
   - Request metadata (method, path, headers)
   - Query parameters
   - Response body
   - Client IP
   - Response time
3. Click on any log item to expand and see full details

## Project Structure

```
fastapi-api-management/
├── main.py                 # Main FastAPI application
├── requirements.txt        # Python dependencies
├── api_db.json            # API definitions database
├── api_logs.json          # API call logs
├── templates/             # HTML templates
│   ├── index.html         # Main management UI
│   ├── login.html         # Login page
│   └── logs.html          # Logs viewer
└── static/                # Static files
    ├── style.css          # Stylesheet
    ├── script.js          # Main JavaScript
    └── logs.js            # Logs viewer JavaScript
```

## API Endpoints

### Management Endpoints (Require Authentication)
- `GET /` - Main management UI
- `GET /logs` - Logs viewer
- `GET /api/manage/list` - List all APIs
- `POST /api/manage/create` - Create new API
- `PUT /api/manage/{api_id}` - Update API
- `DELETE /api/manage/{api_id}` - Delete API
- `POST /api/manage/test` - Test Python code

### Log Endpoints (Require Authentication)
- `GET /api/logs` - Get API logs
- `DELETE /api/logs` - Clear logs

### Authentication
- `GET /login` - Login page
- `POST /login` - Authenticate
- `GET /logout` - Logout

## Configuration

### Default Credentials
- Username: `admin`
- Password: `123456`

**Note**: Change these credentials in `main.py` for production use.

## Production Deployment

For production deployment:

1. Use a production ASGI server like Gunicorn with Uvicorn workers
2. Set up proper session storage (Redis, database, etc.)
3. Use environment variables for sensitive data
4. Enable HTTPS
5. Configure proper logging
6. Set up a reverse proxy (Nginx)

## License

This project is open source and available for use.

## Author

Abdelaziz Farid
Email: abdelaziz.farid6@gmail.com
