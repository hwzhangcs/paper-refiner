# Paper Refiner

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](tests/test_report.py)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

**Paper Refiner** is an intelligent, multi-agent system for automated academic paper revision. It leverages a dual-agent architecture combining Yuketang AI (Reviewer) and OpenAI (Editor) to iteratively refine LaTeX papers from structure to syntax.

---

## 🚀 Key Features

### 🤖 Multi-Agent Collaboration
- **Reviewer Agent (Yuketang)**: Acts as the critic.
    - **Review Mode**: Performs initial comprehensive grading and scoring.
    - **Assistant Mode**: Validates specific changes and ensures criteria are met.
- **Editor Agent (OpenAI)**: Acts as the writer, generating precise JSON patches to fix identified issues.
- **Orchestrator**: Manages the workflow, compilation, and version control.

### 🔄 The Two-Step Refinement Flow

Paper Refiner uses a distinct two-step process to maximize quality:

#### 1. Iteration 0: Review Mode (The "Grader")
- **Purpose**: High-level structural analysis and scoring.
- **Mechanism**: Uploads the full PDF to the "AI Paper Grading" system.
- **Output**: A comprehensive list of issues (P0-Critical to P2-Nice-to-have) and a baseline score.
- *Note: This step is upload-only and does not involve conversational prompting.*

#### 2. Iterations 1-N: Assistant Mode (The "Refiner")
- **Purpose**: Interactive, section-by-section refinement.
- **Mechanism**: Uses the "AI Teaching Assistant" for granular feedback.
- **Workflow**: Runs **5 Passes** per iteration:
    1.  **Structure**: Section organization and flow.
    2.  **Coherence**: Logic and argumentation.
    3.  **Paragraphs**: Clarity and topic sentences.
    4.  **Sentences**: Grammar and syntax.
    5.  **Polish**: Academic tone and formatting.

### 📝 Transparent Audit Trail
- **JSON Patching**: All changes are applied via structured patches, making them fully reversible.
- **Reflection Reports**: Automatically generates detailed reports explaining *why* changes were made.
- **Compilation Checks**: Ensures every change results in a compilable LaTeX document.

---

## 🛠️ Installation & Setup

Please refer to **[SETUP.md](SETUP.md)** for detailed installation and configuration instructions.

**Quick Summary:**
1.  Clone the repo: `git clone https://github.com/hwzhangcs/paper-refiner.git`
2.  Install dependencies: `uv sync`
3.  Set up OpenAI API key in `.env` file
4.  Configure Yuketang credentials using our helper tool:
    ```bash
    # Get Review Mode URL from "AI 论文批改" page and run:
    uv run python tools/extract_session_params.py "YOUR_URL_HERE" review

    # Get Assistant Mode URL from "AI 助教" page and run:
    uv run python tools/extract_session_params.py "YOUR_URL_HERE" assistant
    ```

---

## 📖 Usage

### Command Line (Recommended)

The easiest way to use Paper Refiner is through the command line:

```bash
# Using default configuration (requires config/session_params.json)
uv run python run_refiner.py --paper path/to/paper.tex --iterations 3

# Using specific configuration (e.g., review or assistant mode)
uv run python run_refiner.py --config review --paper path/to/paper.tex --iterations 3
```

### Programmatic Usage

For more control, you can use the Python API directly:

```python
from paper_refiner import PaperRefinerOrchestrator
from paper_api.config import load_cookies, load_session_params

# Load credentials
cookies = load_cookies("config/cookies.json")
params = load_session_params("config/session_params_assistant.json")

# Initialize the system
orchestrator = PaperRefinerOrchestrator(
    paper_path="./paper.tex",
    work_dir="./run_workspace",
    ykt_cookies=cookies,
    ykt_params=params,
    openai_key="your-openai-api-key",
    openai_model="gpt-4o",
    max_iterations=3
)

# Start the refinement process
orchestrator.start()
```

### Output Structure

The system creates a `run_workspace` directory containing:

- **`versions/`**: Full history of the paper at each iteration.
- **`FINAL_REVISION_REPORT.md`**: Summary of all changes.
- **`issues.json`**: Tracker of all identified and resolved issues.

---

## 📁 Project Structure

- **`config/`**: Configuration files and templates.
- **`paper_refiner/`**: Core source code.
    - **`agents/`**: AI agent implementations (Reviewer, Editor, Scorer).
    - **`core/`**: Logic for patching, issue tracking, and versioning.
    - **`prompts/`**: Prompt templates for different passes.
- **`tools/`**: Helper scripts for credential extraction and reporting.
- **`tests/`**: Test suite for core functionality.

---

## ⚠️ Important Notes

- **PDF Requirement**: Iteration 0 requires a compilable PDF. Ensure your local LaTeX environment is set up correctly.
- **Credentials**: Your Yuketang cookies are sensitive. **Never commit `config/*.json` files to version control.** We have configured `.gitignore` to prevent this, but please be careful.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
