# Configuration Guide

This directory contains configuration files for the Paper Refiner system. To run the system, you need to set up several JSON files with your credentials.

## Required Files

1.  **`cookies.json`**: Authentication cookies for the Yuketang platform.
2.  **`session_params.json`** (or `session_params_assistant.json`): Parameters for the "Assistant Mode" (AI TA) session.
3.  **`session_params_review.json`**: Parameters for the "Review Mode" (AI Paper Grading) session.
4.  **`conversation_config.json`** (optional): Stores active conversation IDs.

## Setup Instructions

### 1. Cookies (`cookies.json`)

Copy the template:
```bash
cp config/cookies.json.template config/cookies.json
```

You need to fill in the values from your browser after logging into Yuketang.
- `csrftoken`
- `sessionid`

### 2. Session Parameters

The system uses two different Yuketang AI modes:

#### A. Review Mode (Iteration 0)
Used for the initial paper upload and grading. This corresponds to the **"AI Paper Grading" (AI 论文批改)** feature.

Create `config/session_params_review.json` from the template:
```bash
cp config/session_params.json.template config/session_params_review.json
```
Use `tools/extract_session_params.py` with the URL from the "AI Paper Grading" page to populate this.

#### B. Assistant Mode (Pass 1-5)
Used for interactive refinement and rewriting. This corresponds to the **"AI Teaching Assistant" (AI 助教)** feature.

Create `config/session_params_assistant.json` from the template:
```bash
cp config/session_params.json.template config/session_params_assistant.json
```
Use `tools/extract_session_params.py` with the URL from the "AI Teaching Assistant" page to populate this.

## Automated Extraction Tool

We provide a helper tool to automatically extract these parameters. See [SETUP.md](../SETUP.md) for detailed usage instructions.
