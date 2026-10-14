
import os
import sys
from urllib.parse import quote

import logging
from datetime import datetime, timezone
from pathlib import Path


import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()


LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "audit.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)

audit_logger = logging.getLogger("deployops.audit")


def log_audit_event(
    tool_name: str,
    outcome: str,
    resource: str = "none",
) -> None:
    """Record a tool event without logging secrets or user descriptions."""
    audit_logger.info(
        "event_time=%s tool=%s outcome=%s resource=%s",
        datetime.now(timezone.utc).isoformat(),
        tool_name,
        outcome,
        resource,
    )


mcp = FastMCP("DeployOps")

JENKINS_URL = os.getenv("JENKINS_URL", "").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "")
JENKINS_API_TOKEN = os.getenv("JENKINS_API_TOKEN", "")

# Maps DeployOps service names to real Jenkins job names.
JENKINS_JOBS = {
    "backend": os.getenv("JENKINS_JOB_BACKEND", ""),
}


def get_jenkins_client() -> httpx.Client:
    """Create an authenticated Jenkins API client."""
    if not all([JENKINS_URL, JENKINS_USER, JENKINS_API_TOKEN]):
        raise ValueError(
            "Configure JENKINS_URL, JENKINS_USER, and "
            "JENKINS_API_TOKEN in your .env file."
        )

    return httpx.Client(
        base_url=JENKINS_URL,
        auth=(JENKINS_USER, JENKINS_API_TOKEN),
        timeout=10.0,
    )


def get_job_path(job_name: str) -> str:
    """Build the API path for a Jenkins job."""
    return f"/job/{quote(job_name, safe='')}"


def fetch_job(job_name: str, tree: str) -> dict:
    """Fetch selected job information from Jenkins."""
    with get_jenkins_client() as client:
        response = client.get(
            f"{get_job_path(job_name)}/api/json",
            params={"tree": tree},
        )
        response.raise_for_status()
        return response.json()


def get_service_job(service_name: str) -> tuple[str, str | None]:
    """Validate the service and return its Jenkins job name."""
    service = service_name.strip().lower()
    job_name = JENKINS_JOBS.get(service)

    if not job_name:
        return service, None

    return service, job_name


@mcp.tool()
def get_deploy_status(service_name: str) -> dict:
    """Get the latest build/deployment status for a service from Jenkins."""
    service, job_name = get_service_job(service_name)

    if not job_name:
        return {
            "error": f"No Jenkins job configured for service: {service}",
            "available_services": [
                name for name, job in JENKINS_JOBS.items() if job
            ],
        }

    try:
        job = fetch_job(
            job_name,
            "name,url,lastBuild[number,result,building,url]",
        )

        last_build = job.get("lastBuild")

        if last_build is None:
            status = "NO_BUILDS"
            build_number = None
            build_url = None
        elif last_build.get("building"):
            status = "IN_PROGRESS"
            build_number = last_build.get("number")
            build_url = last_build.get("url")
        else:
            status = last_build.get("result") or "UNKNOWN"
            build_number = last_build.get("number")
            build_url = last_build.get("url")

        return {
            "service": service,
            "job": job.get("name", job_name),
            "status": status,
            "build_number": build_number,
            "build_url": build_url,
            "job_url": job.get("url"),
        }

    except ValueError as exc:
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        return {
            "error": "Jenkins API returned an HTTP error.",
            "status_code": exc.response.status_code,
        }
    except httpx.RequestError:
        return {
            "error": "Could not connect to Jenkins. Check that Jenkins is running and JENKINS_URL is correct."
        }


@mcp.tool()
def list_failed_builds(service_name: str) -> dict:
    """List recent failed builds for a service from Jenkins."""
    service, job_name = get_service_job(service_name)

    if not job_name:
        return {
            "error": f"No Jenkins job configured for service: {service}",
            "available_services": [
                name for name, job in JENKINS_JOBS.items() if job
            ],
        }

    try:
        job = fetch_job(
            job_name,
            "name,url,builds[number,result,building,url]{0,10}",
        )

        failed_builds = [
            {
                "build_number": build["number"],
                "status": build.get("result") or (
                    "IN_PROGRESS" if build.get("building") else "UNKNOWN"
                ),
                "url": build.get("url"),
            }
            for build in job.get("builds", [])
            if not build.get("building") and build.get("result") == "FAILURE"
        ]

        return {
            "service": service,
            "job": job.get("name", job_name),
            "failed_builds": failed_builds,
            "count": len(failed_builds),
        }

    except ValueError as exc:
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        return {
            "error": "Jenkins API returned an HTTP error.",
            "status_code": exc.response.status_code,
        }
    except httpx.RequestError:
        return {
            "error": "Could not connect to Jenkins. Check that Jenkins is running and JENKINS_URL is correct."
        }



JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "")


@mcp.tool()
def create_jira_incident(
    summary: str,
    description: str,
    issue_type: str = "Task",
) -> dict:
    """Create a Jira issue for a deployment incident."""
    summary = summary.strip()
    description = description.strip()
    issue_type = issue_type.strip()

    # Validate input before making an external API request.
    if not summary:
        log_audit_event(
            "create_jira_incident",
            "validation_failed",
            "summary",
        )
        return {"error": "Summary cannot be empty."}

    if len(summary) > 255:
        return {"error": "Summary must be 255 characters or fewer."}

    if not description:
        log_audit_event(
            "create_jira_incident",
            "validation_failed",
            "description",
        )
        return {"error": "Description cannot be empty."}

    
    if len(description) > 10000:
        return {"error": "Description must be 10000 characters or fewer."}

    if not issue_type:
        return {"error": "Issue type cannot be empty."}

    if not all([
        JIRA_URL,
        JIRA_EMAIL,
        JIRA_API_TOKEN,
        JIRA_PROJECT_KEY,
    ]):
        return {
            "error": (
                "Configure JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN, "
                "and JIRA_PROJECT_KEY in .env."
            )
        }

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ],
                    }
                ],
            },
            "issuetype": {"name": issue_type},
        }
    }

    try:
        with httpx.Client(
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            timeout=15.0,
        ) as client:
            response = client.post(
                f"{JIRA_URL}/rest/api/3/issue",
                json=payload,
                headers={"Accept": "application/json"},
            )


        
        if response.status_code == 201:
            issue = response.json()
        
            log_audit_event(
                "create_jira_incident",
                "success",
                issue["key"],
            )
        
            return {
                "success": True,
                "message": "Jira issue created successfully.",
                "issue_key": issue["key"],
                "issue_id": issue["id"],
                "issue_url": f"{JIRA_URL}/browse/{issue['key']}",
            }

        
        
        log_audit_event(
            "create_jira_incident",
            "api_failed",
            f"http_{response.status_code}",
        )

        return {
            "error": "Jira could not create the issue.",
            "status_code": response.status_code,
            "details": response.text[:1000],
        }


    except httpx.RequestError:
        return {
            "error": (
                "Could not connect to Jira. Check JIRA_URL "
                "and your internet connection."
            )
        }

@mcp.tool()
def rollback_service(
    service_name: str,
    target_version: str,
    confirm: bool = False,
) -> dict:
    """Validate a rollback request without executing a deployment change."""
    service = service_name.strip().lower()
    target_version = target_version.strip()

    if service not in JENKINS_JOBS or not JENKINS_JOBS[service]:
        log_audit_event(
            "rollback_service", "validation_failed", "unknown_service"
        )
        return {"error": f"Unknown or unconfigured service: {service}"}

    if not target_version:
        log_audit_event(
            "rollback_service", "validation_failed", "target_version"
        )
        return {"error": "Target version cannot be empty."}

    if not confirm:
        log_audit_event(
            "rollback_service", "confirmation_required", service
        )
        return {
            "status": "confirmation_required",
            "message": (
                "Rollback was not executed. Explicit confirmation is required."
            ),
            "service": service,
            "target_version": target_version,
        }

    # SampleJenkins only builds/tests. No rollback mechanism is configured.
    log_audit_event(
        "rollback_service", "blocked_no_rollback_mechanism", service
    )
    return {
        "status": "not_executed",
        "message": (
            "Rollback is blocked because no real deployment rollback "
            "mechanism is configured for this service."
        ),
        "service": service,
        "target_version": target_version,
    }


if __name__ == "__main__":
    print("Starting DeployOps MCP server...", file=sys.stderr)
    mcp.run()
