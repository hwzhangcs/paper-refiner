"""
Revision Recorder for generating detailed revision reports.

This module:
- Records every revision operation
- Generates pass-level revision reports
- Generates iteration-level comparison reports
- Creates TPAMI-style revision letters
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict
import json

from paper_refiner.models import (
    RevisionRecord, IterationSummary, PassResult,
    PASS_NAMES, PASS_FOCUS
)


class RevisionRecorder:
    """Records and reports on all revisions made during refinement.

    Creates two types of reports:
    1. Pass-level details: What changed in each pass
    2. Iteration-level comparison: Progress across iterations
    """

    def __init__(self, work_dir: Path):
        """Initialize the revision recorder.

        Args:
            work_dir: Root working directory
        """
        self.work_dir = Path(work_dir)
        self.records_dir = self.work_dir / "revision_records"
        self.records_dir.mkdir(parents=True, exist_ok=True)

        # In-memory record storage
        self.records: List[RevisionRecord] = []

        # Load existing records if any
        self._load_records()

    def _load_records(self):
        """Load existing revision records from disk."""
        # Records are organized as: iteration/pass/round_issueID.json
        for iter_dir in self.records_dir.glob("iter*"):
            for pass_dir in iter_dir.glob("pass*"):
                for record_file in pass_dir.glob("*.json"):
                    try:
                        with open(record_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            record = RevisionRecord.from_dict(data)
                            self.records.append(record)
                    except Exception as e:
                        print(f"Warning: Failed to load {record_file}: {e}")

    def record_revision(self, record: RevisionRecord):
        """Record a single revision operation.

        Args:
            record: RevisionRecord to save
        """
        self.records.append(record)

        # Save to disk
        iter_dir = self.records_dir / f"iter{record.iteration}" / f"pass{record.pass_id}"
        iter_dir.mkdir(parents=True, exist_ok=True)

        # Filename: round{N}_{issueID}.json
        filename = f"round{record.round_num}_{record.issue_id}.json"
        file_path = iter_dir / filename

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)

    def generate_revision_report(
        self,
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate detailed pass-level revision report.

        Creates a TPAMI-style revision letter documenting all changes.

        Args:
            output_path: Where to save report (default: work_dir/PASS_REVISION_DETAILS.md)

        Returns:
            Path to the generated report
        """
        if output_path is None:
            output_path = self.work_dir / "PASS_REVISION_DETAILS.md"

        report = []
        report.append("# Detailed Revision Report\n\n")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        report.append("This document details all revisions made during the paper refinement process.\n\n")

        # Organize by iteration, then by pass
        iterations = {}
        for record in self.records:
            if record.iteration not in iterations:
                iterations[record.iteration] = {}
            if record.pass_id not in iterations[record.iteration]:
                iterations[record.iteration][record.pass_id] = []
            iterations[record.iteration][record.pass_id].append(record)

        success_statuses = {"success", "resolved"}

        # Generate report for each iteration
        for iteration in sorted(iterations.keys()):
            report.append(f"## Iteration {iteration}\n\n")

            passes = iterations[iteration]

            for pass_id in sorted(passes.keys()):
                pass_name = PASS_NAMES.get(pass_id, f"Pass {pass_id}")
                pass_focus = PASS_FOCUS.get(pass_id, "")

                report.append(f"### Pass {pass_id}: {pass_name}\n\n")
                if pass_focus:
                    report.append(f"**Focus**: {pass_focus}\n\n")

                # Group by issue
                issues = {}
                for record in passes[pass_id]:
                    if record.issue_id not in issues:
                        issues[record.issue_id] = []
                    issues[record.issue_id].append(record)

                # Report each issue
                for issue_id in sorted(issues.keys()):
                    records = issues[issue_id]
                    first = records[0]

                    report.append(f"#### Issue {issue_id}: {first.issue_title}\n\n")
                    report.append(f"**Priority**: {first.issue_priority}  \n")
                    report.append(f"**Section**: {first.section_id}  \n")
                    report.append(f"**Description**: {first.issue_details}\n\n")

                    # Show all attempts
                    if len(records) > 1:
                        report.append(f"**Resolution** (took {len(records)} attempts):\n\n")
                    else:
                        report.append("**Resolution**:\n\n")

                    for i, record in enumerate(records, 1):
                        report.append(f"**Attempt {i}** (Round {record.round_num}):\n")
                        report.append(f"- Rationale: {record.rationale}\n")
                        report.append(f"- Status: {record.verification_status}\n")

                        if record.verification_status not in success_statuses:
                            report.append(f"- Message: {record.verification_message}\n")

                        if record.tokens_changed > 0:
                            report.append(f"- Tokens changed: {record.tokens_changed}\n")

                        report.append("\n")

                        # Show patch if successful
                        if record.verification_status in success_statuses and record.patch:
                            report.append("```diff\n")
                            # Truncate long patches
                            patch_lines = record.patch.split('\n')[:30]
                            report.append('\n'.join(patch_lines))
                            if len(record.patch.split('\n')) > 30:
                                report.append("\n... (truncated)\n")
                            report.append("```\n\n")

                report.append("\n")

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report)

        return output_path

    def generate_iteration_comparison_report(
        self,
        iteration_history: List[IterationSummary],
        output_path: Optional[Path] = None
    ) -> Path:
        """Generate iteration-level comparison report.

        Shows progress across iterations with summary tables.

        Args:
            iteration_history: List of IterationSummary objects
            output_path: Where to save (default: work_dir/ITERATION_COMPARISON.md)

        Returns:
            Path to the generated report
        """
        if output_path is None:
            output_path = self.work_dir / "ITERATION_COMPARISON.md"

        report = []
        report.append("# Multi-Iteration Comparison Report\n\n")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Overall summary table
        report.append("## Overall Summary\n\n")
        report.append("| Iteration | Issues Resolved | Revisions | Sections Modified | "
                     "Tokens Changed | Change % | New P0 | New P1 | Status |\n")
        report.append("|-----------|-----------------|-----------|-------------------|"
                     "----------------|----------|--------|--------|--------|\n")

        for summary in iteration_history:
            change_pct = summary.token_change_ratio * 100
            status = "✅ Converged" if summary.converged else "🔄 Complete"

            report.append(
                f"| {summary.iteration_num} | "
                f"{summary.issues_resolved} | "
                f"{summary.total_revisions} | "
                f"{summary.sections_modified} | "
                f"{summary.tokens_changed:,} | "
                f"{change_pct:.1f}% | "
                f"{summary.new_issues_p0} | "
                f"{summary.new_issues_p1} | "
                f"{status} |\n"
            )

        report.append("\n")

        # Convergence analysis
        if iteration_history:
            last = iteration_history[-1]
            report.append("## Convergence Analysis\n\n")

            if last.converged:
                report.append(f"✅ **Converged**: {last.convergence_reason}\n\n")
            else:
                report.append("🔄 **Not yet converged**\n\n")

            # Trend analysis
            if len(iteration_history) >= 2:
                report.append("### Change Trend\n\n")
                report.append("| Iteration | Token Change % |\n")
                report.append("|-----------|----------------|\n")
                for summary in iteration_history:
                    report.append(f"| {summary.iteration_num} | "
                                f"{summary.token_change_ratio * 100:.2f}% |\n")
                report.append("\n")

        # Detailed iteration breakdown
        report.append("## Detailed Iteration Breakdown\n\n")

        for summary in iteration_history:
            report.append(f"### Iteration {summary.iteration_num}\n\n")
            report.append(f"**Timestamp**: {summary.timestamp}  \n")
            report.append(f"**Total Revisions**: {summary.total_revisions}  \n")
            report.append(f"**Issues Resolved**: {summary.issues_resolved}  \n")
            report.append(f"**Tokens Changed**: {summary.tokens_changed:,} / "
                        f"{summary.total_tokens:,} ({summary.token_change_ratio:.2%})  \n")
            report.append(f"**New Issues**: P0={summary.new_issues_p0}, "
                        f"P1={summary.new_issues_p1}, P2={summary.new_issues_p2}  \n\n")

            # Pass breakdown
            if summary.pass_results:
                report.append("#### Pass Results\n\n")
                report.append("| Pass | Name | Issues Resolved | Revisions | Sections |\n")
                report.append("|------|------|-----------------|-----------|----------|\n")

                for pass_result in summary.pass_results:
                    sections_str = ', '.join(pass_result.sections_modified[:5])
                    if len(pass_result.sections_modified) > 5:
                        sections_str += ", ..."

                    report.append(
                        f"| {pass_result.pass_id} | "
                        f"{pass_result.pass_name} | "
                        f"{pass_result.issues_resolved} | "
                        f"{pass_result.total_revisions} | "
                        f"{sections_str} |\n"
                    )

                report.append("\n")

            report.append("\n")

        # Statistics summary
        if iteration_history:
            report.append("## Overall Statistics\n\n")

            total_revisions = sum(s.total_revisions for s in iteration_history)
            total_issues = sum(s.issues_resolved for s in iteration_history)
            total_iterations = len(iteration_history)

            report.append(f"- **Total Iterations**: {total_iterations}\n")
            report.append(f"- **Total Issues Resolved**: {total_issues}\n")
            report.append(f"- **Total Revisions**: {total_revisions}\n")

            if total_iterations > 0:
                avg_revisions = total_revisions / total_iterations
                report.append(f"- **Average Revisions per Iteration**: {avg_revisions:.1f}\n")

            report.append("\n")

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(report)

        return output_path

    def record_iteration(self, summary: IterationSummary):
        """Record an iteration summary.

        Args:
            summary: IterationSummary object for this iteration
        """
        # Save iteration summary to disk
        iter_file = self.records_dir / f"iter{summary.iteration_num}_summary.json"

        summary_data = {
            'iteration_num': summary.iteration_num,
            'issues_resolved': summary.issues_resolved,
            'total_revisions': summary.total_revisions,
            'sections_modified': summary.sections_modified,
            'tokens_changed': summary.tokens_changed,
            'total_tokens': summary.total_tokens,
            'token_change_ratio': summary.token_change_ratio,
            'new_issues_p0': summary.new_issues_p0,
            'new_issues_p1': summary.new_issues_p1,
            'new_issues_p2': summary.new_issues_p2,
            'converged': summary.converged,
            'convergence_reason': summary.convergence_reason,
            'timestamp': summary.timestamp,
            'pass_count': len(summary.pass_results)
        }

        with open(iter_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

    def get_revisions(
        self,
        iteration: Optional[int] = None,
        pass_id: Optional[int] = None
    ) -> List[RevisionRecord]:
        """Get revision records with optional filtering.

        Args:
            iteration: Filter by iteration (None for all)
            pass_id: Filter by pass (None for all)

        Returns:
            List of RevisionRecord objects
        """
        filtered = self.records

        if iteration is not None:
            filtered = [r for r in filtered if r.iteration == iteration]

        if pass_id is not None:
            filtered = [r for r in filtered if r.pass_id == pass_id]

        return filtered

    def get_statistics(
        self,
        iteration: Optional[int] = None,
        pass_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get statistics about revisions.

        Args:
            iteration: Filter by iteration (None for all)
            pass_id: Filter by pass (None for all)

        Returns:
            Dictionary with revision statistics
        """
        filtered = self.records

        if iteration is not None:
            filtered = [r for r in filtered if r.iteration == iteration]

        if pass_id is not None:
            filtered = [r for r in filtered if r.pass_id == pass_id]

        success_statuses = {"success", "resolved"}
        failed_statuses = {"failed", "open"}

        stats = {
            'total_revisions': len(filtered),
            'successful': len([r for r in filtered if r.verification_status in success_statuses]),
            'failed': len([r for r in filtered if r.verification_status in failed_statuses]),
            'total_tokens_changed': sum(r.tokens_changed for r in filtered),
            'by_priority': {
                'P0': len([r for r in filtered if r.issue_priority == 'P0']),
                'P1': len([r for r in filtered if r.issue_priority == 'P1']),
                'P2': len([r for r in filtered if r.issue_priority == 'P2'])
            },
            'sections_modified': len(set(r.section_id for r in filtered))
        }

        return stats
