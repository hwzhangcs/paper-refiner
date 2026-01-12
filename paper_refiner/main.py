import os
import sys
import argparse
import logging
from pathlib import Path

from paper_refiner.orchestrator import PaperRefinerOrchestrator
from paper_refiner.utils.config_loader import (
    load_environment,
    load_app_config,
    get_openai_config,
    ensure_paper_exists,
)


def main():
    parser = argparse.ArgumentParser(
        description="Paper Refiner - Automated Paper Revision System"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Configuration name (e.g. 'review', 'assistant'). Defaults to 'session_params.json'.",
    )
    parser.add_argument(
        "--paper",
        type=str,
        default="run_workspace/main.tex",
        help="Path to input paper",
    )
    parser.add_argument("--iterations", type=int, default=3, help="Max iterations")
    args = parser.parse_args()

    load_environment()

    PAPER_PATH = os.path.abspath(args.paper)

    ensure_paper_exists(PAPER_PATH)

    try:
        cookies, params, conv_id, _, _ = load_app_config(args.config)
    except Exception:
        sys.exit(1)

    openai_key, openai_base_url, openai_model = get_openai_config()

    print(f"🚀 Launching Refiner...")
    print(f"   Paper: {PAPER_PATH}")
    print(f"   Mode:  {'Default' if not args.config else args.config}")

    try:
        orchestrator = PaperRefinerOrchestrator(
            paper_path=PAPER_PATH,
            work_dir="run_workspace",
            ykt_cookies=cookies,
            ykt_params=params,
            ykt_conversation_id=conv_id,
            openai_key=openai_key,
            openai_base_url=openai_base_url,
            openai_model=openai_model,
            max_iterations=args.iterations,
        )
    except Exception as e:
        print(f"❌ Error initializing orchestrator: {e}")
        sys.exit(1)

    try:
        orchestrator.start()
        print("\n✅ Refinement process completed successfully!")
        print(f"   Check output in: run_workspace/versions/")
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logging.exception("Fatal error during refinement")
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
