"""
Pass Coordinator for managing the 5-Pass refinement framework within an iteration.

This coordinator:
- Executes 5 passes sequentially within a single iteration
- Each pass has a specific focus (structure → coherence → paragraph → sentence → polish)
- Manages pass-specific review and repair loops
- Tracks progress and results for each pass
"""

from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime
import logging

from paper_refiner.models import (
    PassConfig,
    PassResult,
    RevisionRecord,
    PASS_NAMES,
    PASS_FOCUS,
)
import json
from paper_refiner.core.section_version_manager import SectionVersionManager
from paper_refiner.core.issue_tracker import IssueTracker
from paper_refiner.core.revision_recorder import RevisionRecorder
from paper_refiner.agents.reviewer import ReviewerAgent
from paper_refiner.agents.editor import EditorAgent
from paper_refiner.prompts import get_pass_prompt


class PassCoordinator:
    """Coordinates the execution of 5 passes within a single iteration.

    Each pass follows this workflow:
    1. Pass-specific review to identify issues
    2. Repair loop to fix issues (limited rounds)
    3. Save pass checkpoint
    4. Generate pass summary
    """

    def __init__(
        self,
        work_dir: Path,
        iteration_num: int,
        version_manager: SectionVersionManager,
        issue_tracker: IssueTracker,
        revision_recorder: RevisionRecorder,
        reviewer: ReviewerAgent,
        editor: EditorAgent,
        pass_configs: Optional[Dict[int, PassConfig]] = None,
    ):
        """Initialize the pass coordinator.

        Args:
            work_dir: Working directory for outputs
            iteration_num: Current iteration number
            version_manager: Section version manager instance
            issue_tracker: Issue tracker instance
            revision_recorder: Revision recorder instance
            reviewer: ReviewerAgent instance
            editor: EditorAgent instance
            pass_configs: Optional pass configurations (defaults to standard 5-pass)
        """
        self.work_dir = Path(work_dir)
        self.iteration_num = iteration_num
        self.version_manager = version_manager
        self.issue_tracker = issue_tracker
        self.revision_recorder = revision_recorder
        self.reviewer = reviewer
        self.editor = editor

        # Pass configurations
        self.pass_configs = pass_configs or self._get_default_pass_configs()

        # Logging
        self.logger = logging.getLogger(__name__)

        # Create pass checkpoints directory
        self.pass_checkpoints_dir = (
            self.work_dir / "versions" / f"iter{iteration_num}" / "pass_checkpoints"
        )
        self.pass_checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _get_default_pass_configs(self) -> Dict[int, PassConfig]:
        """Get default configuration for all 5 passes."""
        return {
            1: PassConfig(
                id=1,
                name="Document Structure",
                focus="Overall organization, thesis clarity, taxonomy soundness, scope",
                reviewer_prompt=get_pass_prompt(1),
                issue_types=["section_org", "taxonomy", "scope", "thesis"],
                max_rounds=3,
                priority_threshold="P0",
            ),
            2: PassConfig(
                id=2,
                name="Section Coherence",
                focus="Inter-section transitions, argument flow, balance",
                reviewer_prompt=get_pass_prompt(2),
                issue_types=[
                    "transitions",
                    "logic_flow",
                    "balance",
                    "section_coherence",
                ],
                max_rounds=3,
                priority_threshold="P0",
            ),
            3: PassConfig(
                id=3,
                name="Paragraph Quality",
                focus="Topic sentences, evidence synthesis, paragraph structure",
                reviewer_prompt=get_pass_prompt(3),
                issue_types=["topic_sentence", "evidence", "paragraph_structure"],
                max_rounds=3,
                priority_threshold="P1",
            ),
            4: PassConfig(
                id=4,
                name="Sentence Refinement",
                focus="Clarity, style, grammar, conciseness",
                reviewer_prompt=get_pass_prompt(4),
                issue_types=["clarity", "style", "grammar", "wordiness"],
                max_rounds=2,
                priority_threshold="P1",
            ),
            5: PassConfig(
                id=5,
                name="Final Polish",
                focus="Citations, typos, formatting, minor improvements",
                reviewer_prompt=get_pass_prompt(5),
                issue_types=["citation", "typo", "formatting", "minor"],
                max_rounds=2,
                priority_threshold="P2",
            ),
        }

    def execute_pass(self, pass_id: int, paper_path: Path) -> PassResult:
        """Execute a single pass of the refinement process.

        Args:
            pass_id: Pass number (1-5)
            paper_path: Path to the paper at the start of this pass

        Returns:
            PassResult with statistics and output path
        """
        config = self.pass_configs[pass_id]
        self.logger.info(f"\n  === Pass {pass_id}: {config.name} ===")
        self.logger.info(f"  Focus: {config.focus}")

        start_time = datetime.now()

        # Step 1: Pass-specific review
        self.logger.info(f"  Step 1: Reviewing with Pass {pass_id} focus...")
        new_issues_count = self._conduct_pass_review(
            pass_id, paper_path, config.reviewer_prompt
        )
        self.logger.info(f"  Found {new_issues_count} new issues for Pass {pass_id}")

        # Step 2: Repair loop (limited rounds)
        self.logger.info(f"  Step 2: Repair loop (max {config.max_rounds} rounds)...")
        issues_resolved, total_revisions, sections_modified = (
            self._run_pass_repair_loop(pass_id, config.max_rounds)
        )

        # Step 3: Save pass checkpoint
        self.logger.info(f"  Step 3: Saving Pass {pass_id} checkpoint...")
        output_path = self._save_pass_checkpoint(pass_id)

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Create pass result
        pass_result = PassResult(
            pass_id=pass_id,
            pass_name=config.name,
            issues_resolved=issues_resolved,
            total_revisions=total_revisions,
            sections_modified=list(sections_modified),
            output_paper_path=str(output_path),
            duration_seconds=duration,
            issues_created=new_issues_count,
        )

        self.logger.info(
            f"  Pass {pass_id} Summary: "
            f"{issues_resolved} resolved, "
            f"{total_revisions} revisions, "
            f"{len(sections_modified)} sections"
        )

        return pass_result

    def _conduct_pass_review(
        self, pass_id: int, paper_path: Path, pass_prompt: str
    ) -> int:
        """Conduct pass-specific review to identify issues.

        Args:
            pass_id: Current pass number
            paper_path: Path to paper to review

        Returns:
            Number of new issues found
        """
        # Get current section versions for context
        section_versions = {}
        section_ids = self.version_manager.list_sections()
        for section_id in section_ids:
            versions = self.version_manager.get_section_three_versions(
                section_id, self.iteration_num, pass_id
            )
            section_versions[section_id] = versions

        # Submit for pass-specific review
        new_issues = self.reviewer.submit_paper_for_pass_review(
            pass_id,
            str(paper_path),
            section_versions,
        )

        self._normalize_issue_sections(new_issues, section_ids)

        # Add issues with iteration and pass tracking
        for issue in new_issues:
            issue["iteration"] = self.iteration_num
            issue["pass_id"] = pass_id

        self.issue_tracker.add_issues(new_issues, self.iteration_num, pass_id)
        self.issue_tracker.save()

        return len(new_issues)

    def _normalize_issue_sections(
        self, issues: List[Dict[str, Any]], valid_sections: List[str]
    ) -> None:
        if not issues or not valid_sections:
            return

        for issue in issues:
            raw_sections = issue.get("affected_sections")
            if not isinstance(raw_sections, list) or not raw_sections:
                issue["affected_sections"] = []
                self.logger.warning(
                    f"Issue {issue.get('id')} missing affected_sections; skipping section mapping."
                )
                continue

            resolved_sections: List[str] = []
            for raw in raw_sections:
                raw_text = str(raw)
                resolved = self._resolve_section_id(raw_text, valid_sections)
                if resolved:
                    if resolved != raw_text:
                        self.logger.info(
                            f"Issue {issue.get('id')}: mapped section '{raw_text}' -> '{resolved}'"
                        )
                    resolved_sections.append(resolved)

            if not resolved_sections:
                issue["affected_sections"] = []
                self.logger.warning(
                    f"Issue {issue.get('id')} has no valid affected_sections after normalization."
                )
                continue

            # Preserve order while de-duplicating
            deduped = list(dict.fromkeys(resolved_sections))
            issue["affected_sections"] = deduped

    def _resolve_section_id(
        self, raw_section: str, valid_sections: List[str]
    ) -> Optional[str]:
        import re
        import difflib

        if raw_section in valid_sections:
            return raw_section

        if raw_section.strip().isdigit():
            idx = int(raw_section.strip())
            if 1 <= idx <= len(valid_sections):
                return valid_sections[idx - 1]

        normalized = self.version_manager.normalize_section_id(raw_section)
        if normalized in valid_sections:
            return normalized

        numeric_match = re.match(r"^section_(\d+)$", normalized)
        if numeric_match:
            idx = int(numeric_match.group(1))
            if 1 <= idx <= len(valid_sections):
                return valid_sections[idx - 1]

        normalized = re.sub(r"^section_\\d+_", "", normalized)
        if normalized in valid_sections:
            return normalized

        normalized = re.sub(r"^section_", "", normalized)
        if normalized in valid_sections:
            return normalized

        for section_id in valid_sections:
            if section_id in normalized or normalized in section_id:
                return section_id

        best_match = None
        best_score = 0.0
        for section_id in valid_sections:
            score = difflib.SequenceMatcher(None, normalized, section_id).ratio()
            if score > best_score:
                best_score = score
                best_match = section_id

        if best_match and best_score >= 0.6:
            return best_match

        return None

    def _run_pass_repair_loop(
        self, pass_id: int, max_rounds: int
    ) -> Tuple[int, int, Set[str]]:
        """Execute the repair loop for this pass.

        Args:
            pass_id: Current pass number
            max_rounds: Maximum number of repair rounds

        Returns:
            Tuple of (issues_resolved, total_revisions, sections_modified)
        """
        issues_resolved = 0
        total_revisions = 0
        sections_modified = set()

        for round_num in range(1, max_rounds + 1):
            self.logger.info(f"    Round {round_num}/{max_rounds}")

            # Get issues to fix this round (prioritize P0)
            open_issues = self._get_issues_for_round(pass_id, round_num)

            if not open_issues:
                self.logger.info(
                    f"    No more issues for Pass {pass_id}, Round {round_num}"
                )
                break

            # Fix each issue
            for issue in open_issues:
                applied, resolved = self._fix_single_issue(issue, pass_id, round_num)

                if applied:
                    total_revisions += 1
                    if resolved:
                        issues_resolved += 1
                    if issue.get("affected_sections"):
                        sections_modified.add(issue["affected_sections"][0])

        return issues_resolved, total_revisions, sections_modified

    def _get_issues_for_round(
        self, pass_id: int, round_num: int, max_issues: int = 3
    ) -> List[Dict[str, Any]]:
        """Get issues to fix in this round.

        Args:
            pass_id: Current pass number
            round_num: Current round number
            max_issues: Maximum issues to return

        Returns:
            List of issue dictionaries
        """
        # Try P0 issues first
        issues = self.issue_tracker.get_open_issues(
            iteration=self.iteration_num, pass_id=pass_id, priority_filter=["P0"]
        )[:max_issues]

        # If no P0, try P1
        if not issues:
            issues = self.issue_tracker.get_open_issues(
                iteration=self.iteration_num, pass_id=pass_id, priority_filter=["P1"]
            )[: max_issues - 1]

        # For pass 5, also include P2
        if not issues and pass_id == 5:
            issues = self.issue_tracker.get_open_issues(
                iteration=self.iteration_num, pass_id=pass_id, priority_filter=["P2"]
            )[: max_issues - 2]

        return [issue.to_dict() for issue in issues]

    def _fix_single_issue(
        self, issue: Dict[str, Any], pass_id: int, round_num: int
    ) -> Tuple[bool, bool]:
        """Fix a single issue.

        Args:
            issue: Issue dictionary
            pass_id: Current pass number
            round_num: Current round number

        Returns:
            Tuple of (applied, resolved)
        """
        # Extract section to fix
        if not issue.get("affected_sections"):
            self.logger.warning(f"Issue {issue['id']} has no affected_sections")
            return False, False

        section_id = issue["affected_sections"][0]

        # Get section versions
        versions = self.version_manager.get_section_three_versions(
            section_id, self.iteration_num, pass_id
        )

        current_content = versions.get("current")
        if not current_content:
            self.logger.warning(f"No current content for section {section_id}")
            return False, False

        # Compute residual diff
        residual_diff = self.version_manager.compute_residual_diff(
            section_id, self.iteration_num, pass_id
        )

        # Generate patch using editor
        context = {
            "pass_id": pass_id,
            "iteration": self.iteration_num,
            "section_versions": versions,
            "residual_diff": residual_diff,
        }

        try:
            self.logger.info(
                f"    Calling editor for issue {issue['id']} (section {section_id})"
            )
            patch = self.editor.generate_patch(
                issue, current_content, section_id, context
            )
        except Exception as e:
            self.logger.error(f"Failed to generate patch for {issue['id']}: {e}")
            return False, False

        if not patch:
            self.logger.warning(f"No patch generated for issue {issue['id']}")
            return False, False

        # Apply patch to content
        new_content, apply_success = self._apply_patch(current_content, patch)

        if not apply_success:
            self.logger.warning(f"Failed to apply patch for issue {issue['id']}")
            return False, False

        # Save the new version
        self.version_manager.save_section_version(
            section_id=section_id,
            content=new_content,
            iteration=self.iteration_num,
            pass_id=pass_id,
            is_final=False,  # Working version, will be finalized at pass end
        )

        diff_summary = self._build_diff_summary(current_content, new_content)
        status, feedback = self.reviewer.verify_fix(issue, diff_summary, new_content)
        resolved = status == "resolved"

        # Record the revision
        tokens_changed = abs(len(new_content.split()) - len(current_content.split()))
        revision_record = RevisionRecord(
            revision_id=f"iter{self.iteration_num}_pass{pass_id}_r{round_num}_{issue['id']}",
            iteration=self.iteration_num,
            pass_id=pass_id,
            round_num=round_num,
            issue_id=issue["id"],
            issue_title=issue.get("title", ""),
            issue_priority=issue.get("priority", "P1"),
            issue_details=issue.get("details", ""),
            section_id=section_id,
            rationale=patch.get("rationale", "") if isinstance(patch, dict) else "",
            patch=json.dumps(patch) if isinstance(patch, dict) else str(patch),
            verification_status=status,
            verification_message=feedback
            or f"Applied in iter{self.iteration_num}/pass{pass_id}/round{round_num}",
            timestamp=datetime.now().isoformat(),
            tokens_changed=tokens_changed,
        )
        self.revision_recorder.record_revision(revision_record)

        # Update issue status based on verification
        if resolved:
            self.issue_tracker.update_status(
                issue["id"],
                "resolved",
                feedback
                or f"Verified in iter{self.iteration_num}/pass{pass_id}/round{round_num}",
                resolved_in_iteration=self.iteration_num,
                resolved_in_pass=pass_id,
            )
        else:
            self.issue_tracker.update_status(
                issue["id"],
                "open",
                feedback
                or f"Not resolved in iter{self.iteration_num}/pass{pass_id}/round{round_num}",
            )
        self.issue_tracker.save()

        self.logger.info(
            f"    Issue {issue['id']} verification status: {status} (section {section_id})"
        )
        return True, resolved

    def _build_diff_summary(self, before: str, after: str, max_lines: int = 120) -> str:
        """Build a compact unified diff summary for reviewer verification."""
        import difflib

        diff_lines = difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
        )
        summary = "\n".join(list(diff_lines)[:max_lines])
        return summary or "(no changes detected)"

    def _apply_patch(self, content: str, patch: Dict[str, Any]) -> Tuple[str, bool]:
        """Apply a patch to content.

        Args:
            content: Original content
            patch: Patch dictionary with 'operations' list

        Returns:
            Tuple of (new_content, success)
        """
        operations = patch.get("operations", [])
        if not operations:
            self.logger.warning("Patch has no operations")
            return content, False

        new_content = content
        all_success = True

        for op in operations:
            op_type = op.get("op", "replace")
            search_str = op.get("search", "")
            replace_str = op.get("replace", "")

            if op_type == "replace":
                if not search_str:
                    self.logger.warning("Replace operation missing 'search' string")
                    all_success = False
                    continue

                if search_str in new_content:
                    new_content = new_content.replace(search_str, replace_str, 1)
                    self.logger.debug(
                        f"Applied replace: '{search_str[:50]}...' -> '{replace_str[:50]}...'"
                    )
                else:
                    # Try fuzzy matching - sometimes whitespace differs
                    search_normalized = " ".join(search_str.split())
                    content_normalized = " ".join(new_content.split())

                    if search_normalized in content_normalized:
                        # Find the actual position and extract the real string
                        self.logger.warning(
                            f"Exact match failed, but normalized match found for: '{search_str[:50]}...'"
                        )
                        # Try line-by-line matching
                        matched = self._fuzzy_replace(
                            new_content, search_str, replace_str
                        )
                        if matched:
                            new_content = matched
                        else:
                            all_success = False
                    else:
                        self.logger.warning(
                            f"Search string not found: '{search_str[:100]}...'"
                        )
                        all_success = False

            elif op_type == "insert":
                # Insert after a marker
                after_str = op.get("after", "")
                insert_str = op.get("insert", replace_str)

                if after_str and after_str in new_content:
                    pos = new_content.find(after_str) + len(after_str)
                    new_content = new_content[:pos] + insert_str + new_content[pos:]
                else:
                    self.logger.warning(
                        f"Insert marker not found: '{after_str[:50]}...'"
                    )
                    all_success = False

            elif op_type == "delete":
                if search_str and search_str in new_content:
                    new_content = new_content.replace(search_str, "", 1)
                else:
                    self.logger.warning(
                        f"Delete string not found: '{search_str[:50]}...'"
                    )
                    all_success = False

        # Return success if at least one operation succeeded
        content_changed = new_content != content
        return new_content, content_changed

    def _fuzzy_replace(
        self, content: str, search_str: str, replace_str: str
    ) -> Optional[str]:
        """Attempt fuzzy matching for replacement.

        Handles cases where whitespace or line breaks differ slightly.

        Args:
            content: Original content
            search_str: String to search for
            replace_str: Replacement string

        Returns:
            Modified content if match found, None otherwise
        """
        import difflib

        # Split into lines for comparison
        search_lines = search_str.strip().split("\n")
        content_lines = content.split("\n")

        if not search_lines:
            return None

        # Find best matching sequence
        matcher = difflib.SequenceMatcher(None, content_lines, search_lines)
        blocks = matcher.get_matching_blocks()

        # Look for a good match (at least 80% of search lines match)
        for block in blocks:
            if block.size >= len(search_lines) * 0.8:
                # Found a good match, replace those lines
                start_idx = block.a
                end_idx = block.a + len(search_lines)

                new_lines = (
                    content_lines[:start_idx]
                    + replace_str.split("\n")
                    + content_lines[end_idx:]
                )
                return "\n".join(new_lines)

        return None

    def _save_pass_checkpoint(self, pass_id: int) -> Path:
        """Save a checkpoint of the complete paper after this pass.

        Args:
            pass_id: Pass number that just completed

        Returns:
            Path to the saved checkpoint
        """
        checkpoint_path = self.pass_checkpoints_dir / f"pass{pass_id}_complete.tex"

        # Get all sections at this pass
        sections = self.version_manager.get_iteration_snapshot(
            self.iteration_num, pass_id
        )

        # Merge into complete paper
        self.version_manager.merge_sections_to_paper(sections, checkpoint_path)

        self.logger.info(f"  Saved Pass {pass_id} checkpoint: {checkpoint_path}")

        return checkpoint_path
