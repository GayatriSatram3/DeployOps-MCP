# DeployOps MCP Server

A Python-based Model Context Protocol (MCP) server that connects AI assistants to deployment operations through Jenkins and Jira Cloud.

DeployOps exposes tools for inspecting Jenkins build results, identifying failed builds, creating Jira incidents, and validating rollback requests with safety checks.

## Features

- **Jenkins integration:** Retrieve the latest build status and recent failed builds through the Jenkins REST API.
- **Jira integration:** Create Jira issues with validated summaries, descriptions, and issue types.
- **Rollback safeguards:** Require explicit confirmation and block rollback execution when no deployment rollback mechanism is configured.
- **Input validation:** Reject empty and oversized incident fields and invalid rollback requests.
- **Audit logging:** Record selected operations and outcomes without intentionally logging API tokens or incident descriptions.
- **Automated testing:** Unit tests use mocked responses, while a separate MCP protocol test verifies tool registration.

## Tech Stack

- Python 3.12
- Model Context Protocol (MCP)
- FastMCP
- HTTPX
- python-dotenv
- pytest
- Jenkins REST API
- Jira Cloud REST API v3

## Project Structure

```text
deployops-mcp/
├── src/
│   └── deployops/
│       ├── __init__.py
│       └── server.py
├── tests/
│   ├── test_mcp_client.py
│   └── test_mcp_protocol.py
├── logs/
│   └── audit.log
├── .env
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## Available MCP Tools

| Tool | Description |
|---|---|
| `get_deploy_status` | Retrieve the latest build status for a configured Jenkins job. |
| `list_failed_builds` | Retrieve recent failed builds for a configured Jenkins job. |
| `create_jira_incident` | Create a Jira issue with validated inputs. |
| `rollback_service` | Validate a rollback request and block execution if no real rollback mechanism is configured. |

**Important:** Jenkins build status does not necessarily indicate the health of a deployed application. The current rollback tool does not perform a real rollback.

## Prerequisites

- Python 3.12 or compatible version
- A running Jenkins instance and a Jenkins API token
- A Jira Cloud account with permission to create issues
- A Jira API token

## Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd deployops-mcp
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and populate the values locally.

```dotenv
JENKINS_URL=http://localhost:8080
JENKINS_USER=your_jenkins_username
JENKINS_API_TOKEN=your_jenkins_api_token
JENKINS_JOB_BACKEND=SampleJenkins

JIRA_URL=https://your-site.atlassian.net
JIRA_EMAIL=your_atlassian_email
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=YOUR_PROJECT_KEY
```

Never commit `.env` or share API tokens. Ensure `.env` and generated logs are excluded from version control.

### 5. Start the MCP server

```powershell
python src/deployops/server.py
```

The server uses standard input/output (stdio) for MCP communication. An MCP-compatible client should launch and communicate with it using the appropriate server configuration.

## Testing

Run the test suite:

```powershell
python -m pytest -v
```

The unit tests mock external HTTP responses so they don't need to create real Jira issues. The MCP protocol test starts the server and verifies that the expected tools are registered.

## Security Considerations

- Store credentials in environment variables and keep `.env` out of source control.
- Use dedicated API credentials with the minimum required permissions.
- Avoid logging tokens, authorization headers, or sensitive incident descriptions.
- Treat audit logs as operational data and protect access to them.
- Require appropriate authorization and safeguards before adding deployment-changing operations.
- The current rollback tool is intentionally non-executing.

## Current Limitations

- The Jenkins service mapping currently configures the `backend` alias to `SampleJenkins`.
- A Jenkins build's result is not a guarantee of application deployment health.
- Real rollback execution requires a deployment environment and an explicitly configured rollback procedure.
- Audit logging currently covers selected operations; it is not yet a comprehensive security audit system.

## Future Improvements

- Add additional Jenkins job mappings.
- Add comprehensive audit coverage and dedicated audit-log tests.
- Add role-based authorization and stronger input validation.
- Integrate a real deployment environment with a safe rollback workflow.
- Add CI automation for tests and linting.

## License

Choose and add an appropriate open-source license before distributing the project.
