"""
Pass-Specific Review Prompts for 5-Pass Refinement Framework

Each prompt is TPAMI-specific and designed for a particular pass focus:
- Pass 1: Document Structure
- Pass 2: Section Coherence
- Pass 3: Paragraph Quality
- Pass 4: Sentence Refinement
- Pass 5: Final Polish

All prompts work with three-version context: original, previous, current.
"""

# =============================================================================
# Pass 1: Document Structure
# =============================================================================

STRUCTURE_PROMPT = """You are reviewing a TPAMI journal paper for **Pass 1: Document Structure**.

## Pass 1 Focus Areas
Focus ONLY on high-level structural issues:
- **Thesis clarity**: Is the paper's core contribution immediately clear?
- **Section organization**: Do sections follow logical TPAMI structure (Intro → Related Work → Method → Experiments → Conclusion)?
- **Taxonomy soundness**: Are categorizations and taxonomies well-motivated and comprehensive?
- **Scope appropriateness**: Is the scope appropriate for a TPAMI journal paper (not too narrow like a conference paper)?
- **Balance**: Are sections roughly balanced in importance and length?

## What to IGNORE in This Pass
- Paragraph-level writing quality (Pass 3)
- Sentence-level clarity or grammar (Pass 4)
- Citations, typos, formatting (Pass 5)
- Section-to-section transitions (Pass 2)

## Version Context
You will receive a brief summary of version availability (lengths only).
Do NOT assume full access to previous versions; focus on the **current** paper content below.

## TPAMI-Specific Guidelines
TPAMI papers should:
- Present significant contributions beyond incremental improvements
- Include comprehensive related work that positions the contribution clearly
- Provide thorough experimental validation on standard benchmarks
- Discuss limitations and broader impacts
- Be self-contained with sufficient background

## Issue Reporting Format
For each structural issue found, return a JSON object:

```json
{
  "id": "unique_issue_id",
  "type": "section_org" | "taxonomy" | "scope" | "thesis" | "balance",
  "priority": "P0" | "P1" | "P2",
  "title": "Brief issue title",
  "details": "Detailed explanation of the structural problem",
  "acceptance_criteria": "Concrete criteria to verify the fix",
  "affected_sections": ["section_name"],
  "suggested_fix": "High-level suggestion for reorganization",
  "pass_id": 1,
  "severity": "critical" | "major" | "minor"
}
```

## Priority Guidelines
- **P0 (Critical)**: Fundamental structural flaws that prevent acceptance (unclear thesis, missing key sections, incorrect scope)
- **P1 (Major)**: Significant organizational issues that weaken the paper (poor section balance, weak taxonomy)
- **P2 (Minor)**: Organizational improvements that would strengthen the paper

## Output
Return a JSON array of issues found:
```json
{
  "pass_id": 1,
  "pass_name": "Document Structure",
  "issues": [...]
}
```

Now review the paper and identify all document structure issues.
"""

# =============================================================================
# Pass 2: Section Coherence
# =============================================================================

COHERENCE_PROMPT = """You are reviewing a TPAMI journal paper for **Pass 2: Section Coherence**.

## Pass 2 Focus Areas
Focus ONLY on section-level flow and coherence:
- **Inter-section transitions**: Do sections connect smoothly? Are there jarring topic shifts?
- **Argument flow**: Does the narrative build logically from introduction through conclusion?
- **Section balance**: Is each section appropriately developed relative to its importance?
- **Redundancy**: Are there redundant discussions across sections?
- **Forward/backward references**: Do sections reference each other appropriately?

## What to IGNORE in This Pass
- Document structure (Pass 1 - assume sections are in correct order)
- Paragraph-level issues within sections (Pass 3)
- Sentence-level clarity (Pass 4)
- Citations, typos (Pass 5)

## Version Context
You will receive a brief summary of version availability (lengths only).
Do NOT assume full access to previous versions; focus on the **current** paper content below.

## TPAMI-Specific Guidelines
For TPAMI papers:
- Introduction should motivate the problem and preview the solution
- Related Work should clearly differentiate from prior work
- Method sections should build progressively (overview → details → analysis)
- Experiments should follow a clear evaluation strategy
- Conclusion should tie back to introduction's promises

## Issue Reporting Format
```json
{
  "id": "unique_issue_id",
  "type": "transitions" | "logic_flow" | "balance" | "section_coherence" | "redundancy",
  "priority": "P0" | "P1" | "P2",
  "title": "Brief issue title",
  "details": "Detailed explanation of the coherence problem",
  "acceptance_criteria": "Concrete criteria to verify the fix",
  "affected_sections": ["section1", "section2"],
  "suggested_fix": "How to improve the flow between sections",
  "pass_id": 2,
  "severity": "critical" | "major" | "minor"
}
```

## Priority Guidelines
- **P0 (Critical)**: Broken argument flow that confuses the reader
- **P1 (Major)**: Missing transitions or balance issues that weaken comprehension
- **P2 (Minor)**: Minor flow improvements

## Output
```json
{
  "pass_id": 2,
  "pass_name": "Section Coherence",
  "issues": [...]
}
```

Now review the paper and identify all section coherence issues.
"""

# =============================================================================
# Pass 3: Paragraph Quality
# =============================================================================

PARAGRAPH_PROMPT = """You are reviewing a TPAMI journal paper for **Pass 3: Paragraph Quality**.

## Pass 3 Focus Areas
Focus ONLY on paragraph-level structure and quality:
- **Topic sentences**: Does each paragraph have a clear topic sentence?
- **Evidence synthesis**: Are claims supported with appropriate evidence (citations, experimental results)?
- **Paragraph structure**: Does each paragraph follow a logical flow (claim → evidence → analysis)?
- **Unity**: Does each paragraph focus on a single coherent idea?
- **Length**: Are paragraphs appropriately sized (not too long/short)?
- **Technical depth**: Is the technical content at the right level for TPAMI?

## What to IGNORE in This Pass
- Document structure (Pass 1)
- Section-level transitions (Pass 2)
- Sentence-level grammar or style (Pass 4)
- Citations formatting, typos (Pass 5)

## Version Context
You will receive a brief summary of version availability (lengths only).
Do NOT assume full access to previous versions; focus on the **current** paper content below.

## TPAMI-Specific Guidelines
TPAMI paragraphs should:
- Provide sufficient technical depth for expert readers
- Support claims with citations to authoritative sources
- Include quantitative evidence where appropriate
- Explain technical concepts clearly for the broader CV/ML community
- Balance novelty claims with acknowledgment of prior work

## Issue Reporting Format
```json
{
  "id": "unique_issue_id",
  "type": "topic_sentence" | "evidence" | "paragraph_structure" | "synthesis" | "technical_depth",
  "priority": "P0" | "P1" | "P2",
  "title": "Brief issue title",
  "details": "Detailed explanation of the paragraph problem",
  "acceptance_criteria": "Concrete criteria to verify the fix",
  "affected_sections": ["section_name"],
  "location": "Approximate paragraph location or first few words",
  "suggested_fix": "How to improve the paragraph",
  "pass_id": 3,
  "severity": "critical" | "major" | "minor"
}
```

## Priority Guidelines
- **P0 (Critical)**: Unsupported major claims, severely malformed paragraphs
- **P1 (Major)**: Missing topic sentences, poor evidence synthesis, structural problems
- **P2 (Minor)**: Minor improvements to paragraph flow or unity

## Output
```json
{
  "pass_id": 3,
  "pass_name": "Paragraph Quality",
  "issues": [...]
}
```

Now review the paper and identify all paragraph quality issues.
"""

# =============================================================================
# Pass 4: Sentence Refinement
# =============================================================================

SENTENCE_PROMPT = """You are reviewing a TPAMI journal paper for **Pass 4: Sentence Refinement**.

## Pass 4 Focus Areas
Focus ONLY on sentence-level clarity, style, and correctness:
- **Clarity**: Are sentences clear and unambiguous?
- **Conciseness**: Are there wordy or redundant constructions?
- **Grammar**: Are there grammatical errors?
- **Style**: Is the writing style appropriate for TPAMI (formal, technical, precise)?
- **Active voice**: Are passive constructions overused?
- **Jargon**: Is technical terminology used appropriately and consistently?
- **Readability**: Are complex sentences unnecessarily convoluted?

## What to IGNORE in This Pass
- Document structure (Pass 1)
- Section coherence (Pass 2)
- Paragraph structure (Pass 3)
- Citations, typos, minor formatting (Pass 5)

## Version Context
You will receive a brief summary of version availability (lengths only).
Do NOT assume full access to previous versions; focus on the **current** paper content below.

## TPAMI-Specific Guidelines
TPAMI writing should:
- Use precise technical language
- Avoid colloquialisms and informal language
- Prefer active voice for clarity
- Use consistent terminology throughout
- Balance technical precision with readability
- Follow standard academic English conventions

## Issue Reporting Format
```json
{
  "id": "unique_issue_id",
  "type": "clarity" | "style" | "grammar" | "wordiness" | "consistency" | "voice",
  "priority": "P0" | "P1" | "P2",
  "title": "Brief issue title",
  "details": "Detailed explanation of the sentence problem",
  "acceptance_criteria": "Concrete criteria to verify the fix",
  "affected_sections": ["section_name"],
  "location": "Quote the problematic sentence or phrase",
  "suggested_fix": "Specific rewrite suggestion",
  "pass_id": 4,
  "severity": "critical" | "major" | "minor"
}
```

## Priority Guidelines
- **P0 (Critical)**: Grammatical errors that obscure meaning, severe clarity issues
- **P1 (Major)**: Style problems that hurt readability, significant wordiness, unclear sentences
- **P2 (Minor)**: Minor style improvements, slight wordiness

## Output
```json
{
  "pass_id": 4,
  "pass_name": "Sentence Refinement",
  "issues": [...]
}
```

Now review the paper and identify all sentence-level issues.
"""

# =============================================================================
# Pass 5: Final Polish
# =============================================================================

POLISH_PROMPT = """You are reviewing a TPAMI journal paper for **Pass 5: Final Polish**.

## Pass 5 Focus Areas
Focus on final polishing details:
- **Citation formatting**: Are citations properly formatted in TPAMI style?
- **Citation completeness**: Are all claims properly cited?
- **Typos**: Spelling errors, typos
- **Formatting**: LaTeX formatting, equation formatting, figure/table references
- **Consistency**: Notation consistency, terminology consistency
- **References**: Are references complete and properly formatted?
- **Minor improvements**: Small tweaks that improve overall quality

## What to IGNORE in This Pass
- Major structural issues (should be fixed in Passes 1-4)
- Content problems (should be addressed in earlier passes)

## Version Context
You will receive a brief summary of version availability (lengths only).
Do NOT assume full access to previous versions; focus on the **current** paper content below.

## TPAMI-Specific Guidelines
TPAMI formatting requirements:
- Use IEEE citation style with \cite{} commands
- Number equations that are referenced
- Use consistent notation (define notation clearly in introduction/method)
- Format algorithms using standard packages (algorithm2e, algorithmic)
- Ensure figures and tables are referenced in text
- Use proper mathematical typography (\mathbf, \mathcal, etc.)
- Avoid orphaned citations (citations without context)

## Issue Reporting Format
```json
{
  "id": "unique_issue_id",
  "type": "citation" | "typo" | "formatting" | "minor" | "consistency" | "notation",
  "priority": "P1" | "P2",
  "title": "Brief issue title",
  "details": "Detailed explanation",
  "acceptance_criteria": "Concrete criteria to verify the fix",
  "affected_sections": ["section_name"],
  "location": "Specific location or quote",
  "suggested_fix": "Specific fix",
  "pass_id": 5,
  "severity": "major" | "minor"
}
```

## Priority Guidelines
- **P1 (Major)**: Missing citations for claims, significant formatting errors, notation inconsistencies
- **P2 (Minor)**: Typos, minor formatting improvements, small consistency issues

Note: Pass 5 does not assign P0 priority - critical issues should have been caught in earlier passes.

## Output
```json
{
  "pass_id": 5,
  "pass_name": "Final Polish",
  "issues": [...]
}
```

Now review the paper and identify all polishing issues.
"""

# =============================================================================
# Prompt Mapping
# =============================================================================

PASS_PROMPTS = {
    1: STRUCTURE_PROMPT,
    2: COHERENCE_PROMPT,
    3: PARAGRAPH_PROMPT,
    4: SENTENCE_PROMPT,
    5: POLISH_PROMPT
}

def get_pass_prompt(pass_id: int) -> str:
    """Get the review prompt for a specific pass.

    Args:
        pass_id: Pass number (1-5)

    Returns:
        The prompt string for that pass

    Raises:
        ValueError: If pass_id is not in range 1-5
    """
    if pass_id not in PASS_PROMPTS:
        raise ValueError(f"Invalid pass_id: {pass_id}. Must be 1-5.")
    return PASS_PROMPTS[pass_id]

def get_all_prompts() -> dict:
    """Get all pass prompts.

    Returns:
        Dictionary mapping pass_id (1-5) to prompt strings
    """
    return PASS_PROMPTS.copy()
