from __future__ import annotations


def test_legacy_execute_and_generic_llm_suggest_remain_disabled(client, auth_headers: dict[str, str]) -> None:
    execute = client.post("/api/execute", headers=auth_headers, json={"confirm": True, "items": []})
    llm = client.post("/api/llm/suggest", headers=auth_headers, json={"items": []})

    assert execute.status_code == 410
    assert execute.json()["error_code"] == "legacy_execute_disabled"
    assert llm.status_code == 410
    assert llm.json()["error_code"] == "legacy_llm_suggest_disabled"
