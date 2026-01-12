# Contributing to Paper Refiner

Thank you for your interest in contributing to Paper Refiner!

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/paper_refiner.git`
3. Install dependencies: `uv sync`
4. Create a feature branch: `git checkout -b feature/your-feature-name`

## Code Style

- Follow PEP 8 for Python code
- Use type hints where applicable
- Add docstrings to public functions and classes
- Keep functions focused and testable

## Testing

Before submitting a PR:

```bash
# Run tests
uv run python tests/test_all.py

# Check syntax
python -m py_compile paper_refiner/**/*.py
```

## Pull Request Process

1. Update documentation if you're changing functionality
2. Ensure all tests pass
3. Update CHANGELOG.md with your changes
4. Submit PR with clear description of changes

## Reporting Issues

When reporting bugs, please include:
- Python version
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output

## Questions?

Open an issue with the "question" label.

---

Thank you for contributing! 🎉
