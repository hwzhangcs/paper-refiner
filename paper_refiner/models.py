"""
Data models for multi-iteration paper refiner architecture.

This module defines the core data structures used throughout the system:
- PassConfig: Configuration for each of the 5 passes
- PassResult: Results from a single pass execution
- IterationSummary: Summary of a complete iteration
- RevisionRecord: Complete record of a single revision
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class PassConfig:
    """Configuration for a single pass in the 5-pass framework.

    Attributes:
        id: Pass number (1-5)
        name: Human-readable pass name (e.g., "Document Structure")
        focus: Brief description of what this pass focuses on
        reviewer_prompt: Prompt template for reviewer agent
        issue_types: List of issue type identifiers this pass handles
        max_rounds: Maximum repair rounds within this pass
        priority_threshold: Minimum priority level for issues (P0, P1, P2)
    """

    id: int
    name: str
    focus: str
    reviewer_prompt: str
    issue_types: List[str]
    max_rounds: int
    priority_threshold: str

    def __post_init__(self):
        """Validate pass configuration."""
        if self.id not in range(1, 6):
            raise ValueError(f"Pass id must be 1-5, got {self.id}")
        if self.priority_threshold not in ["P0", "P1", "P2"]:
            raise ValueError(f"Invalid priority threshold: {self.priority_threshold}")


@dataclass
class PassResult:
    """Results from executing a single pass.

    Attributes:
        pass_id: The pass number (1-5)
        pass_name: Human-readable pass name
        issues_resolved: Number of issues successfully resolved
        total_revisions: Total number of revisions made
        sections_modified: List of section IDs that were modified
        output_paper_path: Path to the output paper after this pass
        duration_seconds: Time taken to complete this pass
        issues_created: Number of new issues discovered during this pass
    """

    pass_id: int
    pass_name: str
    issues_resolved: int
    total_revisions: int
    sections_modified: List[str]
    output_paper_path: str
    duration_seconds: float = 0.0
    issues_created: int = 0


@dataclass
class IterationSummary:
    """Summary of a complete iteration (5 passes).

    Attributes:
        iteration_num: The iteration number (0 = initial, 1+ = refinement)
        issues_resolved: Total issues resolved across all passes
        total_revisions: Total revisions made across all passes
        sections_modified: Number of unique sections modified
        tokens_changed: Number of tokens changed from previous iteration
        total_tokens: Total tokens in the paper
        new_issues_p0: Number of new P0 issues discovered
        new_issues_p1: Number of new P1 issues discovered
        new_issues_p2: Number of new P2 issues discovered
        pass_results: List of results from each pass
        timestamp: ISO format timestamp of iteration completion
        converged: Whether convergence was detected
        convergence_reason: Reason for convergence (if converged)
    """

    iteration_num: int
    issues_resolved: int
    total_revisions: int
    sections_modified: int
    tokens_changed: int
    total_tokens: int
    new_issues_p0: int
    new_issues_p1: int
    new_issues_p2: int
    pass_results: List[PassResult]
    timestamp: str
    converged: bool = False
    convergence_reason: Optional[str] = None

    @property
    def token_change_ratio(self) -> float:
        """Calculate the ratio of tokens changed."""
        if self.total_tokens == 0:
            return 0.0
        return self.tokens_changed / self.total_tokens


@dataclass
class RevisionRecord:
    """Complete record of a single revision operation.

    This is used for generating detailed revision reports for journal submissions.

    Attributes:
        revision_id: Unique identifier for this revision
        iteration: Iteration number when this revision occurred
        pass_id: Pass number when this revision occurred
        round_num: Round number within the pass
        issue_id: ID of the issue being addressed
        issue_title: Brief title of the issue
        issue_priority: Priority level (P0, P1, P2)
        issue_details: Full description of the issue
        section_id: Section being modified
        rationale: Explanation of why this change was made
        patch: The actual patch/diff applied
        verification_status: Status after verification (success, failed, partial)
        verification_message: Detailed verification result
        timestamp: ISO format timestamp of the revision
        tokens_changed: Number of tokens changed by this revision
    """

    revision_id: str
    iteration: int
    pass_id: int
    round_num: int
    issue_id: str
    issue_title: str
    issue_priority: str
    issue_details: str
    section_id: str
    rationale: str
    patch: str
    verification_status: str
    verification_message: str
    timestamp: str
    tokens_changed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "revision_id": self.revision_id,
            "iteration": self.iteration,
            "pass_id": self.pass_id,
            "round_num": self.round_num,
            "issue_id": self.issue_id,
            "issue_title": self.issue_title,
            "issue_priority": self.issue_priority,
            "issue_details": self.issue_details,
            "section_id": self.section_id,
            "rationale": self.rationale,
            "patch": self.patch,
            "verification_status": self.verification_status,
            "verification_message": self.verification_message,
            "timestamp": self.timestamp,
            "tokens_changed": self.tokens_changed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RevisionRecord":
        """Create RevisionRecord from dictionary."""
        return cls(**data)


@dataclass
class SectionVersion:
    """Represents a version of a paper section at a specific point in time.

    Attributes:
        section_id: Normalized section identifier (e.g., "introduction")
        content: The LaTeX content of this section
        iteration: Iteration number
        pass_id: Pass number (0 = original, 1-5 = pass versions)
        is_final: Whether this is the final version for this pass/iteration
        token_count: Number of tokens in this section
        timestamp: When this version was created
    """

    section_id: str
    content: str
    iteration: int
    pass_id: int
    is_final: bool = False
    token_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConvergenceMetrics:
    """Metrics used for convergence detection.

    Attributes:
        token_change_ratio: Ratio of tokens changed in this iteration
        new_p0_issues: Number of new P0 issues
        new_p1_issues: Number of new P1 issues
        sections_modified: Number of sections modified
        consecutive_low_change_count: Number of consecutive iterations with low change
    """

    token_change_ratio: float
    new_p0_issues: int
    new_p1_issues: int
    sections_modified: int
    consecutive_low_change_count: int = 0


# Pass type constants for easy reference
PASS_NAMES = {
    1: "Document Structure",
    2: "Section Coherence",
    3: "Paragraph Quality",
    4: "Sentence Refinement",
    5: "Final Polish",
}

PASS_FOCUS = {
    1: "Overall organization, thesis, taxonomy, scope",
    2: "Inter-section transitions, argument flow, balance",
    3: "Topic sentences, evidence synthesis, paragraph coherence",
    4: "Clarity, style, grammar, sentence structure",
    5: "Citations, typos, formatting, final polish",
}

# Priority levels
PRIORITY_LEVELS = ["P0", "P1", "P2"]

# Issue status
ISSUE_STATUS = {
    "open": "open",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "wont_fix": "wont_fix",
}

# Consolidated Pass Definitions
PASS_DEFINITIONS: Dict[int, PassConfig] = {
    1: PassConfig(
        id=1,
        name="Document Structure",
        focus="Overall organization, thesis, taxonomy, scope",
        reviewer_prompt="Focus on high-level structure, section organization, and thesis clarity.",
        issue_types=["section_org", "taxonomy", "scope", "thesis", "organization"],
        max_rounds=3,
        priority_threshold="P0",
    ),
    2: PassConfig(
        id=2,
        name="Section Coherence",
        focus="Inter-section transitions, argument flow, balance",
        reviewer_prompt="Focus on transitions between sections and logical flow.",
        issue_types=[
            "transition",
            "coherence",
            "flow",
            "balance",
            "argument_development",
        ],
        max_rounds=3,
        priority_threshold="P1",
    ),
    3: PassConfig(
        id=3,
        name="Paragraph Quality",
        focus="Topic sentences, evidence synthesis, paragraph coherence",
        reviewer_prompt="Focus on paragraph structure, topic sentences, and evidence.",
        issue_types=["paragraph_structure", "topic_sentence", "evidence", "synthesis"],
        max_rounds=3,
        priority_threshold="P1",
    ),
    4: PassConfig(
        id=4,
        name="Sentence Refinement",
        focus="Clarity, style, grammar, sentence structure",
        reviewer_prompt="Focus on sentence clarity, grammar, and academic style.",
        issue_types=["clarity", "style", "grammar", "sentence_structure"],
        max_rounds=3,
        priority_threshold="P2",
    ),
    5: PassConfig(
        id=5,
        name="Final Polish",
        focus="Citations, typos, formatting, final polish",
        reviewer_prompt="Focus on formatting, citations, and minor errors.",
        issue_types=["citation", "typo", "formatting", "polish"],
        max_rounds=2,
        priority_threshold="P2",
    ),
}


def get_pass_config(pass_id: int) -> PassConfig:
    """Get configuration for a specific pass."""
    if pass_id not in PASS_DEFINITIONS:
        raise ValueError(f"Invalid pass_id: {pass_id}")
    return PASS_DEFINITIONS[pass_id]


def get_pass_for_issue_type(issue_type: str) -> Optional[int]:
    """Determine which pass an issue type belongs to."""
    for pass_id, config in PASS_DEFINITIONS.items():
        if issue_type in config.issue_types:
            return pass_id
    return None


@dataclass
class Issue:
    """Represents a single issue identified by the reviewer."""

    id: str
    priority: str
    title: str
    details: str
    acceptance_criteria: str
    status: str = "open"
    type: str = "unknown"
    affected_sections: List[str] = field(
        default_factory=list
    )  # Sections affected by this issue
    iteration: int = 0
    pass_id: int = 0
    resolved_in_iteration: Optional[int] = None
    resolved_in_pass: Optional[int] = None
    history: List[str] = field(default_factory=list)

    # ===== 反思报告字段 (对齐 report.md 模板) =====
    rubric_dimension: Optional[str] = None  # "A3", "B2", "B3", "C1" 等
    ai_suggestion_summary: Optional[str] = None  # AI建议要点（一句话）
    human_decision: str = "accepted"  # "accepted" | "rejected" | "modified"
    rejection_reason: Optional[str] = None  # 拒绝/修改原因（用于B2）
    evidence_before: Optional[str] = None  # 修改前文本片段（100-150字）
    evidence_after: Optional[str] = None  # 修改后文本片段（100-150字）
    dimension_explanation: Optional[str] = None  # 为什么带来提升（用于证据组）

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Issue":
        """Create Issue from dictionary, handling missing fields safely."""
        # Filter data to only include valid fields
        valid_fields = cls.__dataclass_fields__.keys()

        defaults = {
            "title": "Untitled Issue",
            "details": "No details provided",
            "acceptance_criteria": "None provided",
        }

        filtered_data = {k: v for k, v in data.items() if k in valid_fields}

        for field_name, default_value in defaults.items():
            if field_name not in filtered_data:
                filtered_data[field_name] = default_value

        return cls(**filtered_data)
