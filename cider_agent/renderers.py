"""Thin transport renderers for cider_agent."""

from __future__ import annotations

from typing import Any

from .results import EngineActionResult, TextRequestResult


def render_text_result_for_a2a(result: TextRequestResult) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = result.execution.result if isinstance(result.execution.result, dict) else {"value": result.execution.result}
    metadata: dict[str, Any] = {
        "action": result.execution.action,
        "summary": result.summary or "",
        "resolver": result.resolver,
        "resolved_action": result.resolved_action,
    }
    if result.reasoning:
        metadata["reasoning"] = result.reasoning
    if result.resolver_raw_content:
        metadata["resolver_raw_content"] = result.resolver_raw_content
    if result.resolver_raw_action is not None:
        metadata["resolver_raw_action"] = result.resolver_raw_action
    if result.timings is not None:
        metadata["timings"] = result.timings
    return payload, metadata


def render_action_result_for_a2a(result: EngineActionResult) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = result.result if isinstance(result.result, dict) else {"value": result.result}
    return payload, {
        "action": result.action,
        "summary": str(payload.get("summary", "")).strip() if isinstance(payload, dict) else "",
    }


def render_task_payload_for_cli(task: dict[str, Any], *, original_text: str | None = None) -> dict[str, Any]:
    payload = _extract_task_payload(task)
    metadata = task.get("metadata", {}) if isinstance(task.get("metadata"), dict) else {}
    action = metadata.get("action")
    if original_text is None:
        return payload
    response: dict[str, Any] = {
        "status": "ok",
        "input": original_text,
        "resolver": metadata.get("resolver"),
        "resolved_action": metadata.get("resolved_action", {"action": action} if action else {}),
        "execution": {
            "action": action,
            "result": payload,
        },
    }
    if metadata.get("summary"):
        response["summary"] = metadata["summary"]
    if "reasoning" in metadata:
        response["reasoning"] = metadata["reasoning"]
    if "resolver_raw_content" in metadata:
        response["resolver_raw_content"] = metadata["resolver_raw_content"]
    if "resolver_raw_action" in metadata:
        response["resolver_raw_action"] = metadata["resolver_raw_action"]
    if "timings" in metadata:
        response["timings"] = metadata["timings"]
    return response


def _extract_data_part(parts: Any) -> dict[str, Any] | None:
    if not isinstance(parts, list):
        return None
    for part in parts:
        if isinstance(part, dict) and part.get("kind") == "data" and isinstance(part.get("data"), dict):
            return dict(part["data"])
    return None


def _extract_task_payload(task: dict[str, Any]) -> dict[str, Any]:
    artifacts = task.get("artifacts", [])
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            payload = _extract_data_part(artifact.get("parts", []))
            if payload is not None:
                return payload
    raise ValueError("Task did not include a data artifact.")
