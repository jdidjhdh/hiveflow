"""HiveFlow - Prompt Templates API Tests"""
import pytest


class TestPromptTemplatesAPI:
    """Prompt 模板 API 端点测试"""

    def test_list_templates_empty(self, client):
        resp = client.get("/api/prompt-templates")
        data = resp.json()
        assert resp.status_code == 200
        assert "templates" in data
        assert "categories" in data

    def test_seed_templates(self, client):
        resp = client.post("/api/prompt-templates/seed")
        data = resp.json()
        assert resp.status_code == 200
        assert data["seeded"] > 0
        assert len(data["templates"]) > 0

    def test_list_templates_after_seed(self, client):
        client.post("/api/prompt-templates/seed")
        resp = client.get("/api/prompt-templates")
        data = resp.json()
        assert len(data["templates"]) > 0

    def test_create_template(self, client):
        resp = client.post("/api/prompt-templates", json={
            "name": "Test Template",
            "content": "Hello {{name}}, welcome to {{project}}.",
            "category": "general",
            "description": "A test template",
            "tags": ["test"],
            "variables": ["name", "project"],
        })
        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "created"
        assert data["current_version"] == 1
        assert "id" in data

    def test_get_template(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Get Test",
            "content": "Hello {{name}}",
            "category": "chat",
        })
        template_id = create_resp.json()["id"]

        resp = client.get(f"/api/prompt-templates/{template_id}")
        data = resp.json()
        assert resp.status_code == 200
        assert data["name"] == "Get Test"
        assert data["content"] == "Hello {{name}}"
        assert data["category"] == "chat"

    def test_get_template_not_found(self, client):
        resp = client.get("/api/prompt-templates/nonexistent")
        assert resp.status_code == 404

    def test_update_template(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Update Test",
            "content": "v1 content",
            "category": "general",
        })
        template_id = create_resp.json()["id"]

        resp = client.put(f"/api/prompt-templates/{template_id}", json={
            "content": "v2 updated content",
        })
        data = resp.json()
        assert resp.status_code == 200
        assert data["current_version"] == 2

        get_resp = client.get(f"/api/prompt-templates/{template_id}")
        assert get_resp.json()["content"] == "v2 updated content"

    def test_update_metadata_only(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Meta Update",
            "content": "Original content",
            "category": "general",
        })
        template_id = create_resp.json()["id"]

        resp = client.put(f"/api/prompt-templates/{template_id}", json={
            "description": "New description",
        })
        data = resp.json()
        assert resp.status_code == 200
        # Version stays at 1 since content didn't change (only metadata update)
        assert data["current_version"] == 1

    def test_delete_template(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Delete Test",
            "content": "To be deleted",
        })
        template_id = create_resp.json()["id"]

        resp = client.delete(f"/api/prompt-templates/{template_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        get_resp = client.get(f"/api/prompt-templates/{template_id}")
        assert get_resp.status_code == 404

    def test_list_versions(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Version Test",
            "content": "v1",
        })
        template_id = create_resp.json()["id"]

        client.put(f"/api/prompt-templates/{template_id}", json={"content": "v2"})

        resp = client.get(f"/api/prompt-templates/{template_id}/versions")
        data = resp.json()
        assert resp.status_code == 200
        assert len(data["versions"]) == 2
        assert data["versions"][0]["version"] == 1
        assert data["versions"][1]["version"] == 2

    def test_get_specific_version(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Version Get Test",
            "content": "v1 content",
        })
        template_id = create_resp.json()["id"]

        client.put(f"/api/prompt-templates/{template_id}", json={"content": "v2 content"})

        resp = client.get(f"/api/prompt-templates/{template_id}?version=1")
        data = resp.json()
        assert data["content"] == "v1 content"
        assert data["requested_version"] == 1

    def test_rollback_version(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Rollback Test",
            "content": "v1 original",
        })
        template_id = create_resp.json()["id"]

        client.put(f"/api/prompt-templates/{template_id}", json={"content": "v2 changed"})

        resp = client.post(f"/api/prompt-templates/{template_id}/rollback/1")
        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "rolled_back"
        assert data["rolled_back_to"] == 1
        assert data["current_version"] == 3

        get_resp = client.get(f"/api/prompt-templates/{template_id}")
        assert get_resp.json()["content"] == "v1 original"

    def test_compare_versions(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Compare Test",
            "content": "line1\nline2\nline3",
        })
        template_id = create_resp.json()["id"]

        client.put(f"/api/prompt-templates/{template_id}", json={
            "content": "line1\nmodified\nline3\nline4",
        })

        resp = client.post(
            f"/api/prompt-templates/{template_id}/compare?version_a=1&version_b=2",
        )
        data = resp.json()
        assert resp.status_code == 200
        assert data["added_lines"] >= 0
        assert data["removed_lines"] >= 0
        assert 0 <= data["similarity"] <= 1

    def test_template_render(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Render Test",
            "content": "Hello {{name}}, welcome to {{project}}!",
            "variables": ["name", "project"],
        })
        template_id = create_resp.json()["id"]

        resp = client.post(f"/api/prompt-templates/{template_id}/test", json={
            "variables": {"name": "Alice", "project": "HiveFlow"},
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert "Hello Alice, welcome to HiveFlow!" in data["rendered"]
        assert len(data["unreplaced_variables"]) == 0

    def test_template_render_partial(self, client):
        create_resp = client.post("/api/prompt-templates", json={
            "name": "Partial Render",
            "content": "{{a}} and {{b}} and {{c}}",
            "variables": ["a", "b", "c"],
        })
        template_id = create_resp.json()["id"]

        resp = client.post(f"/api/prompt-templates/{template_id}/test", json={
            "variables": {"a": "1"},
        })
        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert "1" in data["rendered"]
        assert "b" in data["unreplaced_variables"]
        assert "c" in data["unreplaced_variables"]

    def test_filter_by_category(self, client):
        client.post("/api/prompt-templates/seed")
        resp = client.get("/api/prompt-templates?category=rag")
        data = resp.json()
        assert all(t["category"] == "rag" for t in data["templates"])

    def test_search_by_query(self, client):
        client.post("/api/prompt-templates/seed")
        resp = client.get("/api/prompt-templates?q=agent")
        data = resp.json()
        assert all(
            "agent" in t["name"].lower() or "agent" in t["description"].lower()
            for t in data["templates"]
        )

    def test_filter_by_tag(self, client):
        client.post("/api/prompt-templates/seed")
        resp = client.get("/api/prompt-templates?tag=code")
        data = resp.json()
        assert all("code" in t["tags"] for t in data["templates"])

    def test_list_categories(self, client):
        client.post("/api/prompt-templates/seed")
        resp = client.get("/api/prompt-templates/categories")
        data = resp.json()
        assert resp.status_code == 200
        assert "categories" in data
