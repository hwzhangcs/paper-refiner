#!/usr/bin/env python3
"""
Yuketang SDK tests (6 checks).
"""
from __future__ import annotations

import os
import sys

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from paper_api.client import YuketangAIClient
from paper_api.config import load_conversation_id


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a JSON object")
    return data


def _print_result(result: TestResult) -> None:
    if result.passed:
        print(f"✅ {result.name}: PASSED")
    else:
        print(f"❌ {result.name}: FAILED - {result.message}")


def run_tests(verbose: bool = True) -> Tuple[int, int, List[TestResult]]:
    results: List[TestResult] = []
    context: Dict[str, Any] = {}

    def run(name: str, func) -> None:
        try:
            func()
            result = TestResult(name=name, passed=True)
        except Exception as exc:  # noqa: BLE001 - test runner
            result = TestResult(name=name, passed=False, message=str(exc))
        results.append(result)
        if verbose:
            _print_result(result)

    def test_load_cookies() -> None:
        cookies = _load_json("config/cookies.json")
        if not cookies:
            raise ValueError("cookies.json is empty")
        context["cookies"] = cookies

    def test_load_params() -> None:
        params = _load_json("config/session_params.json")
        required = ["agent_id", "capability_id", "classroom_id", "workflow_id"]
        missing = [key for key in required if key not in params]
        if missing:
            raise ValueError(f"session_params.json missing keys: {', '.join(missing)}")
        context["params"] = params

    def test_load_conversation_id() -> None:
        conv_id = load_conversation_id()
        if conv_id is None:
            raise ValueError("conversation_id not found in config/conversation_config.json")
        context["conversation_id"] = conv_id

    def _get_client() -> YuketangAIClient:
        cookies = context.get("cookies")
        params = context.get("params")
        conv_id = context.get("conversation_id")
        if not cookies or not params:
            raise ValueError("cookies/session_params not loaded")
        return YuketangAIClient(cookies=cookies, params=params, conversation_id=conv_id)

    def test_list_conversations() -> None:
        client = _get_client()
        conversations = client.list_conversations()
        if conversations is None:
            raise ValueError("list_conversations returned None")
        if not isinstance(conversations, list):
            raise ValueError("list_conversations did not return a list")

    def test_send_message() -> None:
        client = _get_client()
        stamp = time.strftime("%H:%M:%S")
        reply = client.send_message(
            f"ping test_all.py {stamp}",
            stream=False,
            allow_create_conversation=False,
        )
        if not reply:
            raise ValueError("send_message returned empty response")

    def test_openai_format() -> None:
        client = _get_client()
        stamp = time.strftime("%H:%M:%S")
        reply = client.chat_openai_format(
            [{"role": "user", "content": f"ping openai_format {stamp}"}]
        )
        if not reply:
            raise ValueError("chat_openai_format returned empty response")

    run("test_load_cookies", test_load_cookies)
    run("test_load_params", test_load_params)
    run("test_load_conversation_id", test_load_conversation_id)
    run("test_list_conversations", test_list_conversations)
    run("test_send_message", test_send_message)
    run("test_openai_format", test_openai_format)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    return passed, total, results


def main() -> None:
    print("=== Yuketang SDK Tests ===")
    passed, total, _ = run_tests(verbose=True)
    print(f"\nSummary: {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
