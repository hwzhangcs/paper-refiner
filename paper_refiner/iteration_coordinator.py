"""
Iteration Coordinator for multi-iteration paper refinement.

This is the top-level coordinator that manages:
- Multiple complete iterations (Iteration 1, 2, ..., N)
- Each iteration contains 5 complete passes
- Convergence detection across iterations
- Final report generation
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json

from paper_refiner.models import (
    IterationSummary,
    PassResult,
    ConvergenceMetrics,
    PASS_NAMES,
)
from paper_refiner.core.section_version_manager import SectionVersionManager
from paper_refiner.core.issue_tracker import IssueTracker
from paper_refiner.core.revision_recorder import RevisionRecorder
from paper_refiner.core.convergence_detector import ConvergenceDetector
from paper_refiner.core.reflection_tracer import ReflectionTracer
from paper_refiner.pass_coordinator import PassCoordinator
from paper_refiner.agents.reviewer import ReviewerAgent
from paper_refiner.agents.editor import EditorAgent
from paper_refiner.agents.scorer import ScorerAgent


class IterationCoordinator:
    """Top-level coordinator for multi-iteration paper refinement.

    Workflow:
    1. run_iteration_0(): Extract sections and initial review
    2. run_iteration(N): Execute complete 5-pass iteration
    3. check_convergence(): Determine if refinement should stop
    4. generate_final_report(): Create comprehensive revision report
    """

    def __init__(
        self,
        paper_path: Path,
        work_dir: Path,
        reviewer: ReviewerAgent,
        editor: EditorAgent,
        initial_reviewer: Optional[ReviewerAgent] = None,
        max_iterations: int = 5,
        config: Optional[Dict[str, Any]] = None,
        tpami_pdf_path: Optional[str] = None,
    ):
        """Initialize the iteration coordinator.

        Args:
            paper_path: Path to the LaTeX paper file
            work_dir: Working directory for all outputs
            reviewer: ReviewerAgent instance for Pass 1-5 (assistant mode)
            editor: EditorAgent instance
            initial_reviewer: Optional ReviewerAgent for Iteration 0 (review mode)
            max_iterations: Maximum number of iterations (default: 5)
            config: Optional configuration dictionary
            tpami_pdf_path: Optional path to TPAMI Information for Authors PDF
        """
        self.paper_path = Path(paper_path)
        self.work_dir = Path(work_dir)
        self.reviewer = reviewer
        self.initial_reviewer = initial_reviewer or reviewer  # Fallback to reviewer
        self.editor = editor
        self.max_iterations = max_iterations
        self.config = config or {}
        self.tpami_pdf_path = tpami_pdf_path

        # Create working directories
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.versions_dir = self.work_dir / "versions"
        self.versions_dir.mkdir(exist_ok=True)

        # Initialize core managers
        self.version_manager = SectionVersionManager(self.work_dir)
        self.issue_tracker = IssueTracker(str(self.work_dir / "issues.json"))
        self.revision_recorder = RevisionRecorder(self.work_dir)
        self.convergence_detector = ConvergenceDetector(
            self.config.get("convergence", {})
        )

        self.reflection_tracer = ReflectionTracer(self.work_dir)

        try:
            self.scorer = ScorerAgent()
        except Exception as e:
            self.logger.warning(f"ScorerAgent initialization failed: {e}")
            self.scorer = None

        # State tracking
        self.current_iteration = 0
        self.iteration_history: List[IterationSummary] = []

        # Logging
        self.logger = logging.getLogger(__name__)

    def start(self, max_iterations: Optional[int] = None):
        """Start the multi-iteration refinement process.

        Args:
            max_iterations: Override max iterations (default: use constructor value)
        """
        if max_iterations is not None:
            self.max_iterations = max_iterations

        self.logger.info(
            f"Starting multi-iteration refinement (max: {self.max_iterations})"
        )

        # Iteration 0: Initial setup
        if self.current_iteration == 0:
            self.run_iteration_0()

        # Loop for N iterations
        for i in range(1, self.max_iterations + 1):
            if self.current_iteration >= i:
                continue  # Skip if already done (resuming)

            summary = self.run_iteration(i)
            self.iteration_history.append(summary)

            # Check convergence
            converged, reason = self.check_convergence()
            if converged:
                self.logger.info(f"Convergence detected: {reason}")
                summary.converged = True
                summary.convergence_reason = reason
                break

        # Generate final reports
        self.generate_final_report()

    def run_iteration_0(self):
        """Run Iteration 0: Initial setup and review.

        - Extract sections
        - Save original version
        - Get initial issues from Reviewer
        """
        self.logger.info("Running Iteration 0: Initial setup and review")

        # Extract sections
        self.logger.info(f"Extracting sections from {self.paper_path}")
        sections = self.version_manager.extract_sections(self.paper_path)

        # Save original versions
        for section_id, content in sections.items():
            if section_id.startswith("_"):
                # Save special sections (preamble/postamble) to special files
                self.version_manager._save_special_section(section_id, content)
                self.logger.info(f"  Saved special: {section_id}")
            else:
                self.version_manager.save_section_original(section_id, content)
                self.logger.info(f"  Saved original: {section_id}")

        # Save iteration 0 checkpoint (complete paper)
        iter0_checkpoint = (
            self.versions_dir / "iteration_checkpoints" / "iter0_original.tex"
        )
        iter0_checkpoint.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy(self.paper_path, iter0_checkpoint)

        # Get initial issues from reviewer (use initial_reviewer for Iteration 0)
        self.logger.info("Submitting paper for initial review...")
        initial_issues = self.initial_reviewer.submit_paper_and_get_issues(str(self.paper_path))

        # Add issues with iteration=0
        self.issue_tracker.add_issues(initial_issues, iteration=0)
        self.logger.info(f"  Found {len(initial_issues)} initial issues")

        # Print issue summary (use initial_issues directly to avoid showing stale data)
        p0_count = sum(1 for issue in initial_issues if issue.get('priority') == 'P0')
        p1_count = sum(1 for issue in initial_issues if issue.get('priority') == 'P1')
        p2_count = sum(1 for issue in initial_issues if issue.get('priority') == 'P2')
        self.logger.info(
            f"  P0: {p0_count}, "
            f"P1: {p1_count}, "
            f"P2: {p2_count}"
        )

        self.current_iteration = 0
        self._save_progress()

    def run_iteration(self, iteration_num: int) -> IterationSummary:
        """Run a complete iteration (5 passes).

        Args:
            iteration_num: The iteration number (1+)

        Returns:
            IterationSummary with results from all passes
        """
        self.logger.info(f"Running Iteration {iteration_num}")
        self.current_iteration = iteration_num

        start_time = datetime.now()

        # Get the current paper path
        current_paper_path = self.get_current_paper_path()

        # Initialize Pass Coordinator
        pass_coordinator = PassCoordinator(
            work_dir=self.work_dir,
            iteration_num=iteration_num,
            version_manager=self.version_manager,
            issue_tracker=self.issue_tracker,
            revision_recorder=self.revision_recorder,
            reviewer=self.reviewer,
            editor=self.editor,
        )

        # Run 5 passes
        pass_results = []
        for pass_id in range(1, 6):
            self.logger.info(f"Starting Pass {pass_id}: {PASS_NAMES[pass_id]}")
            result = pass_coordinator.execute_pass(
                pass_id=pass_id, paper_path=current_paper_path
            )
            pass_results.append(result)
            self.logger.info(
                f"Pass {pass_id} completed: {result.issues_resolved} issues resolved"
            )

        # Save checkpoint
        self._save_iteration_checkpoint(iteration_num)
        self._save_progress()

        # Calculate metrics
        tokens_changed, total_tokens = self._calculate_token_changes(iteration_num)
        stats = self.issue_tracker.get_statistics(iteration=iteration_num)
        new_p0 = stats["new_issues_p0"]
        new_p1 = stats["new_issues_p1"]
        new_p2 = stats["new_issues_p2"]

        summary = IterationSummary(
            iteration_num=iteration_num,
            issues_resolved=sum(r.issues_resolved for r in pass_results),
            total_revisions=sum(r.total_revisions for r in pass_results),
            sections_modified=sum(len(r.sections_modified) for r in pass_results),
            tokens_changed=tokens_changed,
            total_tokens=total_tokens,
            new_issues_p0=new_p0,
            new_issues_p1=new_p1,
            new_issues_p2=new_p2,
            pass_results=pass_results,
            timestamp=datetime.now().isoformat(),
        )

        # Record iteration in revision recorder
        self.revision_recorder.record_iteration(summary)

        duration = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"Iteration {iteration_num} completed in {duration:.1f}s")

        return summary

    def _calculate_token_changes(self, iteration_num: int) -> tuple[int, int]:
        """Calculate token changes between iterations.

        Args:
            iteration_num: Current iteration number

        Returns:
            Tuple of (tokens_changed, total_tokens)
        """
        # Simple approximation: count characters (4 chars ~ 1 token)
        try:
            current_paper = self.get_current_paper_path()
            current_content = current_paper.read_text(encoding="utf-8")
            total_tokens = len(current_content) // 4

            if iteration_num == 1:
                # Compare with original
                original = (
                    self.versions_dir / "iteration_checkpoints" / "iter0_original.tex"
                )
                if original.exists():
                    orig_content = original.read_text(encoding="utf-8")
                    # Calculate simple diff
                    tokens_changed = abs(len(current_content) - len(orig_content)) // 4
                else:
                    tokens_changed = 0
            else:
                # Compare with previous iteration
                prev_checkpoint = (
                    self.versions_dir
                    / "iteration_checkpoints"
                    / f"iter{iteration_num - 1}_final.tex"
                )
                if prev_checkpoint.exists():
                    prev_content = prev_checkpoint.read_text(encoding="utf-8")
                    tokens_changed = abs(len(current_content) - len(prev_content)) // 4
                else:
                    tokens_changed = 0

            return tokens_changed, total_tokens
        except Exception as e:
            self.logger.warning(f"Error calculating token changes: {e}")
            return 0, 0

    def _save_iteration_checkpoint(self, iteration_num: int):
        """Save a complete paper checkpoint for this iteration.

        Args:
            iteration_num: Current iteration number
        """
        checkpoint_dir = self.versions_dir / "iteration_checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint_path = checkpoint_dir / f"iter{iteration_num}_final.tex"

        # Merge all sections into complete paper
        sections = self.version_manager.get_iteration_snapshot(iteration_num, pass_id=5)
        self.version_manager.merge_sections_to_paper(sections, checkpoint_path)

        self.logger.info(
            f"Saved iteration {iteration_num} checkpoint: {checkpoint_path}"
        )

    def _save_progress(self):
        """Save current iteration state to disk."""
        state_path = self.work_dir / "state.json"
        state = {
            "current_iteration": self.current_iteration,
            "timestamp": datetime.now().isoformat(),
        }
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def check_convergence(self) -> tuple[bool, str]:
        """Check if the refinement has converged.

        Returns:
            Tuple of (converged: bool, reason: str)
        """
        return self.convergence_detector.check_convergence(self.iteration_history)

    def generate_final_report(self):
        """Generate comprehensive final reports.

        Creates:
        1. ITERATION_COMPARISON.md - Iteration comparison
        2. PASS_REVISION_DETAILS.md - Detailed pass-level changes
        3. FINAL_REVISION_REPORT.md - Overall summary
        """
        self.logger.info("Generating final reports...")

        # Generate iteration comparison report
        comparison_report = self.revision_recorder.generate_iteration_comparison_report(
            self.iteration_history
        )
        self.logger.info(f"Generated: {comparison_report}")

        # Generate detailed pass revision report
        details_report = self.revision_recorder.generate_revision_report()
        self.logger.info(f"Generated: {details_report}")

        # Generate final summary report
        report_path = self.work_dir / "FINAL_REVISION_REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Multi-Iteration Revision Report\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Overall statistics
            total_issues = sum(s.issues_resolved for s in self.iteration_history)
            total_revisions = sum(s.total_revisions for s in self.iteration_history)
            total_iterations = len(self.iteration_history)

            f.write("## Summary Statistics\n\n")
            f.write(f"- **Total Iterations**: {total_iterations}\n")
            f.write(f"- **Total Issues Resolved**: {total_issues}\n")
            f.write(f"- **Total Revisions Made**: {total_revisions}\n")

            if self.iteration_history and self.iteration_history[-1].converged:
                f.write(f"- **Status**: ✅ Converged\n")
                f.write(
                    f"- **Convergence Reason**: {self.iteration_history[-1].convergence_reason}\n"
                )
            else:
                f.write(f"- **Status**: 🔄 Completed (max iterations reached)\n")

            f.write("\n## Iteration Summary\n\n")
            f.write(
                "| Iteration | Issues Resolved | Revisions | Token Change | Status |\n"
            )
            f.write(
                "|-----------|----------------|-----------|--------------|--------|\n"
            )

            for summary in self.iteration_history:
                status = "✅ Converged" if summary.converged else "🔄 Complete"
                f.write(
                    f"| {summary.iteration_num} | "
                    f"{summary.issues_resolved} | "
                    f"{summary.total_revisions} | "
                    f"{summary.token_change_ratio:.2%} | "
                    f"{status} |\n"
                )

            f.write("\\n## Related Reports\\n\\n")
            f.write(f"- [Iteration Comparison](./{comparison_report.name})\\n")
            f.write(f"- [Pass Revision Details](./{details_report.name})\\n")

        self.logger.info(f"Report saved to: {report_path}")

        if self.scorer:
            self.logger.info("\\n" + "=" * 60)
            self.logger.info("Using Review mode to score reflection report...")
            self.logger.info("=" * 60)

            reflection_report_path = self.work_dir / "reflection_report.md"

            if reflection_report_path.exists():
                try:
                    score_result = self.scorer.score_reflection_report(
                        str(reflection_report_path), reset_conversation=True
                    )

                    if self.reflection_tracer:
                        self.reflection_tracer.log_scoring_from_review(
                            iteration=self.current_iteration,
                            pass_id=0,
                            report_path=str(reflection_report_path),
                            scores={
                                "A": score_result.get("A", 0),
                                "B": score_result.get("B", 0),
                                "C": score_result.get("C", 0),
                                "D": score_result.get("D", 0),
                                "E": score_result.get("E", 0),
                            },
                            total_score=score_result.get("total", 0),
                            feedback=score_result.get("feedback", ""),
                        )

                    self.logger.info(f"\\nScoring results:")
                    self.logger.info(f"  A: {score_result.get('A', 0)}/15")
                    self.logger.info(f"  B: {score_result.get('B', 0)}/25")
                    self.logger.info(f"  C: {score_result.get('C', 0)}/25")
                    self.logger.info(f"  D: {score_result.get('D', 0)}/20")
                    self.logger.info(f"  E: {score_result.get('E', 0)}/15")
                    self.logger.info(f"  Total: {score_result.get('total', 0)}/100")

                    score_json_path = self.work_dir / "final_scores.json"
                    import json

                    with open(score_json_path, "w", encoding="utf-8") as f:
                        json.dump(score_result, f, indent=2, ensure_ascii=False)

                    self.logger.info(f"\\n✅ Scores saved to: {score_json_path}")

                except Exception as e:
                    self.logger.error(f"Scoring failed: {e}")
            else:
                self.logger.warning(
                    f"Reflection report not found: {reflection_report_path}"
                )

    def get_current_paper_path(self) -> Path:
        """Get the path to the current version of the paper.

        Returns:
            Path to the latest paper version
        """
        if self.current_iteration == 0:
            return self.paper_path

        # Return the latest iteration checkpoint
        checkpoint_dir = self.versions_dir / "iteration_checkpoints"
        latest = checkpoint_dir / f"iter{self.current_iteration}_final.tex"

        if latest.exists():
            return latest

        return self.paper_path
