#!/usr/bin/env python3
"""
Core module tests (IssueTracker, SectionVersionManager, RevisionRecorder, Orchestrator).
"""
from __future__ import annotations

import os
import sys

import json
import tempfile
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from paper_refiner.core.issue_tracker import IssueTracker
from paper_refiner.core.section_version_manager import SectionVersionManager
from paper_refiner.core.revision_recorder import RevisionRecorder
from paper_refiner.models import RevisionRecord
from paper_refiner.orchestrator import PaperRefinerOrchestrator


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""


def _print_result(result: TestResult) -> None:
    if result.passed:
        print(f"✅ {result.name}: PASSED")
    else:
        print(f"❌ {result.name}: FAILED - {result.message}")


def run_tests(verbose: bool = True) -> Tuple[int, int, List[TestResult]]:
    results: List[TestResult] = []

    def run(name: str, func) -> None:
        try:
            func()
            result = TestResult(name=name, passed=True)
        except Exception as exc:  # noqa: BLE001 - test runner
            result = TestResult(name=name, passed=False, message=str(exc))
        results.append(result)
        if verbose:
            _print_result(result)

    def test_issue_tracker() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            issues_path = os.path.join(temp_dir, "issues.json")
            tracker = IssueTracker(issues_path)
            tracker.add_issues(
                [
                    {
                        "id": "P0-1",
                        "priority": "P0",
                        "title": "Test issue",
                        "details": "Test details",  # Added required field
                        "acceptance_criteria": "Test acceptance",
                    }
                ]
            )
            open_issues = tracker.get_open_issues()
            if len(open_issues) != 1:
                raise ValueError("expected 1 open issue")
            
            # Use object attribute access
            if open_issues[0].id != "P0-1":
                raise ValueError("Issue ID mismatch")

            tracker.update_status("P0-1", "resolved", "test pass")
            tracker_reloaded = IssueTracker(issues_path)
            issue = tracker_reloaded.get_issue("P0-1")
            
            # Use object attribute access
            if not issue or issue.status != "resolved":
                raise ValueError("issue status did not persist")
            if not issue.history:
                raise ValueError("issue history not saved")

    def test_section_version_manager() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = os.path.join(temp_dir, "work")
            os.makedirs(work_dir, exist_ok=True)
            paper_path = os.path.join(temp_dir, "paper.tex")
            with open(paper_path, "w", encoding="utf-8") as f:
                f.write(
                    "\\documentclass{article}\n"
                    "\\begin{document}\n"
                    "\\section{Introduction}\n"
                    "Intro text.\n"
                    "\\section{Method}\n"
                    "Method text.\n"
                    "\\end{document}\n"
                )

            manager = SectionVersionManager(Path(work_dir)) # Pass Path
            # Pass Path object
            sections = manager.extract_sections(Path(paper_path)) 
            if "introduction" not in sections:
                raise ValueError("introduction section not found")

            manager.save_section_original("introduction", sections["introduction"])
            expected = os.path.join(work_dir, "sections", "introduction", "original.tex")
            if not os.path.exists(expected):
                raise ValueError("original section not saved")

    def test_revision_recorder() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = os.path.join(temp_dir, "work")
            recorder = RevisionRecorder(work_dir)
            record = RevisionRecord(
                revision_id="iter1_pass1_r1_P0-1",
                iteration=1,
                pass_id=1,
                round_num=1,
                issue_id="P0-1",
                issue_title="Test issue",
                issue_priority="P0",
                issue_details="Test details",
                section_id="introduction",
                rationale="Test rationale",
                patch="{\"operations\": []}",
                verification_status="resolved",
                verification_message="Verified",
                timestamp="2024-01-01T00:00:00",
                tokens_changed=0,
            )
            recorder.record_revision(record)
            expected = os.path.join(
                work_dir,
                "revision_records",
                "iter1",
                "pass1",
                "round1_P0-1.json",
            )
            if not os.path.exists(expected):
                raise ValueError("revision record not saved")

    def test_orchestrator_init() -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paper_path = os.path.join(temp_dir, "paper.tex")
            with open(paper_path, "w", encoding="utf-8") as f:
                f.write("\\documentclass{article}\\begin{document}Test\\end{document}")
            work_dir = os.path.join(temp_dir, "run_workspace")
            orchestrator = PaperRefinerOrchestrator(
                paper_path=paper_path,
                work_dir=work_dir,
                ykt_cookies={},
                openai_key="test",
                openai_base_url="http://localhost:1",
                openai_model="gpt-4o",
            )
            expected = os.path.join(work_dir, "sections")
            if not os.path.isdir(expected):
                raise ValueError("sections directory not created")

    run("test_issue_tracker", test_issue_tracker)
    run("test_section_version_manager", test_section_version_manager)
    run("test_revision_recorder", test_revision_recorder)
    run("test_orchestrator_init", test_orchestrator_init)

    passed = sum(1 for result in results if result.passed)
    total = len(results)
    return passed, total, results


def main() -> None:
    print("=== Core Module Tests ===")
    passed, total, _ = run_tests(verbose=True)
    print(f"\nSummary: {passed}/{total} tests passed")


if __name__ == "__main__":
    main()
