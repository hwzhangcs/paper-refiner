"""
Convergence Detector for multi-iteration refinement.

This module detects when the paper refinement has converged and should stop.
Uses multiple metrics to determine convergence:
- Token change ratio
- New critical issues
- Sections modified
- Consecutive low-change iterations
"""

from typing import List, Dict, Any, Tuple, Optional
import logging

from paper_refiner.models import IterationSummary, ConvergenceMetrics


class ConvergenceDetector:
    """Detects convergence in multi-iteration paper refinement.

    Convergence criteria (any one triggers):
    1. Token change ratio < threshold (e.g., 5%)
    2. No new P0 issues and few P1 issues
    3. Very few sections modified
    4. Consecutive iterations with low change
    """

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None):
        """Initialize convergence detector.

        Args:
            thresholds: Optional custom thresholds. Defaults:
                - token_change_ratio: 0.05 (5%)
                - new_p0_issues: 0
                - new_p1_threshold: 2
                - sections_modified: 2
                - consecutive_low_change: 2
        """
        self.logger = logging.getLogger(__name__)

        # Default thresholds
        self.thresholds = {
            'token_change_ratio': 0.05,      # < 5% change
            'new_p0_issues': 0,              # No new P0 issues
            'new_p1_threshold': 2,           # ≤ 2 new P1 issues
            'sections_modified': 2,          # ≤ 2 sections modified
            'consecutive_low_change': 2,     # 2 consecutive low-change iterations
            'min_iterations': 1              # Minimum iterations before convergence
        }

        # Override with custom thresholds
        if thresholds:
            self.thresholds.update(thresholds)

    def check_convergence(
        self,
        history: List[IterationSummary]
    ) -> Tuple[bool, str]:
        """Check if refinement has converged.

        Args:
            history: List of IterationSummary from all iterations

        Returns:
            Tuple of (is_converged: bool, reason: str)
        """
        if not history:
            return False, "No iterations completed yet"

        # Need minimum iterations
        if len(history) < self.thresholds['min_iterations']:
            return False, f"Need at least {self.thresholds['min_iterations']} iterations"

        current = history[-1]

        if current.total_revisions == 0 and current.issues_resolved == 0:
            reason = "No effective revisions or resolved issues in latest iteration"
            self.logger.warning(f"Convergence blocked: {reason}")
            return False, reason

        # Extract metrics
        metrics = ConvergenceMetrics(
            token_change_ratio=current.token_change_ratio,
            new_p0_issues=current.new_issues_p0,
            new_p1_issues=current.new_issues_p1,
            sections_modified=current.sections_modified
        )

        # Check 1: Low token change ratio
        if metrics.token_change_ratio < self.thresholds['token_change_ratio']:
            reason = (f"Low token change ratio: {metrics.token_change_ratio:.2%} "
                     f"< {self.thresholds['token_change_ratio']:.2%}")
            self.logger.info(f"✅ Convergence detected: {reason}")
            return True, reason

        # Check 2: No new critical issues
        if (metrics.new_p0_issues <= self.thresholds['new_p0_issues'] and
            metrics.new_p1_issues <= self.thresholds['new_p1_threshold']):

            # Need at least 2 iterations to confirm
            if len(history) >= 2:
                previous = history[-2]
                if (previous.new_issues_p0 <= self.thresholds['new_p0_issues'] and
                    previous.new_issues_p1 <= self.thresholds['new_p1_threshold']):

                    reason = (f"No critical issues for {len(history)} iterations "
                             f"(P0: {metrics.new_p0_issues}, P1: {metrics.new_p1_issues})")
                    self.logger.info(f"✅ Convergence detected: {reason}")
                    return True, reason

        # Check 3: Few sections modified
        if metrics.sections_modified <= self.thresholds['sections_modified']:
            # Need at least 2 iterations to confirm
            if len(history) >= 2:
                previous = history[-2]
                if previous.sections_modified <= self.thresholds['sections_modified']:
                    reason = (f"Few sections modified: {metrics.sections_modified} sections "
                             f"≤ {self.thresholds['sections_modified']}")
                    self.logger.info(f"✅ Convergence detected: {reason}")
                    return True, reason

        # Check 4: Consecutive low-change iterations
        if self._check_consecutive_low_change(history):
            reason = (f"Consecutive low-change iterations: "
                     f"{self.thresholds['consecutive_low_change']}+")
            self.logger.info(f"✅ Convergence detected: {reason}")
            return True, reason

        # Not converged
        reason = self._get_not_converged_reason(metrics, history)
        self.logger.debug(f"Not converged: {reason}")
        return False, reason

    def _check_consecutive_low_change(self, history: List[IterationSummary]) -> bool:
        """Check for consecutive iterations with low change.

        Args:
            history: List of IterationSummary

        Returns:
            True if consecutive_low_change threshold met
        """
        required_count = self.thresholds['consecutive_low_change']

        if len(history) < required_count:
            return False

        # Check the last N iterations
        recent = history[-required_count:]

        for summary in recent:
            # Consider "low change" if token ratio < 2x threshold
            if summary.token_change_ratio >= (2 * self.thresholds['token_change_ratio']):
                return False

            # Or if many sections were modified
            if summary.sections_modified > self.thresholds['sections_modified']:
                return False

        return True

    def _get_not_converged_reason(
        self,
        metrics: ConvergenceMetrics,
        history: List[IterationSummary]
    ) -> str:
        """Generate explanation for why convergence has not been reached.

        Args:
            metrics: Current convergence metrics
            history: Iteration history

        Returns:
            Human-readable reason string
        """
        reasons = []

        # Token change
        if metrics.token_change_ratio >= self.thresholds['token_change_ratio']:
            reasons.append(
                f"token change {metrics.token_change_ratio:.2%} "
                f">= {self.thresholds['token_change_ratio']:.2%}"
            )

        # New issues
        if metrics.new_p0_issues > self.thresholds['new_p0_issues']:
            reasons.append(f"{metrics.new_p0_issues} new P0 issues")

        if metrics.new_p1_issues > self.thresholds['new_p1_threshold']:
            reasons.append(f"{metrics.new_p1_issues} new P1 issues")

        # Sections modified
        if metrics.sections_modified > self.thresholds['sections_modified']:
            reasons.append(f"{metrics.sections_modified} sections modified")

        if not reasons:
            reasons.append("need more iterations for confidence")

        return "Not converged: " + ", ".join(reasons)
