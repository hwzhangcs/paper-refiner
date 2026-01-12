"""
Section Version Manager for multi-iteration paper refinement.

This module handles:
- Extracting sections from LaTeX papers
- Saving section versions at each iteration/pass checkpoint
- Retrieving three versions (original, previous, current) for residual diff
- Computing residual diffs between versions
- Merging sections back into complete papers
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import difflib
import json

from paper_refiner.models import SectionVersion


class SectionVersionManager:
    """Manages section-level versioning across iterations and passes.

    Directory structure:
        work_dir/
        ├── sections/
        │   ├── introduction/
        │   │   ├── original.tex
        │   │   ├── iter1/
        │   │   │   ├── pass1_working.tex
        │   │   │   ├── pass1_final.tex
        │   │   │   └── pass5_final.tex
        │   │   └── iter2/
        │   │       └── pass1_final.tex...
        │   └── methodology/...
    """

    def __init__(self, work_dir: Path):
        """Initialize the section version manager.

        Args:
            work_dir: Root working directory for the paper refinement project
        """
        self.work_dir = Path(work_dir)
        self.sections_dir = self.work_dir / "sections"
        self.sections_dir.mkdir(parents=True, exist_ok=True)
        # Cache for file content: path_str -> content
        self._cache: Dict[str, str] = {}

    def _read_file(self, path: Path) -> str:
        """Read file content with caching."""
        path_str = str(path.absolute())
        if path_str in self._cache:
            return self._cache[path_str]

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self._cache[path_str] = content
        return content

    def _write_file(self, path: Path, content: str) -> None:
        """Write file content and update cache."""
        path_str = str(path.absolute())
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        self._cache[path_str] = content

    def extract_sections(self, paper_path: Path) -> Dict[str, str]:
        """Extract sections from a LaTeX paper.

        Extracts top-level \\section{} blocks and their content, including
        all nested \\subsection{} and \\subsubsection{} as part of the
        parent section.

        Args:
            paper_path: Path to the LaTeX paper file

        Returns:
            Dictionary mapping section_id -> content
            Example: {'introduction': '\\section{Introduction}\\n...', ...}
        """
        # Read using cache mechanism (though likely first read)
        content = self._read_file(paper_path)

        # Extract sections with their full content
        # Pattern: \section{Title} followed by everything until next \section or end
        pattern = r"\\section\{([^}]+)\}(.*?)(?=\\section\{|\\bibliography|\\end\{document\}|\Z)"
        matches = re.findall(pattern, content, re.DOTALL)

        sections = {}
        section_order = []  # Track original document order
        for title, body in matches:
            section_id = self.normalize_section_id(title)
            section_content = f"\\section{{{title}}}\n{body}"
            sections[section_id] = section_content
            section_order.append(section_id)

        # Also extract document preamble and postamble for reconstruction
        preamble_pattern = r"^(.*?)\\section\{"
        preamble_match = re.search(preamble_pattern, content, re.DOTALL)
        if preamble_match:
            sections["_preamble"] = preamble_match.group(1)

        postamble_pattern = r"(\\bibliography.*?\\end\{document\}.*?)$"
        postamble_match = re.search(postamble_pattern, content, re.DOTALL)
        if postamble_match:
            sections["_postamble"] = postamble_match.group(1)

        # Save section order to metadata file for later reconstruction
        self._save_section_order(section_order)

        return sections

    def normalize_section_id(self, section_title: str) -> str:
        """Normalize section title to a valid identifier.

        Args:
            section_title: Raw section title (e.g., "Introduction")

        Returns:
            Normalized identifier (e.g., "introduction")
        """
        # Lowercase, replace spaces with underscores, remove non-alphanumeric
        clean = re.sub(r"[^a-zA-Z0-9\s]", "", section_title)
        return clean.strip().lower().replace(" ", "_")

    def _save_section_order(self, order: List[str]) -> None:
        """Save the original order of sections."""
        metadata_path = self.sections_dir / "section_order.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump({"order": order}, f, indent=2)

    def get_section_order(self) -> List[str]:
        """Retrieve the original section order."""
        metadata_path = self.sections_dir / "section_order.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("order", [])
        return []

    def save_section_original(self, section_id: str, content: str) -> Path:
        """Save the original version of a section.

        Args:
            section_id: Normalized section identifier
            content: Section content

        Returns:
            Path to the saved file
        """
        section_dir = self.sections_dir / section_id
        section_dir.mkdir(parents=True, exist_ok=True)

        original_path = section_dir / "original.tex"
        self._write_file(original_path, content)

        # Create basic metadata
        metadata = {
            "section_id": section_id,
            "version": "original",
            "iteration": 0,
            "timestamp": datetime.now().isoformat(),
            "token_count": self._count_tokens(content),
        }
        metadata_path = section_dir / "original_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return original_path

    def save_section_version(
        self,
        section_id: str,
        content: str,
        iteration: int,
        pass_id: int,
        is_final: bool = False,
    ) -> Path:
        """Save a version of a section at a specific iteration/pass checkpoint.

        Args:
            section_id: Normalized section identifier
            content: Section content
            iteration: Iteration number (1+)
            pass_id: Pass number (1-5)
            is_final: Whether this is the final version for this pass

        Returns:
            Path to the saved file
        """
        section_dir = self.sections_dir / section_id / f"iter{iteration}"
        section_dir.mkdir(parents=True, exist_ok=True)

        # Determine filename
        if is_final:
            filename = f"pass{pass_id}_final.tex"
        else:
            filename = f"pass{pass_id}_working.tex"

        file_path = section_dir / filename
        self._write_file(file_path, content)

        # Save metadata
        metadata = {
            "section_id": section_id,
            "iteration": iteration,
            "pass_id": pass_id,
            "is_final": is_final,
            "timestamp": datetime.now().isoformat(),
            "token_count": self._count_tokens(content),
        }
        metadata_path = section_dir / f"{filename.replace('.tex', '_metadata.json')}"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        return file_path

    def get_section_three_versions(
        self, section_id: str, iteration: int, current_pass: int
    ) -> Dict[str, Optional[str]]:
        """Get three versions of a section for residual diff computation.

        Args:
            section_id: Normalized section identifier
            iteration: Current iteration number
            current_pass: Current pass number

        Returns:
            Dictionary with keys: 'original', 'previous', 'current'
            - original: The initial version (iteration 0)
            - previous: The version from the previous pass (or None if pass 1)
            - current: The current working version
        """
        versions: Dict[str, Optional[str]] = {
            "original": None,
            "previous": None,
            "current": None,
        }

        section_dir = self.sections_dir / section_id

        # Get original version
        original_path = section_dir / "original.tex"
        if original_path.exists():
            versions["original"] = self._read_file(original_path)

        # Get previous version
        if current_pass > 1:
            # Previous pass in same iteration
            previous_path = (
                section_dir / f"iter{iteration}" / f"pass{current_pass - 1}_final.tex"
            )
            if previous_path.exists():
                versions["previous"] = self._read_file(previous_path)
            else:
                # Fallback: search for any previous pass in this iteration or previous iterations
                found_previous = False
                for prev_pass in range(current_pass - 1, 0, -1):
                    fallback_path = (
                        section_dir / f"iter{iteration}" / f"pass{prev_pass}_final.tex"
                    )
                    if fallback_path.exists():
                        versions["previous"] = self._read_file(fallback_path)
                        found_previous = True
                        break
                # If still not found, check previous iterations
                if not found_previous:
                    for prev_iter in range(iteration - 1, 0, -1):
                        for prev_pass in range(5, 0, -1):
                            fallback_path = (
                                section_dir
                                / f"iter{prev_iter}"
                                / f"pass{prev_pass}_final.tex"
                            )
                            if fallback_path.exists():
                                versions["previous"] = self._read_file(fallback_path)
                                found_previous = True
                                break
                        if found_previous:
                            break
                # Ultimate fallback: use original
                if not found_previous:
                    versions["previous"] = versions["original"]
        elif iteration > 1:
            # Last pass of previous iteration - try to find any previous version
            previous_iter_path = (
                section_dir / f"iter{iteration - 1}" / "pass5_final.tex"
            )
            if previous_iter_path.exists():
                versions["previous"] = self._read_file(previous_iter_path)
            else:
                # Fallback: search for any previous iteration's final version
                found_previous = False
                for prev_iter in range(iteration - 1, 0, -1):
                    for prev_pass in range(5, 0, -1):
                        fallback_path = (
                            section_dir
                            / f"iter{prev_iter}"
                            / f"pass{prev_pass}_final.tex"
                        )
                        if fallback_path.exists():
                            versions["previous"] = self._read_file(fallback_path)
                            found_previous = True
                            break
                    if found_previous:
                        break
                # Ultimate fallback: use original
                if not found_previous:
                    versions["previous"] = versions["original"]
        else:
            # No previous version for iteration 1, pass 1
            versions["previous"] = versions["original"]

        # Get current working version
        current_path = (
            section_dir / f"iter{iteration}" / f"pass{current_pass}_working.tex"
        )
        if current_path.exists():
            versions["current"] = self._read_file(current_path)
        else:
            # If no working version yet, use previous as current
            versions["current"] = versions["previous"]

        return versions

    def compute_residual_diff(
        self, section_id: str, iteration: int, current_pass: int, context_lines: int = 3
    ) -> str:
        """Compute residual diff showing only new changes not in previous version.

        Args:
            section_id: Normalized section identifier
            iteration: Current iteration number
            current_pass: Current pass number
            context_lines: Number of context lines to include (default: 3)

        Returns:
            Unified diff string showing changes from previous to current
        """
        versions = self.get_section_three_versions(section_id, iteration, current_pass)

        if versions["previous"] is None or versions["current"] is None:
            return ""

        # Generate unified diff
        previous_lines = versions["previous"].splitlines(keepends=True)
        current_lines = versions["current"].splitlines(keepends=True)

        diff = difflib.unified_diff(
            previous_lines,
            current_lines,
            fromfile=f"{section_id}_previous",
            tofile=f"{section_id}_current",
            n=context_lines,
        )

        return "".join(diff)

    def merge_sections_to_paper(
        self,
        sections: Dict[str, str],
        output_path: Path,
        section_order: Optional[List[str]] = None,
    ) -> Path:
        """Merge section versions back into a complete paper.

        Args:
            sections: Dictionary mapping section_id -> content
            output_path: Path where to save the merged paper
            section_order: Optional list of section IDs in desired order.
                           If not provided, uses the saved original order.

        Returns:
            Path to the saved paper
        """
        # Reconstruct the paper
        parts = []

        # Add preamble if exists
        if "_preamble" in sections:
            parts.append(sections["_preamble"])

        # Get section order: use provided order, or load from saved metadata
        if section_order is None:
            section_order = self.get_section_order()

        # Add sections in the correct order
        # First add sections that are in the order list
        added_sections = set()
        for section_id in section_order:
            if section_id in sections:
                parts.append(sections[section_id])
                added_sections.add(section_id)

        # Then add any remaining sections not in the order list (shouldn't happen normally)
        for section_id in sections.keys():
            if not section_id.startswith("_") and section_id not in added_sections:
                parts.append(sections[section_id])

        # Add postamble if exists
        if "_postamble" in sections:
            parts.append(sections["_postamble"])

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_file(output_path, "\n\n".join(parts))

        return output_path

    def get_section_content(
        self, section_id: str, iteration: int, pass_id: int, is_final: bool = True
    ) -> Optional[str]:
        """Retrieve section content at a specific iteration/pass.

        Falls back to previous versions if the specific version doesn't exist:
        - If iter{iteration}/pass{pass_id} doesn't exist, try iter{iteration}/pass{pass_id-1}
        - If that doesn't exist, try iter{iteration-1}/pass5
        - Eventually fall back to original.tex

        Args:
            section_id: Normalized section identifier
            iteration: Iteration number (0 for original)
            pass_id: Pass number (0 for original, 1-5 for passes)
            is_final: Whether to get final or working version

        Returns:
            Section content or None if not found
        """
        # Try to get the exact version first
        if iteration == 0:
            path = self.sections_dir / section_id / "original.tex"
            if path.exists():
                return self._read_file(path)
            return None

        # For iteration > 0, try multiple fallback options
        suffix = "final" if is_final else "working"

        # Option 1: Exact path iter{iteration}/pass{pass_id}
        path = (
            self.sections_dir
            / section_id
            / f"iter{iteration}"
            / f"pass{pass_id}_{suffix}.tex"
        )
        if path.exists():
            return self._read_file(path)

        # Option 2: Try previous passes in the same iteration
        for prev_pass in range(pass_id - 1, 0, -1):
            path = (
                self.sections_dir
                / section_id
                / f"iter{iteration}"
                / f"pass{prev_pass}_{suffix}.tex"
            )
            if path.exists():
                return self._read_file(path)

        # Option 3: Try previous iteration's pass5 (final)
        for prev_iter in range(iteration - 1, 0, -1):
            path = (
                self.sections_dir
                / section_id
                / f"iter{prev_iter}"
                / f"pass5_{suffix}.tex"
            )
            if path.exists():
                return self._read_file(path)

        # Option 4: Fall back to original
        path = self.sections_dir / section_id / "original.tex"
        if path.exists():
            return self._read_file(path)

        return None

    def _save_special_section(self, section_id: str, content: str) -> Path:
        """Save special sections like _preamble and _postamble.

        Args:
            section_id: Special section ID (_preamble or _postamble)
            content: Section content

        Returns:
            Path to the saved file
        """
        special_dir = self.sections_dir / "_special"
        special_dir.mkdir(parents=True, exist_ok=True)

        file_path = special_dir / f"{section_id}.tex"
        self._write_file(file_path, content)

        return file_path

    def _get_special_section(self, section_id: str) -> Optional[str]:
        """Retrieve special section content.

        Args:
            section_id: Special section ID (_preamble or _postamble)

        Returns:
            Section content or None if not found
        """
        file_path = self.sections_dir / "_special" / f"{section_id}.tex"
        if file_path.exists():
            return self._read_file(file_path)
        return None

    def list_sections(self, preserve_order: bool = True) -> List[str]:
        """List all section IDs that have been extracted.

        Args:
            preserve_order: If True, return sections in original document order.
                           If False, return alphabetically sorted.

        Returns:
            List of section IDs (excluding special keys like _preamble)
        """
        if not self.sections_dir.exists():
            return []

        # Get all section directories
        existing_sections = set()
        for item in self.sections_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                existing_sections.add(item.name)

        if preserve_order:
            # Return in original document order
            saved_order = self.get_section_order()
            # Filter to only include sections that still exist
            ordered_sections = [s for s in saved_order if s in existing_sections]
            # Add any sections not in saved order (shouldn't happen normally)
            for s in existing_sections:
                if s not in ordered_sections:
                    ordered_sections.append(s)
            return ordered_sections
        else:
            return sorted(existing_sections)

    def _count_tokens(self, text: str) -> int:
        """Estimate token count (simple whitespace-based approximation).

        Args:
            text: Text to count tokens in

        Returns:
            Approximate token count
        """
        # Simple approximation: split by whitespace
        # For more accurate counting, could use tiktoken library
        return len(text.split())

    def get_iteration_snapshot(
        self, iteration: int, pass_id: int = 5
    ) -> Dict[str, str]:
        """Get a snapshot of all sections at a specific iteration/pass.

        Args:
            iteration: Iteration number
            pass_id: Pass number (default: 5 for end of iteration)

        Returns:
            Dictionary mapping section_id -> content
        """
        sections = {}
        for section_id in self.list_sections():
            content = self.get_section_content(
                section_id, iteration, pass_id, is_final=True
            )
            if content:
                sections[section_id] = content

        # Include preamble and postamble if they exist (use special section retrieval)
        preamble = self._get_special_section("_preamble")
        if preamble:
            sections["_preamble"] = preamble

        postamble = self._get_special_section("_postamble")
        if postamble:
            sections["_postamble"] = postamble

        return sections
