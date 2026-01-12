# Setup Guide

This guide will help you set up the Paper Refiner system.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- Yuketang (雨课堂) Account
- OpenAI API Key

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd paper_refiner
    ```

2.  **Install dependencies:**
    ```bash
    uv sync
    ```

3.  **Set up environment variables:**
    Create a `.env` file in the root directory:
    ```bash
    OPENAI_API_KEY=your_openai_api_key
    # Optional: Custom base URL
    # OPENAI_BASE_URL=https://api.openai.com/v1
    ```

## Configuration

The system requires credentials for Yuketang to function. You need to configure two separate sessions: one for initial review ("Review Mode") and one for interactive refinement ("Assistant Mode").

### Step 1: Get Review Mode Credentials (Iteration 0)

1.  Log in to Yuketang web interface.
2.  Navigate to the **"AI Paper Grading" (AI 论文批改)** section.
3.  Copy the URL of the page (it should look like `.../pro/lms/...`).
4.  Run the extraction tool:
    ```bash
    uv run python tools/extract_session_params.py "YOUR_REVIEW_PAGE_URL" review
    ```
    *Follow the interactive prompts to log in if required.*

### Step 2: Get Assistant Mode Credentials (Pass 1-5)

1.  Navigate to the **"AI Teaching Assistant" (AI 助教)** section in Yuketang.
2.  Copy the URL of the page.
3.  Run the extraction tool:
    ```bash
    uv run python tools/extract_session_params.py "YOUR_ASSISTANT_PAGE_URL" assistant
    ```

### Step 3: Verify Configuration

Check that the following files exist in the `config/` directory:
- `cookies.json`
- `session_params_review.json`
- `session_params_assistant.json`

## Troubleshooting

### "ReviewerAgent error: No response from initial prompt"
This is normal for Iteration 0 (Review Mode). The system expects an upload-only interaction. If you see this error in Pass 1-5, check your `session_params_assistant.json`.

### "403 Forbidden" or Auth Errors
Your cookies or session IDs may have expired. Re-run the `extract_session_params.py` tool to refresh your credentials.

### PDF Upload Fails
Ensure your paper compiles correctly to PDF locally before running the system. The review mode requires a valid PDF file.

## Next Steps

Once setup is complete, proceed to the [Usage Guide](README.md#usage) to start refining your paper.
