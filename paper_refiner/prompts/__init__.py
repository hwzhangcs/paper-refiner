"""
Prompts package for Paper Refiner.

Contains pass-specific review prompts for the 5-Pass framework.
"""

from paper_refiner.prompts.pass_prompts import (
    STRUCTURE_PROMPT,
    COHERENCE_PROMPT,
    PARAGRAPH_PROMPT,
    SENTENCE_PROMPT,
    POLISH_PROMPT,
    PASS_PROMPTS,
    get_pass_prompt,
    get_all_prompts
)

__all__ = [
    'STRUCTURE_PROMPT',
    'COHERENCE_PROMPT',
    'PARAGRAPH_PROMPT',
    'SENTENCE_PROMPT',
    'POLISH_PROMPT',
    'PASS_PROMPTS',
    'get_pass_prompt',
    'get_all_prompts'
]
