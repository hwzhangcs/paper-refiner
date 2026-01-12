import os
import sys
import json
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from paper_refiner.orchestrator import PaperRefinerOrchestrator
from paper_api.config import load_cookies, load_session_params, load_conversation_id

def main():
    parser = argparse.ArgumentParser(description="Paper Refiner - Automated Paper Revision System")
    parser.add_argument("--config", type=str, default=None, help="Configuration name (e.g. 'review', 'assistant'). Defaults to 'session_params.json'.")
    parser.add_argument("--paper", type=str, default="run_workspace/main.tex", help="Path to input paper")
    parser.add_argument("--iterations", type=int, default=3, help="Max iterations")
    args = parser.parse_args()

    # User Configuration
    PAPER_PATH = os.path.abspath(args.paper)
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    COOKIES_FILE = "config/cookies.json"

    # Config Filenames
    if args.config:
        PARAMS_FILE = f"config/session_params_{args.config}.json"
        CONV_FILE = f"config/conversation_config_{args.config}.json"
        print(f"🔧 Using configuration: '{args.config}'")
    else:
        PARAMS_FILE = "config/session_params.json"
        CONV_FILE = "config/conversation_config.json"
        print("🔧 Using default configuration")

    # Verify essential files
    if not os.path.exists(COOKIES_FILE):
        print(f"❌ Error: {COOKIES_FILE} not found. Please run 'uv run python tools/extract_session_params.py' first.")
        return

    if not os.path.exists(PARAMS_FILE):
        print(f"❌ Error: {PARAMS_FILE} not found.")
        print(f"   Run 'uv run python tools/extract_session_params.py <URL> {args.config if args.config else ''}' to generate it.")
        return

    if not os.path.exists(PAPER_PATH):
        # Create dummy for testing if not exists
        print(f"⚠️  Warning: {PAPER_PATH} not found. Creating a dummy file for testing.")
        os.makedirs(os.path.dirname(PAPER_PATH), exist_ok=True)
        with open(PAPER_PATH, 'w') as f:
            f.write(r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Rectified Flow is a generative model.
It has some connection to ODEs.
\end{document}
            """)

    # Load configuration
    try:
        cookies = load_cookies(COOKIES_FILE)
        params = load_session_params(PARAMS_FILE)
        # Conversation ID is optional (will auto-create if missing)
        try:
            conv_id = load_conversation_id(CONV_FILE)
        except FileNotFoundError:
            conv_id = None
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return

    print(f"🚀 Launching Refiner...")
    print(f"   Paper: {PAPER_PATH}")
    print(f"   Mode:  {'Default' if not args.config else args.config}")

    if not OPENAI_API_KEY:
        print("⚠️  Warning: OPENAI_API_KEY not found in environment variables.")

    orchestrator = PaperRefinerOrchestrator(
        paper_path=PAPER_PATH,
        work_dir="run_workspace",
        ykt_cookies=cookies,
        ykt_params=params,
        ykt_conversation_id=conv_id,
        openai_key=OPENAI_API_KEY,
        openai_base_url=OPENAI_BASE_URL,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        max_iterations=args.iterations
    )

    try:
        orchestrator.start()
        print("\n✅ Refinement process completed successfully!")
        print(f"   Check output in: run_workspace/versions/")
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user.")
    except Exception as e:
        logging.exception("Fatal error during refinement")
        print(f"\n❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
