"""
Data migration script for upgrading issues.json to v2.0 schema.

This script:
1. Reads existing issues.json (v1.0 format)
2. Adds iteration, pass_id, and resolution tracking fields
3. Backs up the original file
4. Writes the upgraded schema

Usage:
    python -m paper_refiner.tools.migrate_issues <work_dir>
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Import the pass classification mapping
from paper_refiner.core.issue_tracker import ISSUE_TYPE_TO_PASS


def classify_issue_by_pass(issue: Dict[str, Any]) -> int:
    """Classify an issue to determine which pass it belongs to.

    Args:
        issue: Issue dictionary

    Returns:
        Pass number (1-5), or 0 if cannot classify
    """
    issue_type = issue.get('type', '').lower()

    # Direct lookup
    if issue_type in ISSUE_TYPE_TO_PASS:
        return ISSUE_TYPE_TO_PASS[issue_type]

    # Fuzzy matching based on description
    description = issue.get('details', '').lower()
    combined = f"{issue_type} {description}"

    # Pass 1: Document Structure
    if any(kw in combined for kw in ['structure', 'organization', 'thesis', 'taxonomy', 'scope']):
        return 1

    # Pass 2: Section Coherence
    if any(kw in combined for kw in ['transition', 'coherence', 'flow', 'section']):
        return 2

    # Pass 3: Paragraph Quality
    if any(kw in combined for kw in ['paragraph', 'topic sentence', 'evidence']):
        return 3

    # Pass 4: Sentence Refinement
    if any(kw in combined for kw in ['clarity', 'grammar', 'sentence', 'style']):
        return 4

    # Pass 5: Final Polish
    if any(kw in combined for kw in ['citation', 'typo', 'format', 'polish']):
        return 5

    # Cannot classify
    return 0


def migrate_issues_json(work_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Migrate issues.json to v2.0 schema.

    Args:
        work_dir: Working directory containing issues.json
        dry_run: If True, don't write changes, just report

    Returns:
        Dictionary with migration statistics
    """
    issues_path = work_dir / "issues.json"

    if not issues_path.exists():
        print(f"❌ Error: {issues_path} does not exist")
        return {'error': 'File not found'}

    # Read existing issues
    print(f"Reading {issues_path}...")
    with open(issues_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    issues = data.get('issues', [])
    print(f"Found {len(issues)} issues")

    # Statistics
    stats = {
        'total_issues': len(issues),
        'already_migrated': 0,
        'needs_migration': 0,
        'by_pass': {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
        'errors': []
    }

    # Migrate each issue
    migrated_issues = []
    for i, issue in enumerate(issues):
        # Check if already migrated
        if 'iteration' in issue and 'pass_id' in issue:
            stats['already_migrated'] += 1
            migrated_issues.append(issue)
            continue

        stats['needs_migration'] += 1

        try:
            # Add iteration field (default: 0 for existing issues)
            issue['iteration'] = issue.get('iteration', 0)

            # Add pass_id (auto-classify)
            if 'pass_id' not in issue:
                pass_id = classify_issue_by_pass(issue)
                issue['pass_id'] = pass_id
                stats['by_pass'][pass_id] += 1

            # Add resolution tracking
            if 'resolved_in_iteration' not in issue:
                issue['resolved_in_iteration'] = None

            if 'resolved_in_pass' not in issue:
                issue['resolved_in_pass'] = None

            # Add type field if missing (for future classification)
            if 'type' not in issue:
                issue['type'] = 'unknown'

            migrated_issues.append(issue)

        except Exception as e:
            stats['errors'].append(f"Issue {i} ({issue.get('id', 'unknown')}): {str(e)}")
            # Keep original issue if migration fails
            migrated_issues.append(issue)

    # Report
    print("\n=== Migration Report ===")
    print(f"Total issues: {stats['total_issues']}")
    print(f"Already migrated: {stats['already_migrated']}")
    print(f"Newly migrated: {stats['needs_migration']}")
    print("\nIssues by pass:")
    for pass_id in sorted(stats['by_pass'].keys()):
        count = stats['by_pass'][pass_id]
        if count > 0:
            pass_name = {
                0: "Unclassified",
                1: "Document Structure",
                2: "Section Coherence",
                3: "Paragraph Quality",
                4: "Sentence Refinement",
                5: "Final Polish"
            }.get(pass_id, f"Pass {pass_id}")
            print(f"  Pass {pass_id} ({pass_name}): {count}")

    if stats['errors']:
        print(f"\n⚠️  Errors: {len(stats['errors'])}")
        for error in stats['errors'][:5]:  # Show first 5 errors
            print(f"  - {error}")

    # Write migrated data
    if not dry_run:
        # Backup original file
        backup_path = issues_path.with_suffix('.json.backup')
        backup_path = work_dir / f"issues_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.backup"

        print(f"\nBacking up original to: {backup_path}")
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Write migrated data
        migrated_data = {'issues': migrated_issues}
        print(f"Writing migrated data to: {issues_path}")

        with open(issues_path, 'w', encoding='utf-8') as f:
            json.dump(migrated_data, f, indent=2, ensure_ascii=False)

        print("✅ Migration complete!")
    else:
        print("\n🔍 Dry run - no changes written")

    return stats


def main():
    """Main entry point for migration script."""
    if len(sys.argv) < 2:
        print("Usage: python -m paper_refiner.tools.migrate_issues <work_dir> [--dry-run]")
        print("\nExample:")
        print("  python -m paper_refiner.tools.migrate_issues ./work_dir")
        print("  python -m paper_refiner.tools.migrate_issues ./work_dir --dry-run")
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    dry_run = '--dry-run' in sys.argv

    if not work_dir.exists():
        print(f"❌ Error: Directory {work_dir} does not exist")
        sys.exit(1)

    print(f"Migrating issues in: {work_dir}")
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified\n")

    stats = migrate_issues_json(work_dir, dry_run=dry_run)

    if stats.get('error'):
        sys.exit(1)

    # Exit with error if there were migration errors
    if stats.get('errors'):
        sys.exit(2)


if __name__ == '__main__':
    main()
