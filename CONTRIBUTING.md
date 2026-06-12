# Contributing to HiveFlow

Thank you for your interest in contributing to HiveFlow! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [OSS Launch](#oss-launch-checklist)

## OSS Launch Checklist

If you are preparing a public release, see [OSS_LAUNCH.md](../OSS_LAUNCH.md) and [GOVERNANCE.md](../GOVERNANCE.md).

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend development)
- Git

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/hiveflow.git
cd hiveflow

# 2. Create a virtual environment
cd packages/core
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install with dev dependencies
pip install -e ".[dev]"

# 4. Install pre-commit hooks
pip install pre-commit
pre-commit install

# 5. Verify setup
pytest
ruff check hiveflow/
mypy hiveflow/
```

### Frontend Setup (Optional)

```bash
cd packages/studio/frontend
npm install
npm run dev
```

## Making Changes

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or improvements
- `ci/` - CI/CD changes

### 2. Make Your Changes

- Follow the [coding standards](#coding-standards)
- Add tests for new functionality
- Update documentation as needed

### 3. Run Tests and Linting

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=hiveflow --cov-report=term-missing

# Run linter
ruff check hiveflow/

# Run type checker
mypy hiveflow/

# Format code
ruff format hiveflow/
```

## Submitting a Pull Request

1. **Ensure your branch is up to date**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **Squash commits** (if applicable)
   ```bash
   git rebase -i HEAD~N
   ```

3. **Push your branch**
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Open a Pull Request** on GitHub

### PR Template

When opening a PR, please include:
- **Description**: What does this PR do?
- **Related Issues**: Link any related issues
- **Testing**: How was this tested?
- **Breaking Changes**: Note any breaking changes
- **Screenshots**: For UI changes

## Coding Standards

### Python Style

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use `ruff` for linting and formatting
- Line length: 120 characters
- Use type hints for function signatures

### Naming Conventions

- **Classes**: `PascalCase` (e.g., `BlackboardBackend`)
- **Functions/Methods**: `snake_case` (e.g., `get_value`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRIES`)
- **Private Methods**: Leading underscore (e.g., `_internal_helper`)

### Documentation

- All public APIs must have docstrings
- Use Google-style docstrings:
  ```python
  def create_worker(self, agent_id: str, skills: set[str]) -> Worker:
      """Create a new worker with the given capabilities.

      Args:
          agent_id: Unique identifier for the agent.
          skills: Set of skills the worker possesses.

      Returns:
          The created Worker instance.

      Raises:
          ValueError: If agent_id is empty.
      """
  ```

### Error Handling

- Use specific exception types
- Provide clear error messages
- Log errors with context (trace_id, agent_id, etc.)

## Testing Guidelines

### Writing Tests

- Name tests descriptively: `test_should_recover_from_timeout`
- Use the Arrange-Act-Assert pattern
- Mock external services (LLM APIs, Redis, etc.)
- Test both success and failure paths

### Test Categories

- **Unit Tests**: Test individual functions/classes
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete workflows

### Coverage

- Aim for >80% code coverage
- Focus on critical paths and edge cases
- Don't sacrifice quality for coverage numbers

## Documentation

### Updating Documentation

- Update relevant `.md` files for API changes
- Add examples to tutorials for new features
- Keep the README up to date
- **Bilingual docs:** edit matching files under `docs/en/` and `docs/zh/` (see [docs/en/i18n.md](docs/en/i18n.md))

### Writing Tutorials

- Start with the user's goal
- Provide complete, runnable code
- Include expected output
- Explain the "why" not just the "how"

## Release Process

Releases are managed by maintainers:

1. Update `CHANGELOG.md`
2. Bump version in `pyproject.toml`
3. Create a git tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. CI/CD automatically builds and publishes to PyPI

## Questions?

- Open a [GitHub Discussion](https://github.com/jdidjhdh/hiveflow/discussions)
- Open an [Issue](https://github.com/jdidjhdh/hiveflow/issues)
