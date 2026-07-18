"""Smoke tests for workspace APIs (projects, proposals, jobs, CRM, schedules, export)."""


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_workspace_projects_proposals_jobs_clients_schedules_audit(client):
    p = client.post("/api/workspace/projects", json={"name": "Acme", "description": "Test"})
    assert p.status_code == 200, p.text
    project_id = p.json()["id"]
    assert p.json()["name"] == "Acme"

    listed = client.get("/api/workspace/projects")
    assert listed.status_code == 200
    assert any(x["id"] == project_id for x in listed.json())

    s = client.post("/api/sessions", json={"title": "Workspace smoke"})
    assert s.status_code == 200
    sid = s.json()["id"]

    pinned = client.patch(f"/api/sessions/{sid}", json={"pinned": True, "project_id": project_id})
    assert pinned.status_code == 200
    assert pinned.json()["pinned"] is True
    assert pinned.json()["project_id"] == project_id

    pr = client.post(
        "/api/workspace/proposals",
        json={"title": "Draft", "content": "Hello client", "sessionId": sid},
    )
    assert pr.status_code == 200
    assert client.get("/api/workspace/proposals").json()

    job = client.post(
        "/api/workspace/jobs",
        json={
            "content": "Need a Python FastAPI developer for API integration. Budget $50/hr.",
            "title": "API gig",
        },
    )
    assert job.status_code == 200
    body = job.json()
    assert body["fit_score"] is not None
    assert body["fit_score"] > 0

    c = client.post("/api/workspace/clients", json={"name": "Jane", "rate": "$80/hr", "notes": "VIP"})
    assert c.status_code == 200
    assert any(x["name"] == "Jane" for x in client.get("/api/workspace/clients").json())

    sch = client.post("/api/workspace/schedules", json={"topic": "AI tooling", "cadence": "weekly"})
    assert sch.status_code == 200
    assert client.get("/api/workspace/schedules").json()

    assert client.get("/api/workspace/audit").status_code == 200

    usage = client.get(f"/api/workspace/sessions/{sid}/usage")
    assert usage.status_code == 200
    assert "total_tokens" in usage.json()

    client.post(f"/api/sessions/{sid}/messages", json={"messages": [{"role": "user", "content": "hi"}]})
    client.post(
        f"/api/sessions/{sid}/messages",
        json={
            "messages": [
                {"role": "assistant", "content": "hello\n\n```mermaid\ngraph TD; A-->B\n```"}
            ]
        },
    )
    exp = client.get(f"/api/workspace/sessions/{sid}/export?format=markdown")
    assert exp.status_code == 200
    assert "hello" in exp.text

    arts = client.post(f"/api/workspace/sessions/{sid}/artifacts/sync")
    assert arts.status_code == 200
    assert isinstance(arts.json(), list)

    cockpit = client.get("/api/workspace/freelance/cockpit")
    assert cockpit.status_code == 200
    assert "connected_platforms" in cockpit.json()

    client.delete(f"/api/workspace/projects/{project_id}")
    client.delete(f"/api/sessions/{sid}")


def test_whatsapp_coming_soon_in_providers(client):
    r = client.get("/api/connections/providers")
    assert r.status_code == 200
    payload = r.json()
    providers = payload["providers"] if isinstance(payload, dict) else payload
    wa = next((p for p in providers if p["id"] == "whatsapp"), None)
    assert wa is not None
    assert wa["status"] == "coming_soon"
    tg = next((p for p in providers if p["id"] == "telegram"), None)
    assert tg is not None
