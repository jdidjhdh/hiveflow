"""LLM settings API and Agent runtime wiring tests."""
import os

import pytest


class TestLLMSettingsAPI:
    def test_provider_crud(self, client, initialized_engine):
        cred = client.post("/api/credentials", json={
            "name": "OpenAI Test Key",
            "type": "api_key",
            "value": "sk-test-key",
        })
        assert cred.status_code == 200
        cred_id = cred.json()["id"]

        created = client.post("/api/llm/providers", json={
            "name": "Test GPT",
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key_credential_id": cred_id,
            "temperature": 0.2,
            "max_tokens": 2048,
            "top_p": 1,
        })
        assert created.status_code == 200
        provider_id = created.json()["id"]

        listed = client.get("/api/llm/providers")
        assert listed.status_code == 200
        assert any(p["id"] == provider_id for p in listed.json()["providers"])

        updated = client.put(f"/api/llm/providers/{provider_id}", json={"temperature": 0.5})
        assert updated.status_code == 200
        assert updated.json()["temperature"] == 0.5

        deleted = client.delete(f"/api/llm/providers/{provider_id}")
        assert deleted.status_code == 200

    def test_agent_settings_echo(self, client, initialized_engine):
        client.post("/api/agent/runtime", json={"mode": "agent"})
        resp = client.put("/api/llm/agent", json={
            "use_echo_llm": True,
            "reload_agent": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["use_echo_llm"] is True
        assert body["llm_source"] == "echo"
        assert body["reloaded"] is True

    def test_agent_settings_requires_provider_when_disabling_echo(self, client, initialized_engine):
        resp = client.put("/api/llm/agent", json={
            "use_echo_llm": False,
            "reload_agent": False,
        })
        assert resp.status_code == 400

    def test_agent_settings_with_provider(self, client, initialized_engine):
        cred = client.post("/api/credentials", json={
            "name": "Key",
            "type": "api_key",
            "value": "sk-test",
        })
        cred_id = cred.json()["id"]

        provider = client.post("/api/llm/providers", json={
            "name": "Planner",
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key_credential_id": cred_id,
        })
        provider_id = provider.json()["id"]

        client.post("/api/agent/runtime", json={"mode": "agent"})
        resp = client.put("/api/llm/agent", json={
            "use_echo_llm": False,
            "planning_provider_id": provider_id,
            "execution_provider_id": provider_id,
            "reload_agent": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["llm_source"] == "settings"
        assert body["planning_provider"]["id"] == provider_id


@pytest.mark.asyncio
async def test_plan_only_uses_settings_llm_when_configured(initialized_engine):
    """When Studio LLM settings disable echo, resolver should use settings source."""
    from app.core.llm_settings import create_provider, update_agent_settings, resolve_llm_source
    from app.api.credentials import _credentials_store, fernet
    import time
    import uuid

    os.environ.pop("HIVEFLOW_AGENT_ECHO_LLM", None)
    engine = initialized_engine

    cred_id = f"cred_{uuid.uuid4().hex[:8]}"
    _credentials_store[cred_id] = {
        "id": cred_id,
        "name": "fake",
        "type": "api_key",
        "value": fernet.encrypt(b"sk-fake").decode(),
        "created_at": time.time(),
    }

    provider = create_provider({
        "name": "Mock OpenAI",
        "provider": "openai",
        "model_name": "gpt-4o-mini",
        "api_key_credential_id": cred_id,
    })
    update_agent_settings({
        "use_echo_llm": False,
        "planning_provider_id": provider["id"],
        "execution_provider_id": provider["id"],
    })

    await engine.set_runtime_mode("agent")
    assert engine.get_runtime_info()["agent_active"]
    assert resolve_llm_source() == "settings"
