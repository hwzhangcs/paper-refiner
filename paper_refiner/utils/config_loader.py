import os
import argparse
from typing import Optional, Tuple, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import logging

try:
    from paper_api.config import load_cookies, load_session_params, load_conversation_id
except ImportError:
    raise ImportError("paper_api.config module is required")

logger = logging.getLogger(__name__)


def load_environment() -> None:
    load_dotenv()


def validate_config_paths(
    cookies_file: str, params_file: str, config_name: Optional[str] = None
) -> bool:
    if not os.path.exists(cookies_file):
        logger.error(
            f"Error: {cookies_file} not found. Please run 'python tools/extract_session_params.py' first."
        )
        return False

    if not os.path.exists(params_file):
        logger.error(f"Error: {params_file} not found.")
        cmd = f"python tools/extract_session_params.py <URL> {config_name if config_name else ''}"
        logger.error(f"   Run '{cmd}' to generate it.")
        return False

    return True


def ensure_paper_exists(paper_path: str) -> None:
    if not os.path.exists(paper_path):
        logger.warning(
            f"Warning: {paper_path} not found. Creating a dummy file for testing."
        )
        os.makedirs(os.path.dirname(paper_path), exist_ok=True)
        with open(paper_path, "w") as f:
            f.write(r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Rectified Flow is a generative model.
It has some connection to ODEs.
\end{document}
            """)


def load_app_config(
    config_name: Optional[str] = None,
) -> Tuple[Dict[str, str], Dict[str, str], Optional[int], str, str]:
    cookies_file = "config/cookies.json"
    if config_name:
        params_file = f"config/session_params_{config_name}.json"
        conv_file = f"config/conversation_config_{config_name}.json"
        logger.info(f"Using configuration: '{config_name}'")
    else:
        params_file = "config/session_params.json"
        conv_file = "config/conversation_config.json"
        logger.info("Using default configuration")

    if not validate_config_paths(cookies_file, params_file, config_name):
        raise FileNotFoundError("Configuration files missing")

    try:
        cookies = load_cookies(cookies_file)
        params = load_session_params(params_file)
        try:
            conv_id = load_conversation_id(conv_file)
        except FileNotFoundError:
            conv_id = None

        return cookies, params, conv_id, params_file, cookies_file

    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise e


def get_openai_config() -> Tuple[Optional[str], str, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    if not api_key:
        logger.warning("Warning: OPENAI_API_KEY not found in environment variables.")

    return api_key, base_url, model
