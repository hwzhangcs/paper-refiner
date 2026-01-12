import json
import os
from typing import List, Dict, Optional, Any, Union
import logging
from paper_refiner.models import get_pass_for_issue_type, PASS_DEFINITIONS, Issue

ISSUE_TYPE_TO_PASS = {}
for pid, config in PASS_DEFINITIONS.items():
    for itype in config.issue_types:
        ISSUE_TYPE_TO_PASS[itype] = pid


# Re-export or reconstruct for backward compatibility
ISSUE_TYPE_TO_PASS = {}
for pid, config in PASS_DEFINITIONS.items():
    for itype in config.issue_types:
        ISSUE_TYPE_TO_PASS[itype] = pid


class IssueTracker:
    """
    Manages the lifecycle of issues (open -> resolved).
    Persists state to issues.json.

    Extended for multi-iteration architecture with:
    - iteration: Which iteration this issue was discovered
    - pass_id: Which pass (1-5) this issue belongs to
    - type: Issue type for automatic pass classification
    - resolved_in_iteration: When it was resolved
    - resolved_in_pass: Which pass resolved it
    """

    def __init__(self, storage_path: str):
        self.storage_path = os.path.abspath(storage_path)
        self.logger = logging.getLogger(__name__)
        self.issues: List[Issue] = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    raw_issues = data.get("issues", [])
                    self.issues = [Issue.from_dict(i) for i in raw_issues]
            except Exception as e:
                self.logger.error(
                    f"Failed to load issues from {self.storage_path}: {e}"
                )
                self.issues = []
        else:
            self.issues = []

    def save(self):
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json_data = {"issues": [i.to_dict() for i in self.issues]}
                json.dump(json_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Failed to save issues to {self.storage_path}: {e}")

    def add_issues(
        self,
        new_issues: List[Dict[str, Any]],
        iteration: int = 0,
        pass_id: Optional[int] = None,
    ):
        """
        Adds new issues with iteration/pass tracking.

        Args:
            new_issues: List of issue dictionaries from ReviewerAgent
            iteration: Current iteration number (0 = initial)
            pass_id: Current pass (1-5) or None for auto-detection
        """
        existing_ids = {i.id for i in self.issues}
        for issue_dict in new_issues:
            if issue_dict["id"] not in existing_ids:
                # Set default values
                if "status" not in issue_dict:
                    issue_dict["status"] = "open"

                # Add iteration tracking
                issue_dict["iteration"] = iteration

                # Add pass_id (auto-detect from type if not specified)
                if pass_id is not None:
                    issue_dict["pass_id"] = pass_id
                elif "type" in issue_dict:
                    issue_dict["pass_id"] = self.classify_issue_by_pass(issue_dict)
                else:
                    issue_dict["pass_id"] = 0  # Unknown

                # Initialize resolution tracking
                issue_dict["resolved_in_iteration"] = None
                issue_dict["resolved_in_pass"] = None

                # Convert to Issue object
                issue_obj = Issue.from_dict(issue_dict)
                self.issues.append(issue_obj)
                existing_ids.add(issue_obj.id)
        self.save()

    def get_open_issues(
        self,
        iteration: Optional[int] = None,
        pass_id: Optional[int] = None,
        priority_filter: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Issue]:
        """
        Returns open issues with advanced filtering.

        Args:
            iteration: Filter by iteration number
            pass_id: Filter by pass (1-5)
            priority_filter: Filter by priority (e.g. ['P0', 'P1'])
            limit: Maximum number of issues to return

        Returns:
            List of filtered open Issue objects
        """
        result = []
        for issue in self.issues:
            # Status filter
            if issue.status != "open":
                continue

            # Iteration filter
            if iteration is not None and issue.iteration != iteration:
                continue

            # Pass filter
            if pass_id is not None and issue.pass_id != pass_id:
                continue

            # Priority filter
            if priority_filter and issue.priority not in priority_filter:
                continue

            result.append(issue)

            # Apply limit
            if limit is not None and len(result) >= limit:
                break

        return result

    def get_issue(self, issue_id: str) -> Optional[Issue]:
        for issue in self.issues:
            if issue.id == issue_id:
                return issue
        return None

    def update_status(
        self,
        issue_id: str,
        status: str,
        history_entry: Optional[str] = None,
        resolved_in_iteration: Optional[int] = None,
        resolved_in_pass: Optional[int] = None,
    ):
        """
        Update issue status with resolution tracking.
        """
        for issue in self.issues:
            if issue.id == issue_id:
                issue.status = status

                # Track resolution
                if status == "resolved":
                    if resolved_in_iteration is not None:
                        issue.resolved_in_iteration = resolved_in_iteration
                    if resolved_in_pass is not None:
                        issue.resolved_in_pass = resolved_in_pass

                # History tracking
                if history_entry:
                    issue.history.append(history_entry)

                self.save()
                return
        self.logger.warning(f"Issue {issue_id} not found for update.")

    def all_resolved(self, priority_filter: Optional[List[str]] = None) -> bool:
        """
        Checks if all issues (optionally of specific priority) are resolved.
        """
        for issue in self.issues:
            if priority_filter and issue.priority not in priority_filter:
                continue
            if issue.status == "open":
                return False
        return True

    def classify_issue_by_pass(self, issue_dict: Dict[str, Any]) -> int:
        """
        Classify an issue to determine which pass (1-5) it belongs to.
        Accepts a dictionary because classification happens before object creation.

        Args:
            issue_dict: Issue dictionary with 'type' field

        Returns:
            Pass number (1-5), or 0 if cannot classify
        """
        issue_type = issue_dict.get("type", "").lower()

        # Direct lookup via models (Single Source of Truth)
        pass_id = get_pass_for_issue_type(issue_type)
        if pass_id:
            return pass_id

        # Fuzzy matching using Pass Definitions from models
        description = issue_dict.get("details", "").lower()
        combined_text = f"{issue_type} {description}"

        for pid, config in PASS_DEFINITIONS.items():
            # Check against issue types as keywords
            if any(kw in combined_text for kw in config.issue_types):
                return pid

            # Check against pass name parts (e.g. 'structure' -> Pass 1)
            name_parts = config.name.lower().split()
            if any(part in combined_text for part in name_parts if len(part) > 3):
                return pid

        # Default: cannot classify
        return 0

    def get_statistics(self, iteration: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics about issues.
        """
        stats = {
            "total": 0,
            "open": 0,
            "resolved": 0,
            "by_priority": {"P0": 0, "P1": 0, "P2": 0},
            "by_pass": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 0: 0},
            "new_issues_p0": 0,
            "new_issues_p1": 0,
            "new_issues_p2": 0,
        }

        for issue in self.issues:
            # Filter by iteration if specified
            if iteration is not None and issue.iteration != iteration:
                continue

            stats["total"] += 1

            # Status
            if issue.status == "open":
                stats["open"] += 1
            elif issue.status == "resolved":
                stats["resolved"] += 1

            # Priority
            priority = issue.priority or "P2"
            if priority in stats["by_priority"]:
                stats["by_priority"][priority] += 1

            # Track new issues for this iteration
            if iteration is not None and issue.iteration == iteration:
                if priority == "P0":
                    stats["new_issues_p0"] += 1
                elif priority == "P1":
                    stats["new_issues_p1"] += 1
                elif priority == "P2":
                    stats["new_issues_p2"] += 1

            # Pass
            pass_id = issue.pass_id or 0
            if pass_id in stats["by_pass"]:
                stats["by_pass"][pass_id] += 1

        return stats
