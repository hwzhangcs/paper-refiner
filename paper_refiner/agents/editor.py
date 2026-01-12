import json
import logging
from typing import Dict, Any, Optional, List, Union
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_fixed
from paper_refiner.models import PASS_DEFINITIONS, Issue

class EditorAgent:
    """
    Wraps OpenAI API to act as the Editor.
    Generates JSON patches to fix issues.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.logger = logging.getLogger(__name__)

        self.SYSTEM_PROMPT = """
        You are an expert LaTeX Editor for Computer Science papers (Generative Models).
        Your task is to fix specific issues in a TeX file based on a Reviewer's feedback.

        RULES:
        1. Output ONLY a valid JSON Patch.
        2. Do NOT change parts of the text unrelated to the issue.
        3. Do NOT hallucinate citations.
        4. NEVER output markdown code blocks (```json). Output raw JSON.
        5. The `search` string in the patch must be EXACTLY what is in the original text (copy-paste), otherwise replacement fails.
        6. If the text to search spans multiple lines, ensure newlines and indentation match exactly.

        JSON PATCH FORMAT:
        {
          "issue_id": "ID_FROM_INPUT",
          "target_file": "filename.tex",
          "operations": [
            {
              "op": "replace",
              "search": "exact string to find",
              "replace": "new string"
            }
          ],
          "rationale": "Explanation of changes..."
        }
        """

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def generate_patch(self, issue: Union[Dict[str, Any], Issue], file_content: str, filename: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Generate a JSON patch for a specific issue.

        Args:
            issue: Issue object or dictionary
            file_content: Content of the file to modify
            filename: Name of the file
            context: Optional context (pass_id, iteration, etc.)

        Returns:
            JSON Patch dictionary or None if failed
        """
        try:
            # Normalize issue to dictionary
            if isinstance(issue, Issue):
                issue_data = issue.to_dict()
            else:
                issue_data = issue

            prompt_context = self._build_context_string(context or {})
            
            user_prompt = f"""
            CONTEXT:
            {prompt_context}

            ISSUE TO FIX:
            ID: {issue_data['id']}
            Title: {issue_data['title']}
            Description: {issue_data.get('description', issue_data.get('details', ''))}
            Acceptance Criteria: {issue_data.get('acceptance_criteria', '')}

            TARGET FILE: {filename}
            CONTENT:
            ```latex
            {file_content}
            ```

            Generate a JSON Patch to fix this issue strictly following the acceptance criteria.
            """

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            content = response.choices[0].message.content
            if not content:
                return None

            patch = json.loads(content)

            # Basic validation
            if "operations" not in patch:
                self.logger.error("Invalid patch format: missing operations")
                return None

            return patch

        except Exception as e:
            self.logger.error(f"Error generating patch: {e}")
            return None

    def _build_context_string(self, context: Dict[str, Any]) -> str:
        """Build a context string for the prompt based on iteration/pass info.

        Args:
            context: Dictionary with pass_id, iteration, section_versions, residual_diff

        Returns:
            Formatted context string for the prompt
        """
        lines = []

        if 'iteration' in context:
            lines.append(f"Current Iteration: {context['iteration']}")

        if 'pass_id' in context:
            pass_config = PASS_DEFINITIONS.get(context['pass_id'])
            if pass_config:
                lines.append(f"Current Pass: {pass_config.id} ({pass_config.name})")
                lines.append(f"Focus: {pass_config.focus}")
            else:
                lines.append(f"Current Pass: {context['pass_id']}")

        # Include residual diff if available
        if context.get('residual_diff'):
            lines.append("")
            lines.append("RESIDUAL DIFF (changes since previous pass):")
            lines.append("```diff")
            lines.append(context['residual_diff'][:2000])  # Limit size
            lines.append("```")

        # Include version info summary
        if context.get('section_versions'):
            versions = context['section_versions']
            lines.append("")
            lines.append("VERSION INFO:")
            if versions.get('original'):
                lines.append(f"- Original version available ({len(versions['original'])} chars)")
            if versions.get('previous'):
                lines.append(f"- Previous pass version available ({len(versions['previous'])} chars)")
            if versions.get('current'):
                lines.append(f"- Current version: {len(versions['current'])} chars")

        return "\n".join(lines)
