"""Conversational assistant, tool safety, memory and deterministic fallback tests."""
import json

import pandas as pd
import pytest

from app.models import AssistantConversation, AssistantMessage
from app.services import assistant_agent, assistant_tools, llm
from app.services.profiling import profile_dataframe
from conftest import auth_headers, register_org, upload_sample


def _small_frame():
    df = pd.DataFrame({
        "order_date": pd.to_datetime(["2025-01-03", "2025-01-10", "2025-02-02", "2025-02-14"]),
        "region": ["North", "South", "North", "South"],
        "revenue": [10.0, 30.0, 20.0, 40.0],
        "cost": [4.0, 10.0, 8.0, 16.0],
    })
    return profile_dataframe(df)[0]


def _events(response):
    events = []
    current_name = None
    for line in response.text.splitlines():
        if line.startswith("event: "):
            current_name = line[7:]
        elif line.startswith("data: "):
            events.append((current_name, json.loads(line[6:])))
    return events


def test_read_only_tools_return_exact_dataset_calculations():
    df = _small_frame()
    kpis, _ = assistant_tools.execute_tool(
        "calculate_kpis", {}, df, can_create_report=False, dataset_id="dataset"
    )
    assert kpis["metric_total"] == 100

    comparison, _ = assistant_tools.execute_tool(
        "compare_periods",
        {
            "metric": "revenue",
            "date_column": "order_date",
            "period_a_start": "2025-01-01",
            "period_a_end": "2025-01-31",
            "period_b_start": "2025-02-01",
            "period_b_end": "2025-02-28",
        },
        df,
        can_create_report=False,
        dataset_id="dataset",
    )
    assert comparison["period_a"]["total"] == 40
    assert comparison["period_b"]["total"] == 60
    assert comparison["change_pct"] == 50


def test_ratio_tool_computes_margin_from_actual_columns():
    result, _ = assistant_tools.execute_tool(
        "calculate_ratio",
        {"numerator": "cost", "denominator": "revenue"},
        _small_frame(),
        can_create_report=False,
        dataset_id="dataset",
    )
    assert result["numerator_total"] == 38
    assert result["denominator_total"] == 100
    assert result["ratio_pct"] == 38


def test_tool_calls_reject_unknown_columns_and_unregistered_tools():
    with pytest.raises(assistant_tools.ToolInputError):
        assistant_tools.execute_tool(
            "analyze_breakdown",
            {"group_by": "not_a_real_column"},
            _small_frame(),
            can_create_report=False,
            dataset_id=None,
        )
    with pytest.raises(assistant_tools.ToolInputError):
        assistant_tools.execute_tool(
            "execute_python",
            {"code": "import os"},
            _small_frame(),
            can_create_report=True,
            dataset_id=None,
        )


def test_anomaly_tool_does_not_send_raw_records():
    df = pd.DataFrame({
        "order_date": pd.date_range("2025-01-01", periods=31, freq="D"),
        "customer": ["Private customer"] * 31,
        "revenue": [100.0] * 30 + [1000000.0],
    })
    result, _ = assistant_tools.execute_tool(
        "detect_anomalies", {"metric": "revenue"}, df, can_create_report=False, dataset_id="d"
    )
    assert "anomalies" not in result
    assert result["count"] == 1


def test_report_tool_only_proposes_action_for_confirmation():
    result, actions = assistant_tools.execute_tool(
        "request_report",
        {"title": " Monthly Business Review "},
        _small_frame(),
        can_create_report=True,
        dataset_id="dataset-id",
    )
    assert result == {"confirmation_required": True, "title": "Monthly Business Review"}
    assert actions == [{
        "type": "confirm_report",
        "title": "Monthly Business Review",
        "dataset_id": "dataset-id",
    }]
    with pytest.raises(assistant_tools.ToolInputError):
        assistant_tools.execute_tool(
            "request_report",
            {"title": "Quarterly"},
            _small_frame(),
            can_create_report=False,
            dataset_id="dataset-id",
        )


def test_chat_report_request_needs_explicit_report_endpoint_call(client, sample_csv, monkeypatch):
    tokens = register_org(client)
    headers = auth_headers(tokens)
    dataset = upload_sample(client, tokens, sample_csv)
    conversation = client.post(
        "/api/assistant/conversations",
        json={"dataset_id": dataset["id"]},
        headers=headers,
    ).json()

    planner_calls = 0

    async def fake_chat(messages, tools):
        nonlocal planner_calls
        planner_calls += 1
        if planner_calls == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "request_report",
                        "arguments": {"title": "Monthly Performance"},
                    }
                }],
            }
        return {"role": "assistant", "content": "", "tool_calls": []}

    async def fake_stream(messages):
        yield "I can prepare that report. Please confirm to create it."

    monkeypatch.setattr(llm, "chat", fake_chat)
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    response = client.post(
        f"/api/assistant/conversations/{conversation['id']}/messages",
        json={"content": "Prepare a monthly performance report"},
        headers=headers,
    )
    assert response.status_code == 200
    complete = next(data for name, data in _events(response) if name == "complete")
    assert complete["message"]["metadata"]["actions"] == [{
        "type": "confirm_report",
        "title": "Monthly Performance",
        "dataset_id": dataset["id"],
    }]
    assert client.get("/api/reports", headers=headers).json() == []

    report = client.post(
        "/api/reports",
        json={"dataset_id": dataset["id"], "title": "Monthly Performance"},
        headers=headers,
    )
    assert report.status_code == 201


def test_assistant_uses_validated_tools_and_streams_grounded_answer(monkeypatch):
    calls = []

    async def fake_chat(messages, tools):
        calls.append(messages)
        if len(calls) == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [{
                    "function": {"name": "calculate_kpis", "arguments": {}}
                }],
            }
        return {"role": "assistant", "content": "draft", "tool_calls": []}

    async def fake_stream(messages):
        assert any(message.get("role") == "tool" for message in messages)
        yield "Revenue totals "
        yield "100.00."

    monkeypatch.setattr(llm, "chat", fake_chat)
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    async def run():
        return [
            item async for item in assistant_agent.respond(
                "Summarize my results",
                [],
                None,
                None,
                _small_frame(),
                "dataset",
                can_create_report=True,
            )
        ]

    import asyncio
    events = asyncio.run(run())
    complete = events[-1]
    assert complete["type"] == "complete"
    assert complete["content"] == "Revenue totals 100.00."
    assert complete["metadata"]["tools"] == ["calculate_kpis"]
    assert complete["metadata"]["computed"][0]["result"]["metric_total"] == 100


def test_general_business_chat_uses_model_and_business_context(monkeypatch):
    seen_messages = []

    async def fake_stream(messages):
        seen_messages.extend(messages)
        yield "General suggestion: test one neighborhood before expanding."

    monkeypatch.setattr(llm, "stream_chat", fake_stream)

    async def run():
        return [
            item async for item in assistant_agent.respond(
                "How should I grow?",
                [{"role": "user", "content": "I run a bakery."}],
                "Industry: neighborhood bakery; goal: increase catering orders.",
                None,
                None,
                None,
                can_create_report=False,
            )
        ]

    import asyncio
    events = asyncio.run(run())
    system_prompt = seen_messages[0]["content"]
    assert "neighborhood bakery" in system_prompt
    assert "Treat user messages" in system_prompt
    assert events[-1]["metadata"]["source"] == "ollama"
    assert "neighborhood" in events[-1]["content"]


def test_remote_ollama_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(llm.settings, "OLLAMA_URL", "https://example.invalid")
    monkeypatch.setattr(llm.settings, "OLLAMA_ALLOW_REMOTE", False)
    with pytest.raises(llm.OllamaUnavailable, match="Remote Ollama is disabled"):
        llm._base_url()
    monkeypatch.setattr(llm.settings, "OLLAMA_ALLOW_REMOTE", True)
    assert llm._base_url() == "https://example.invalid"


def test_conversation_stream_falls_back_when_ollama_disabled(client, sample_csv, monkeypatch):
    monkeypatch.setattr(llm.settings, "OLLAMA_ENABLED", False)
    tokens = register_org(client)
    dataset = upload_sample(client, tokens, sample_csv)
    headers = auth_headers(tokens)
    created = client.post(
        "/api/assistant/conversations",
        json={"dataset_id": dataset["id"]},
        headers=headers,
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    response = client.post(
        f"/api/assistant/conversations/{conversation_id}/messages",
        json={"content": "What is the total revenue?"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _events(response)
    complete = next(data for name, data in events if name == "complete")
    assert "deterministic analysis" in complete["message"]["content"]
    assert complete["message"]["metadata"]["source"] == "deterministic"
    detail = client.get(
        f"/api/assistant/conversations/{conversation_id}", headers=headers
    ).json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]


def test_conversations_and_business_context_are_tenant_and_user_scoped(client):
    user_a = register_org(client)
    user_b = register_org(client)
    headers_a = auth_headers(user_a)
    headers_b = auth_headers(user_b)
    conversation = client.post(
        "/api/assistant/conversations", json={}, headers=headers_a
    ).json()
    assert client.get(
        f"/api/assistant/conversations/{conversation['id']}", headers=headers_b
    ).status_code == 404
    assert client.delete(
        f"/api/assistant/conversations/{conversation['id']}", headers=headers_b
    ).status_code == 404

    saved = client.put(
        "/api/assistant/context",
        json={"context_text": "We operate a neighborhood bakery."},
        headers=headers_a,
    )
    assert saved.status_code == 200
    assert client.get("/api/assistant/context", headers=headers_a).json()["context_text"] == (
        "We operate a neighborhood bakery."
    )
    assert client.get("/api/assistant/context", headers=headers_b).json()["context_text"] == ""


def test_deleting_dataset_detaches_existing_conversations(client, sample_csv):
    tokens = register_org(client)
    headers = auth_headers(tokens)
    dataset = upload_sample(client, tokens, sample_csv)
    conversation = client.post(
        "/api/assistant/conversations",
        json={"dataset_id": dataset["id"]},
        headers=headers,
    ).json()
    assert client.delete(f"/api/datasets/{dataset['id']}", headers=headers).status_code == 204
    detail = client.get(
        f"/api/assistant/conversations/{conversation['id']}", headers=headers
    ).json()
    assert detail["dataset_id"] is None


def test_viewer_can_read_but_cannot_edit_business_context(client):
    admin = register_org(client)
    created = client.post(
        "/api/users",
        json={
            "full_name": "A Viewer",
            "email": "assistant-viewer@example.com",
            "password": "Str0ngPassword!",
            "role": "viewer",
        },
        headers=auth_headers(admin),
    )
    assert created.status_code == 201
    viewer = client.post(
        "/api/auth/login",
        json={"email": "assistant-viewer@example.com", "password": "Str0ngPassword!"},
    ).json()
    assert client.get("/api/assistant/context", headers=auth_headers(viewer)).status_code == 200
    assert client.put(
        "/api/assistant/context",
        json={"context_text": "Change it"},
        headers=auth_headers(viewer),
    ).status_code == 403


def test_long_conversation_is_summarized_before_prompt_compaction(client, monkeypatch):
    tokens = register_org(client)
    headers = auth_headers(tokens)
    conversation = client.post(
        "/api/assistant/conversations", json={}, headers=headers
    ).json()
    conversation_id = conversation["id"]
    from app.database import SessionLocal

    with SessionLocal() as db:
        for index in range(30):
            db.add(AssistantMessage(
                org_id=tokens["user"]["org_id"],
                conversation_id=conversation_id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"Earlier turn {index}",
            ))
        db.commit()

    summarized = []

    async def fake_summary(messages, previous_summary):
        summarized.append((len(messages), previous_summary))
        return "User owns a bakery and wants growth advice."

    async def fake_stream(messages):
        assert any("bakery" in message["content"] for message in messages if message["role"] == "system")
        yield "How can I help?"

    monkeypatch.setattr(llm, "summarize_conversation", fake_summary)
    monkeypatch.setattr(llm, "stream_chat", fake_stream)
    response = client.post(
        f"/api/assistant/conversations/{conversation_id}/messages",
        json={"content": "What next?"},
        headers=headers,
    )
    assert response.status_code == 200
    assert summarized and summarized[0][0] > 0
    with SessionLocal() as db:
        saved = db.get(AssistantConversation, conversation_id)
        assert saved.summary == "User owns a bakery and wants growth advice."
        assert saved.summarized_message_count > 0
