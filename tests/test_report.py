#!/usr/bin/env python3
"""
Complete system test report (14 checks).
"""
from __future__ import annotations

import os
import sys

import importlib.util
import json
from dataclasses import dataclass
from typing import Dict, List, Tuple

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""


def _print_header() -> None:
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           Paper Refiner System - Complete Test Report        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def _find_missing_modules(modules: List[str]) -> List[str]:
    missing = []
    for module in modules:
        if importlib.util.find_spec(module) is None:
            missing.append(module)
    return missing


def _check_environment() -> Tuple[CheckResult, Dict[str, str]]:
    details: Dict[str, str] = {}
    if sys.version_info < (3, 10):
        return CheckResult(
            name="Environment Check",
            passed=False,
            message=f"Python {sys.version.split()[0]} is not supported. Requires 3.10+",
        ), details
    details["Python"] = sys.version.split()[0]

    deps = ["openai", "requests", "tenacity", "playwright"]
    missing = _find_missing_modules(deps)
    if missing:
        return CheckResult(
            name="Environment Check",
            passed=False,
            message=f"Missing dependencies: {', '.join(missing)}",
        ), details
    details["Dependencies"] = "All installed"
    return CheckResult(name="Environment Check", passed=True), details


def _check_module_structure() -> Tuple[CheckResult, Dict[str, str]]:
    details: Dict[str, str] = {}
    package_ok = importlib.util.find_spec("paper_refiner") is not None
    details["paper_refiner package"] = "OK" if package_ok else "Missing"

    core_modules = [
        "paper_refiner.core.issue_tracker",
        "paper_refiner.core.section_version_manager",
        "paper_refiner.core.revision_recorder",
        "paper_refiner.agents.reviewer",
        "paper_refiner.agents.editor",
    ]
    missing = _find_missing_modules(core_modules)
    details["Core modules"] = f"{len(core_modules) - len(missing)}/{len(core_modules)} found"
    passed = package_ok and not missing
    return CheckResult(name="Module Structure", passed=passed, message=", ".join(missing)), details


def _check_sdk_tests() -> Tuple[CheckResult, Dict[str, str], int]:
    details: Dict[str, str] = {}
    try:
        try:
            import test_all  # type: ignore
        except Exception:
            from tests import test_all  # type: ignore
    except Exception as exc:  # noqa: BLE001 - test runner
        details["Yuketang API"] = "0/6 tests passed"
        return (
            CheckResult(name="SDK Tests", passed=False, message=str(exc)),
            details,
            0,
        )

    passed, total, _ = test_all.run_tests(verbose=False)
    details["Yuketang API"] = f"{passed}/{total} tests passed"
    return CheckResult(name="SDK Tests", passed=(passed == total)), details, passed


def _check_core_modules() -> Tuple[
    Tuple[CheckResult, Dict[str, str]],
    Tuple[CheckResult, Dict[str, str]],
]:
    try:
        try:
            import test_modules  # type: ignore
        except Exception:
            from tests import test_modules  # type: ignore
    except Exception as exc:  # noqa: BLE001 - test runner
        core_details = {
            "IssueTracker": "Failed",
            "SectionVersionManager": "Failed",
            "RevisionRecorder": "Failed",
        }
        core_check = CheckResult(name="Core Components", passed=False, message=str(exc))
        orchestrator_details = {"PaperRefinerOrchestrator": "Failed"}
        orchestrator_check = CheckResult(name="Orchestrator", passed=False, message=str(exc))
        return (core_check, core_details), (orchestrator_check, orchestrator_details)

    _, _, results = test_modules.run_tests(verbose=False)
    result_map = {result.name: result for result in results}

    core_details: Dict[str, str] = {}
    issue_result = result_map.get("test_issue_tracker")
    section_result = result_map.get("test_section_version_manager")
    recorder_result = result_map.get("test_revision_recorder")

    issue_ok = issue_result.passed if issue_result else False
    section_ok = section_result.passed if section_result else False
    recorder_ok = recorder_result.passed if recorder_result else False

    core_details["IssueTracker"] = "OK" if issue_ok else "Failed"
    core_details["SectionVersionManager"] = "OK" if section_ok else "Failed"
    core_details["RevisionRecorder"] = "OK" if recorder_ok else "Failed"
    core_check = CheckResult(
        name="Core Components",
        passed=issue_ok and section_ok and recorder_ok,
    )

    orchestrator_details: Dict[str, str] = {}
    orchestrator_result = result_map.get("test_orchestrator_init")
    orchestrator_ok = orchestrator_result.passed if orchestrator_result else False
    orchestrator_details["PaperRefinerOrchestrator"] = (
        "Initialized successfully" if orchestrator_ok else "Failed"
    )
    orchestrator_check = CheckResult(
        name="Orchestrator",
        passed=orchestrator_ok,
    )

    return (core_check, core_details), (orchestrator_check, orchestrator_details)


def _check_workspace_setup() -> Tuple[CheckResult, Dict[str, str]]:
    details: Dict[str, str] = {}
    os.makedirs("run_workspace", exist_ok=True)
    details["run_workspace/"] = "Created"

    issues_path = os.path.join("run_workspace", "issues.json")
    if not os.path.exists(issues_path):
        with open(issues_path, "w", encoding="utf-8") as f:
            json.dump({"issues": []}, f, indent=2)
    details["issues.json"] = "Exists" if os.path.exists(issues_path) else "Missing"
    passed = os.path.exists(issues_path)
    return CheckResult(name="Workspace Setup", passed=passed), details


def _check_documentation() -> Tuple[CheckResult, Dict[str, str]]:
    details: Dict[str, str] = {}
    docs_dir = "docs"
    required = [
        "GETTING_STARTED.md",
        "ARCHITECTURE.md",
        "USER_GUIDE.md",
        "API_REFERENCE.md",
    ]
    if not os.path.isdir(docs_dir):
        return CheckResult(name="Documentation", passed=False, message="docs/ missing"), details
    missing = [name for name in required if not os.path.exists(os.path.join(docs_dir, name))]
    details["docs/ structure"] = "Complete" if not missing else f"Missing: {', '.join(missing)}"
    return CheckResult(name="Documentation", passed=not missing), details


def _print_section(check: CheckResult, details: Dict[str, str]) -> None:
    icon = "✅" if check.passed else "❌"
    print(f"{icon} {check.name}")
    for key, value in details.items():
        print(f"   {key}: {value}")
    if not check.passed and check.message:
        print(f"   Error: {check.message}")
    print()


def main() -> None:
    _print_header()

    env_check = _check_environment()
    module_check = _check_module_structure()
    sdk_check, sdk_details, sdk_passed = _check_sdk_tests()
    core_check, orchestrator_check = _check_core_modules()
    workspace_check = _check_workspace_setup()
    docs_check = _check_documentation()

    checks: List[Tuple[CheckResult, Dict[str, str]]] = [
        env_check,
        module_check,
        (sdk_check, sdk_details),
        core_check,
        orchestrator_check,
        workspace_check,
        docs_check,
    ]

    for check, details in checks:
        _print_section(check, details)

    sdk_passed = min(sdk_passed, 6)
    core_component_passed = 0
    if core_check[0].passed:
        core_component_passed = 3
    else:
        core_component_passed = sum(
            1
            for label in ("IssueTracker", "SectionVersionManager", "RevisionRecorder")
            if core_check[1].get(label) == "OK"
        )

    total_checks = 14
    passed_count = (
        int(env_check[0].passed)
        + int(module_check[0].passed)
        + sdk_passed
        + core_component_passed
        + int(orchestrator_check[0].passed)
        + int(workspace_check[0].passed)
        + int(docs_check[0].passed)
    )
    overall_passed = passed_count == total_checks
    status_icon = "✅" if overall_passed else "❌"

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 Summary: {passed_count}/{total_checks} checks passed {status_icon}")
    if overall_passed:
        print("System is ready to use!")


if __name__ == "__main__":
    main()
