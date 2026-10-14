
import sys
from pathlib import Path

import pytest

# Make the src directory importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from deployops import server


def test_backend_deployment_status(monkeypatch):
    monkeypatch.setattr(
        server,
        "fetch_job",
        lambda job, tree: {
            "name": job,
            "url": "http://localhost:8080/job/SampleJenkins/",
            "lastBuild": {
                "number": 7,
                "result": "SUCCESS",
                "building": False,
                "url": "http://localhost:8080/job/SampleJenkins/7/",
            },
        },
    )

    result = server.get_deploy_status("backend")

    assert result["service"] == "backend"
    assert result["job"] == "SampleJenkins"
    assert result["status"] == "SUCCESS"
    assert result["build_number"] == 7


def test_frontend_failed_builds(monkeypatch):
    monkeypatch.setattr(
        server,
        "fetch_job",
        lambda job, tree: {
            "name": job,
            "url": "http://localhost:8080/job/SampleJenkins/",
            "builds": [
                {
                    "number": 10,
                    "result": "FAILURE",
                    "building": False,
                    "url": "http://localhost:8080/job/SampleJenkins/10/",
                },
                {
                    "number": 9,
                    "result": "SUCCESS",
                    "building": False,
                    "url": "http://localhost:8080/job/SampleJenkins/9/",
                },
            ],
        },
    )

    result = server.list_failed_builds("backend")

    assert result["service"] == "backend"
    assert result["count"] == 1
    assert result["failed_builds"][0]["build_number"] == 10


def test_unknown_service():
    result = server.get_deploy_status("unknown")

    assert "error" in result
    assert "backend" in result["available_services"]


def test_create_jira_incident(monkeypatch):
    # Mock the Jira HTTP response: no real issue is created.
    class FakeResponse:
        status_code = 201

        @staticmethod
        def json():
            return {"key": "DM-999", "id": "999"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(server.httpx, "Client", FakeClient)

    result = server.create_jira_incident(
        "Test incident",
        "A mocked test incident.",
        "Task",
    )

    assert result["success"] is True
    assert result["issue_key"] == "DM-999"
    assert result["issue_url"].endswith("/browse/DM-999")


def test_jira_incident_rejects_empty_summary():
    result = server.create_jira_incident(
        "   ",
        "Test description",
        "Task",
    )

    assert "error" in result
    assert "Summary cannot be empty" in result["error"]


def test_jira_incident_rejects_empty_description():
    result = server.create_jira_incident(
        "Test incident",
        "   ",
        "Task",
    )

    assert "error" in result
    assert "Description cannot be empty" in result["error"]


def test_rollback_requires_confirmation():
    result = server.rollback_service(
        "backend",
        "v1.0.0",
        False,
    )

    assert result["status"] == "confirmation_required"


def test_rollback_is_blocked_without_deployment_mechanism():
    result = server.rollback_service(
        "backend",
        "v1.0.0",
        True,
    )

    assert result["status"] == "not_executed"
    assert "no real deployment rollback mechanism" in result["message"]
