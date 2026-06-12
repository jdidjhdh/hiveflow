"""Triggers and scheduler settings API tests."""
import pytest


class TestTriggersAPI:
    def test_trigger_crud(self, client):
        create = client.post("/api/triggers", json={
            "name": "Daily sync",
            "type": "schedule",
            "config": {"cron": "0 0 * * *"},
            "enabled": True,
            "workflow_id": "wf_1",
        })
        assert create.status_code == 200
        trigger_id = create.json()["id"]

        listed = client.get("/api/triggers")
        assert listed.status_code == 200
        assert any(t["id"] == trigger_id for t in listed.json()["triggers"])

        updated = client.put(f"/api/triggers/{trigger_id}", json={"enabled": False})
        assert updated.status_code == 200
        assert updated.json()["enabled"] is False

        toggled = client.post(f"/api/triggers/{trigger_id}/toggle")
        assert toggled.status_code == 200
        assert toggled.json()["enabled"] is True

        deleted = client.delete(f"/api/triggers/{trigger_id}")
        assert deleted.status_code == 200


class TestSchedulerSettingsAPI:
    def test_scheduler_settings_roundtrip(self, client, initialized_engine):
        resp = client.get("/api/settings/scheduler")
        assert resp.status_code == 200
        assert resp.json()["strategy"] in ("least_loaded", "auction")

        updated = client.put("/api/settings/scheduler", json={
            "strategy": "auction",
            "auction_timeout": 8,
        })
        assert updated.status_code == 200
        body = updated.json()
        assert body["strategy"] == "auction"
        assert body["auction_timeout"] == 8

        reset = client.put("/api/settings/scheduler", json={
            "strategy": "least_loaded",
            "auction_timeout": 5,
        })
        assert reset.status_code == 200
        assert reset.json()["strategy"] == "least_loaded"
