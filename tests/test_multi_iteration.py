"""
Unit tests for multi-iteration architecture components.

Tests:
- SectionVersionManager: section extraction, versioning, diff computation
- IssueTracker extensions: iteration/pass tracking, filtering, classification
- Data models: validation and serialization
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import json

from paper_refiner.core.section_version_manager import SectionVersionManager
from paper_refiner.core.issue_tracker import IssueTracker, ISSUE_TYPE_TO_PASS
from paper_refiner.models import (
    PassConfig, PassResult, IterationSummary, RevisionRecord,
    ConvergenceMetrics, PASS_NAMES
)


class TestSectionVersionManager(unittest.TestCase):
    """Test section extraction and version management."""

    def setUp(self):
        """Create temporary work directory."""
        self.work_dir = Path(tempfile.mkdtemp())
        self.manager = SectionVersionManager(self.work_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        if self.work_dir.exists():
            shutil.rmtree(self.work_dir)

    def test_section_extraction_simple(self):
        """Test extracting sections from a simple LaTeX paper."""
        # Create a sample LaTeX paper
        paper_content = r"""
\documentclass{article}
\begin{document}

\section{Introduction}
This is the introduction text.
Some more content here.

\section{Related Work}
This is related work.
\subsection{Deep Learning}
Details about deep learning.

\section{Methodology}
Our approach is novel.

\bibliography{references}
\end{document}
"""
        paper_path = self.work_dir / "test_paper.tex"
        with open(paper_path, 'w', encoding='utf-8') as f:
            f.write(paper_content)

        # Extract sections
        sections = self.manager.extract_sections(paper_path)

        # Verify sections were extracted
        self.assertIn('introduction', sections)
        self.assertIn('related_work', sections)
        self.assertIn('methodology', sections)
        self.assertIn('_preamble', sections)
        self.assertIn('_postamble', sections)

        # Verify content
        self.assertIn('This is the introduction text', sections['introduction'])
        self.assertIn('Details about deep learning', sections['related_work'])
        self.assertIn('\\documentclass{article}', sections['_preamble'])

    def test_section_id_normalization(self):
        """Test section ID normalization."""
        test_cases = [
            ("Introduction", "introduction"),
            ("Related Work", "related_work"),
            ("Deep Learning: A Survey", "deep_learning_a_survey"),
            ("Approach (Novel)", "approach_novel")
        ]

        for title, expected_id in test_cases:
            normalized = self.manager._normalize_section_id(title)
            self.assertEqual(normalized, expected_id)

    def test_save_and_retrieve_section_original(self):
        """Test saving and retrieving original section."""
        section_content = "\\section{Introduction}\nThis is content."

        # Save original
        saved_path = self.manager.save_section_original("introduction", section_content)
        self.assertTrue(saved_path.exists())

        # Retrieve
        retrieved = self.manager.get_section_content("introduction", iteration=0, pass_id=0)
        self.assertEqual(retrieved, section_content)

        # Verify metadata
        metadata_path = saved_path.parent / "original_metadata.json"
        self.assertTrue(metadata_path.exists())
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        self.assertEqual(metadata['section_id'], 'introduction')
        self.assertEqual(metadata['iteration'], 0)

    def test_save_and_retrieve_section_versions(self):
        """Test saving and retrieving section versions across iterations/passes."""
        # Save original
        self.manager.save_section_original("introduction", "Original content")

        # Save iteration 1, pass 1
        self.manager.save_section_version(
            "introduction", "Pass 1 content", iteration=1, pass_id=1, is_final=True
        )

        # Save iteration 1, pass 2 working
        self.manager.save_section_version(
            "introduction", "Pass 2 working", iteration=1, pass_id=2, is_final=False
        )

        # Retrieve versions
        original = self.manager.get_section_content("introduction", 0, 0)
        pass1 = self.manager.get_section_content("introduction", 1, 1, is_final=True)
        pass2_working = self.manager.get_section_content("introduction", 1, 2, is_final=False)

        self.assertEqual(original, "Original content")
        self.assertEqual(pass1, "Pass 1 content")
        self.assertEqual(pass2_working, "Pass 2 working")

    def test_get_three_versions(self):
        """Test retrieving three versions for residual diff."""
        # Setup versions
        self.manager.save_section_original("intro", "Version 0")
        self.manager.save_section_version("intro", "Version iter1 pass1", 1, 1, True)
        self.manager.save_section_version("intro", "Version iter1 pass2", 1, 2, True)
        self.manager.save_section_version("intro", "Version iter1 pass3 working", 1, 3, False)

        # Get three versions for iteration 1, pass 3
        versions = self.manager.get_section_three_versions("intro", 1, 3)

        self.assertEqual(versions['original'], "Version 0")
        self.assertEqual(versions['previous'], "Version iter1 pass2")  # Previous pass
        self.assertEqual(versions['current'], "Version iter1 pass3 working")

    def test_compute_residual_diff(self):
        """Test residual diff computation."""
        # Setup versions
        self.manager.save_section_original("intro", "Line 1\nLine 2\nLine 3\n")
        self.manager.save_section_version("intro", "Line 1\nLine 2 modified\nLine 3\n", 1, 1, True)
        self.manager.save_section_version("intro", "Line 1\nLine 2 modified\nLine 3 changed\n", 1, 2, False)

        # Compute diff from pass 1 to pass 2
        diff = self.manager.compute_residual_diff("intro", 1, 2)

        # Verify diff shows the change
        self.assertIn("Line 3", diff)
        self.assertIn("Line 3 changed", diff)
        self.assertIn("-", diff)  # Should have deletions
        self.assertIn("+", diff)  # Should have additions

    def test_merge_sections_to_paper(self):
        """Test merging sections back into a complete paper."""
        sections = {
            '_preamble': '\\documentclass{article}\n\\begin{document}\n',
            'introduction': '\\section{Introduction}\nIntro text.\n',
            'methodology': '\\section{Methodology}\nMethod text.\n',
            '_postamble': '\\end{document}\n'
        }

        output_path = self.work_dir / "merged.tex"
        result_path = self.manager.merge_sections_to_paper(sections, output_path)

        self.assertTrue(result_path.exists())

        with open(result_path, 'r') as f:
            content = f.read()

        self.assertIn('\\documentclass{article}', content)
        self.assertIn('\\section{Introduction}', content)
        self.assertIn('\\section{Methodology}', content)
        self.assertIn('\\end{document}', content)

    def test_list_sections(self):
        """Test listing all extracted sections."""
        self.manager.save_section_original("intro", "content")
        self.manager.save_section_original("methods", "content")
        self.manager.save_section_original("results", "content")

        sections = self.manager.list_sections()

        self.assertEqual(len(sections), 3)
        self.assertIn('intro', sections)
        self.assertIn('methods', sections)
        self.assertIn('results', sections)


class TestIssueTrackerExtensions(unittest.TestCase):
    """Test IssueTracker extensions for multi-iteration support."""

    def setUp(self):
        """Create temporary issue tracker."""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        self.temp_file.close()
        self.tracker = IssueTracker(self.temp_file.name)

    def tearDown(self):
        """Clean up temporary file."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_add_issues_with_iteration_and_pass(self):
        """Test adding issues with iteration/pass tracking."""
        issues = [
            {'id': 'I1', 'priority': 'P0', 'type': 'thesis', 'details': 'Fix thesis'},
            {'id': 'I2', 'priority': 'P1', 'type': 'grammar', 'details': 'Grammar issue'}
        ]

        self.tracker.add_issues(issues, iteration=1, pass_id=None)

        # Verify issues were added with correct metadata
        issue1 = self.tracker.get_issue('I1')
        self.assertEqual(issue1['iteration'], 1)
        self.assertEqual(issue1['pass_id'], 1)  # Auto-classified from 'thesis'
        self.assertEqual(issue1['status'], 'open')
        self.assertIsNone(issue1['resolved_in_iteration'])

        issue2 = self.tracker.get_issue('I2')
        self.assertEqual(issue2['pass_id'], 4)  # Auto-classified from 'grammar'

    def test_classify_issue_by_pass(self):
        """Test automatic issue classification."""
        test_cases = [
            ({'type': 'thesis', 'details': 'Unclear thesis'}, 1),
            ({'type': 'transition', 'details': 'Bad transition'}, 2),
            ({'type': 'paragraph_structure', 'details': 'Poor paragraphs'}, 3),
            ({'type': 'grammar', 'details': 'Grammar errors'}, 4),
            ({'type': 'citation', 'details': 'Missing citations'}, 5),
            ({'type': 'unknown', 'details': 'Some issue'}, 0),  # Cannot classify
        ]

        for issue, expected_pass in test_cases:
            pass_id = self.tracker.classify_issue_by_pass(issue)
            self.assertEqual(pass_id, expected_pass,
                           f"Issue {issue} should be classified as pass {expected_pass}")

    def test_get_open_issues_with_filters(self):
        """Test filtering open issues by iteration, pass, and priority."""
        issues = [
            {'id': 'I1', 'priority': 'P0', 'type': 'thesis'},
            {'id': 'I2', 'priority': 'P1', 'type': 'grammar'},
            {'id': 'I3', 'priority': 'P0', 'type': 'citation'},
        ]

        self.tracker.add_issues(issues[:2], iteration=1)
        self.tracker.add_issues([issues[2]], iteration=2)

        # Filter by iteration
        iter1_issues = self.tracker.get_open_issues(iteration=1)
        self.assertEqual(len(iter1_issues), 2)

        # Filter by pass
        pass1_issues = self.tracker.get_open_issues(pass_id=1)
        self.assertEqual(len(pass1_issues), 1)
        self.assertEqual(pass1_issues[0]['id'], 'I1')

        # Filter by priority
        p0_issues = self.tracker.get_open_issues(priority_filter=['P0'])
        self.assertEqual(len(p0_issues), 2)

        # Combined filter
        iter1_p0 = self.tracker.get_open_issues(iteration=1, priority_filter=['P0'])
        self.assertEqual(len(iter1_p0), 1)
        self.assertEqual(iter1_p0[0]['id'], 'I1')

        # Test limit
        limited = self.tracker.get_open_issues(limit=2)
        self.assertEqual(len(limited), 2)

    def test_update_status_with_resolution_tracking(self):
        """Test updating issue status with resolution metadata."""
        issues = [{'id': 'I1', 'priority': 'P0', 'type': 'thesis'}]
        self.tracker.add_issues(issues, iteration=1)

        # Resolve the issue
        self.tracker.update_status('I1', 'resolved',
                                  history_entry='Fixed in pass 2',
                                  resolved_in_iteration=1,
                                  resolved_in_pass=2)

        issue = self.tracker.get_issue('I1')
        self.assertEqual(issue['status'], 'resolved')
        self.assertEqual(issue['resolved_in_iteration'], 1)
        self.assertEqual(issue['resolved_in_pass'], 2)
        self.assertIn('Fixed in pass 2', issue['history'])

    def test_get_statistics(self):
        """Test issue statistics computation."""
        issues = [
            {'id': 'I1', 'priority': 'P0', 'type': 'thesis'},
            {'id': 'I2', 'priority': 'P1', 'type': 'grammar'},
            {'id': 'I3', 'priority': 'P0', 'type': 'citation'},
        ]

        self.tracker.add_issues(issues[:2], iteration=1)
        self.tracker.add_issues([issues[2]], iteration=2)

        # Mark one as resolved
        self.tracker.update_status('I1', 'resolved')

        # Get statistics for iteration 1
        stats = self.tracker.get_statistics(iteration=1)

        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['open'], 1)  # I2 still open
        self.assertEqual(stats['resolved'], 1)  # I1 resolved
        self.assertEqual(stats['by_priority']['P0'], 1)
        self.assertEqual(stats['by_priority']['P1'], 1)
        self.assertEqual(stats['new_issues_p0'], 1)
        self.assertEqual(stats['new_issues_p1'], 1)


class TestDataModels(unittest.TestCase):
    """Test data model classes."""

    def test_pass_config_validation(self):
        """Test PassConfig validation."""
        # Valid config
        config = PassConfig(
            id=1,
            name="Document Structure",
            focus="Organization",
            reviewer_prompt="Check structure",
            issue_types=['thesis', 'scope'],
            max_rounds=3,
            priority_threshold="P0"
        )
        self.assertEqual(config.id, 1)

        # Invalid pass id
        with self.assertRaises(ValueError):
            PassConfig(id=6, name="Invalid", focus="", reviewer_prompt="",
                      issue_types=[], max_rounds=1, priority_threshold="P0")

        # Invalid priority
        with self.assertRaises(ValueError):
            PassConfig(id=1, name="Test", focus="", reviewer_prompt="",
                      issue_types=[], max_rounds=1, priority_threshold="P3")

    def test_iteration_summary_properties(self):
        """Test IterationSummary computed properties."""
        summary = IterationSummary(
            iteration_num=1,
            issues_resolved=5,
            total_revisions=10,
            sections_modified=3,
            tokens_changed=1000,
            total_tokens=20000,
            new_issues_p0=0,
            new_issues_p1=2,
            new_issues_p2=5,
            pass_results=[],
            timestamp="2024-01-01T00:00:00"
        )

        # Test token change ratio
        self.assertAlmostEqual(summary.token_change_ratio, 0.05)

    def test_convergence_metrics(self):
        """Test convergence detection."""
        thresholds = {
            'token_change_ratio': 0.05,
            'new_p0_issues': 0,
            'sections_modified': 2,
            'consecutive_low_change': 2
        }

        # Converged - low token change
        metrics1 = ConvergenceMetrics(
            token_change_ratio=0.03,
            new_p0_issues=0,
            new_p1_issues=1,
            sections_modified=3
        )
        self.assertTrue(metrics1.is_converged(thresholds))

        # Converged - no new P0 issues
        metrics2 = ConvergenceMetrics(
            token_change_ratio=0.08,
            new_p0_issues=0,
            new_p1_issues=1,
            sections_modified=5
        )
        self.assertTrue(metrics2.is_converged(thresholds))

        # Not converged
        metrics3 = ConvergenceMetrics(
            token_change_ratio=0.15,
            new_p0_issues=3,
            new_p1_issues=5,
            sections_modified=6
        )
        self.assertFalse(metrics3.is_converged(thresholds))

    def test_revision_record_serialization(self):
        """Test RevisionRecord to/from dict."""
        record = RevisionRecord(
            revision_id="R1",
            iteration=1,
            pass_id=2,
            round_num=1,
            issue_id="I1",
            issue_title="Fix grammar",
            issue_priority="P1",
            issue_details="Grammar error in section 2",
            section_id="introduction",
            rationale="Improved clarity",
            patch="diff content",
            verification_status="success",
            verification_message="Verified",
            timestamp="2024-01-01T00:00:00",
            tokens_changed=50
        )

        # To dict
        record_dict = record.to_dict()
        self.assertEqual(record_dict['revision_id'], 'R1')
        self.assertEqual(record_dict['pass_id'], 2)

        # From dict
        restored = RevisionRecord.from_dict(record_dict)
        self.assertEqual(restored.revision_id, record.revision_id)
        self.assertEqual(restored.tokens_changed, record.tokens_changed)


if __name__ == '__main__':
    unittest.main()
