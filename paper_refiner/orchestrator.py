"""
Paper Refiner Orchestrator - Main entry point for multi-iteration refinement.

This orchestrator now uses the new multi-iteration architecture:
- IterationCoordinator manages multiple complete iterations
- PassCoordinator manages 5 passes within each iteration
- Each pass follows: Document Structure -> Section Coherence -> Paragraph Quality -> Sentence Refinement -> Final Polish
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from paper_refiner.iteration_coordinator import IterationCoordinator
from paper_refiner.agents.reviewer import ReviewerAgent
from paper_refiner.agents.editor import EditorAgent


class PaperRefinerOrchestrator:
    """Main orchestrator for the Paper Refiner 2.0 multi-iteration system.

    Usage:
        orchestrator = PaperRefinerOrchestrator(
            paper_path="paper.tex",
            work_dir="run_workspace",
            ykt_cookies=cookies,
            openai_key="...",
            openai_base_url="...",
            openai_model="gpt-4o"
        )
        orchestrator.start()
    """

    def __init__(
        self,
        paper_path: str,
        work_dir: str = "run_workspace",
        ykt_cookies: Dict[str, str] = None,
        ykt_params: Optional[Dict[str, str]] = None,
        ykt_conversation_id: Optional[int] = None,
        ykt_review_params: Optional[Dict[str, str]] = None,
        ykt_review_conversation_id: Optional[int] = None,
        reset_conversation_each_request: bool = True,
        openai_key: str = None,
        openai_base_url: str = None,
        openai_model: str = "gpt-3.5-turbo",
        max_iterations: int = 5,
        tpami_pdf_path: str = None
    ):
        """Initialize the orchestrator with all required components.

        Args:
            paper_path: Path to the LaTeX paper file
            work_dir: Working directory for outputs
            ykt_cookies: Yuketang session cookies for ReviewerAgent
            ykt_params: Yuketang session params for assistant mode (Pass 1-5)
            ykt_conversation_id: Optional conversation ID for assistant mode
            ykt_review_params: Yuketang session params for review mode (Iteration 0)
            ykt_review_conversation_id: Optional conversation ID for review mode
            reset_conversation_each_request: Reset conversation per request
            openai_key: OpenAI API key for EditorAgent
            openai_base_url: OpenAI base URL (for proxies/custom endpoints)
            openai_model: OpenAI model to use
            max_iterations: Maximum number of refinement iterations
            tpami_pdf_path: Path to TPAMI Information for Authors PDF (optional)
        """
        self.paper_path = Path(paper_path).absolute()
        self.work_dir = Path(work_dir).absolute()

        # Set default TPAMI PDF path if not provided
        if tpami_pdf_path is None:
            tpami_pdf_path = str(Path(__file__).parent / "resources" / "TPAMI_Information_for_Authors.pdf")

        # Create work directory
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Configure iteration settings
        config = self._load_config()

        # Load defaults from config files if not provided
        try:
            from paper_api.config import load_cookies, load_session_params, load_conversation_id
        except Exception:
            load_cookies = load_session_params = load_conversation_id = None  # type: ignore

        # Load cookies
        if ykt_cookies is None and load_cookies:
            try:
                ykt_cookies = load_cookies("config/cookies.json")
            except FileNotFoundError:
                ykt_cookies = {}

        # Load assistant mode config (for Pass 1-5)
        if ykt_params is None and load_session_params:
            try:
                ykt_params = load_session_params("config/session_params_assistant.json")
            except FileNotFoundError:
                try:
                    ykt_params = load_session_params("config/session_params.json")
                except FileNotFoundError:
                    ykt_params = None

        if ykt_conversation_id is None and load_conversation_id:
            try:
                ykt_conversation_id = load_conversation_id("config/conversation_config_assistant.json")
            except FileNotFoundError:
                try:
                    ykt_conversation_id = load_conversation_id("config/conversation_config.json")
                except FileNotFoundError:
                    ykt_conversation_id = None

        # Load review mode config (for Iteration 0)
        if ykt_review_params is None and load_session_params:
            try:
                ykt_review_params = load_session_params("config/session_params_review.json")
            except FileNotFoundError:
                ykt_review_params = None

        if ykt_review_conversation_id is None and load_conversation_id:
            try:
                ykt_review_conversation_id = load_conversation_id("config/conversation_config_review.json")
            except FileNotFoundError:
                ykt_review_conversation_id = None

        # Initialize agents
        # Initial reviewer for Iteration 0 (uses review mode config)
        self.initial_reviewer = ReviewerAgent(
            cookies=ykt_cookies or {},
            params=ykt_review_params,
            conversation_id=ykt_review_conversation_id,
            reset_conversation_each_request=reset_conversation_each_request,
        )

        # Regular reviewer for Pass 1-5 (uses assistant mode config)
        self.reviewer = ReviewerAgent(
            cookies=ykt_cookies or {},
            params=ykt_params,
            conversation_id=ykt_conversation_id,
            reset_conversation_each_request=reset_conversation_each_request,
        )

        self.editor = EditorAgent(
            api_key=openai_key,
            base_url=openai_base_url,
            model=openai_model
        )

        # Initialize the iteration coordinator
        self.coordinator = IterationCoordinator(
            paper_path=self.paper_path,
            work_dir=self.work_dir,
            reviewer=self.reviewer,
            initial_reviewer=self.initial_reviewer,
            editor=self.editor,
            max_iterations=max_iterations,
            config=config,
            tpami_pdf_path=tpami_pdf_path
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from refiner_config.yaml if it exists."""
        config_path = Path("config/refiner_config.yaml")
        if config_path.exists():
            try:
                import yaml
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                self.logger.warning(f"Failed to load config: {e}")

        # Default configuration
        return {
            'convergence': {
                'min_iterations': 2,
                'token_change_threshold': 0.05,  # 5%
                'max_iterations': 5
            }
        }

    def start(self, max_iterations: Optional[int] = None):
        """Start the multi-iteration refinement process.

        This will:
        1. Run Iteration 0: Extract sections and initial review
        2. Run Iterations 1-N: Each with 5 passes
           - Pass 1: Document Structure
           - Pass 2: Section Coherence
           - Pass 3: Paragraph Quality
           - Pass 4: Sentence Refinement
           - Pass 5: Final Polish
        3. Check for convergence
        4. Generate final revision reports

        Args:
            max_iterations: Override max iterations (default: use constructor value)
        """
        self.logger.info(f"Starting Paper Refiner 2.0")
        self.logger.info(f"Paper: {self.paper_path}")
        self.logger.info(f"Work directory: {self.work_dir}")
        self.logger.info(f"Model: {self.editor.model}")
        self.logger.info(f"")

        # Start the iteration coordinator
        self.coordinator.start(max_iterations=max_iterations)

        # Print summary
        self._print_summary()

    def _print_summary(self):
        """Print a summary of the refinement process."""
        self.logger.info("")
        self.logger.info("="*60)
        self.logger.info("REFINEMENT SUMMARY")
        self.logger.info("="*60)

        if self.coordinator.iteration_history:
            total_issues = sum(s.issues_resolved for s in self.coordinator.iteration_history)
            total_revisions = sum(s.total_revisions for s in self.coordinator.iteration_history)

            self.logger.info(f"Total iterations: {len(self.coordinator.iteration_history)}")
            self.logger.info(f"Total issues resolved: {total_issues}")
            self.logger.info(f"Total revisions: {total_revisions}")

            last = self.coordinator.iteration_history[-1]
            if last.converged:
                self.logger.info(f"Status: Converged ({last.convergence_reason})")
            else:
                self.logger.info(f"Status: Completed max iterations")

        self.logger.info("")
        self.logger.info(f"Reports available in: {self.work_dir}")
        self.logger.info("  - FINAL_REVISION_REPORT.md")
        self.logger.info("  - ITERATION_COMPARISON.md")
        self.logger.info("  - PASS_REVISION_DETAILS.md")
        self.logger.info("  - issues.json")
        self.logger.info("="*60)
