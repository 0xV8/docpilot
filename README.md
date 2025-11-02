# docpilot

> AI-powered documentation autopilot for Python projects

[![PyPI version](https://badge.fury.io/py/docpilot.svg)](https://badge.fury.io/py/docpilot)
[![Python Versions](https://img.shields.io/pypi/pyversions/docpilot.svg)](https://pypi.org/project/docpilot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**docpilot** automatically generates professional, comprehensive docstrings for your Python code using AI. Say goodbye to manual documentation and hello to intelligent, context-aware docstrings that follow your preferred style guide.

## Features

- **AI-Powered Generation**: Leverage GPT-4, Claude, or local LLMs (Ollama) to generate intelligent, context-aware docstrings
- **Multiple Docstring Styles**: Full support for Google, NumPy, and Sphinx docstring formats
- **Smart Code Analysis**: Understands your codebase structure, type hints, and complexity metrics
- **Production-Ready CLI**: Beautiful terminal UI with progress tracking and detailed reporting
- **Flexible Configuration**: Configure via TOML files, environment variables, or CLI arguments
- **Zero-Cost Option**: Use local LLMs (Ollama) for completely free operation
- **Batch Processing**: Process entire codebases with intelligent file discovery
- **Safe by Default**: Dry-run mode and diff preview before making changes

## Installation

### Basic Installation

```bash
pip install docpilot
```

### With Cloud LLM Support

```bash
# OpenAI and Anthropic support
pip install "docpilot[llm]"
```

### With Local LLM Support

```bash
# Ollama support for local, free LLM inference
pip install "docpilot[local]"
```

### Full Installation

```bash
# Everything including development tools
pip install "docpilot[all]"
```

## Quick Start

### 1. Initialize Configuration

```bash
docpilot init
```

This creates a `docpilot.toml` configuration file with sensible defaults.

### 2. Set Up Your LLM Provider

#### Option A: OpenAI

```bash
export OPENAI_API_KEY="your-api-key-here"
```

#### Option B: Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

#### Option C: Local LLM (Free)

```bash
# Install Ollama from https://ollama.ai
ollama pull llama2
```

### 3. Generate Docstrings

```bash
# Generate for a single file
docpilot generate mymodule.py

# Generate for entire project
docpilot generate ./src --style google

# Preview changes without modifying files
docpilot generate ./src --dry-run --diff
```

## Usage Examples

### Analyze Code Structure

Examine your code without generating documentation:

```bash
docpilot analyze ./src --show-complexity --show-patterns
```

**Output:**
```
Analyzing ./src/myproject/utils.py...
✓ Found 15 elements (12 public, 3 private)

Functions:
├── calculate_total (line 10) - complexity: 3
├── validate_input (line 25) - complexity: 5
└── process_data (line 45) - complexity: 8
```

### Generate with Custom Configuration

```bash
docpilot generate ./src \
  --provider anthropic \
  --model claude-3-sonnet-20240229 \
  --style numpy \
  --include-private \
  --overwrite
```

### Test LLM Connection

Verify your API credentials before processing:

```bash
docpilot test-connection --provider openai
```

## Real-World Example

**Before:**
```python
def calculate_compound_interest(principal, rate, time, frequency):
    return principal * (1 + rate / frequency) ** (frequency * time)
```

**After (Google Style):**
```python
def calculate_compound_interest(principal, rate, time, frequency):
    """Calculate compound interest for a given principal amount.

    This function computes the future value of an investment using the
    compound interest formula: A = P(1 + r/n)^(nt), where interest is
    compounded at regular intervals.

    Args:
        principal (float): The initial investment amount in dollars.
        rate (float): Annual interest rate as a decimal (e.g., 0.05 for 5%).
        time (float): Investment duration in years.
        frequency (int): Number of times interest is compounded per year
            (e.g., 12 for monthly, 4 for quarterly).

    Returns:
        float: The total amount after interest, including the principal.

    Examples:
        >>> calculate_compound_interest(1000, 0.05, 10, 12)
        1647.01

        >>> calculate_compound_interest(5000, 0.03, 5, 4)
        5806.11
    """
    return principal * (1 + rate / frequency) ** (frequency * time)
```

## Configuration

### Configuration File

Create `docpilot.toml` in your project root:

```toml
[docpilot]
# Docstring style: google, numpy, sphinx, or auto
style = "google"

# Overwrite existing docstrings
overwrite = false

# Include private elements (with leading underscore)
include_private = false

# Code analysis options
analyze_code = true
calculate_complexity = true
infer_types = true
detect_patterns = true

# Generation options
include_examples = true
max_line_length = 88

# File patterns
file_pattern = "**/*.py"
exclude_patterns = [
    "**/test_*.py",
    "**/*_test.py",
    "**/tests/**",
    "**/__pycache__/**",
]

# LLM settings
llm_provider = "openai"
llm_model = "gpt-3.5-turbo"
llm_temperature = 0.7
llm_max_tokens = 2000
llm_timeout = 30

# Project context (helps generate better docs)
project_name = "My Awesome Project"
project_description = "A Python library for awesome things"
```

### Environment Variables

All configuration can be set via environment variables with the `DOCPILOT_` prefix:

```bash
export DOCPILOT_STYLE="numpy"
export DOCPILOT_LLM_PROVIDER="anthropic"
export DOCPILOT_LLM_MODEL="claude-3-haiku-20240307"
export DOCPILOT_OVERWRITE="true"
```

### CLI Arguments

CLI arguments override both file and environment configuration:

```bash
docpilot generate ./src \
  --style sphinx \
  --provider local \
  --model llama2 \
  --overwrite
```

## Supported Docstring Styles

### Google Style (Default)

```python
def example(arg1, arg2):
    """Short description.

    Longer description if needed.

    Args:
        arg1 (int): Description of arg1.
        arg2 (str): Description of arg2.

    Returns:
        bool: Description of return value.

    Raises:
        ValueError: When validation fails.
    """
```

### NumPy Style

```python
def example(arg1, arg2):
    """Short description.

    Longer description if needed.

    Parameters
    ----------
    arg1 : int
        Description of arg1.
    arg2 : str
        Description of arg2.

    Returns
    -------
    bool
        Description of return value.

    Raises
    ------
    ValueError
        When validation fails.
    """
```

### Sphinx Style

```python
def example(arg1, arg2):
    """Short description.

    Longer description if needed.

    :param arg1: Description of arg1.
    :type arg1: int
    :param arg2: Description of arg2.
    :type arg2: str
    :return: Description of return value.
    :rtype: bool
    :raises ValueError: When validation fails.
    """
```

## LLM Providers

### OpenAI

Best for: High-quality, consistent docstrings

```bash
# Supported models
docpilot generate ./src --provider openai --model gpt-4
docpilot generate ./src --provider openai --model gpt-3.5-turbo
```

### Anthropic (Claude)

Best for: Detailed explanations and complex code

```bash
# Supported models
docpilot generate ./src --provider anthropic --model claude-3-opus-20240229
docpilot generate ./src --provider anthropic --model claude-3-sonnet-20240229
docpilot generate ./src --provider anthropic --model claude-3-haiku-20240307
```

### Local (Ollama)

Best for: Privacy, cost-free operation, offline work

```bash
# First, pull a model
ollama pull llama2
ollama pull codellama
ollama pull mistral

# Then use it
docpilot generate ./src --provider local --model llama2
```

## Requirements

- **Python**: 3.9 or higher
- **Operating System**: Linux, macOS, Windows
- **Optional**: OpenAI API key, Anthropic API key, or Ollama installation

## Advanced Usage

### Using in CI/CD

```yaml
# .github/workflows/docs.yml
name: Generate Documentation

on: [push, pull_request]

jobs:
  generate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install docpilot
        run: pip install "docpilot[llm]"

      - name: Generate docstrings
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          docpilot generate ./src --dry-run
```

### Integration with pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: docpilot
        name: Generate docstrings
        entry: docpilot generate --dry-run
        language: system
        types: [python]
```

### Programmatic Usage

```python
from docpilot.core.generator import DocstringGenerator
from docpilot.llm.base import create_provider, LLMConfig, LLMProvider
from docpilot.core.models import DocstringStyle

# Configure LLM
config = LLMConfig(
    provider=LLMProvider.OPENAI,
    model="gpt-3.5-turbo",
    api_key="your-api-key"
)

# Create generator
llm = create_provider(config)
generator = DocstringGenerator(llm_provider=llm)

# Generate docstrings
import asyncio

async def generate():
    results = await generator.generate_for_file(
        file_path="mymodule.py",
        style=DocstringStyle.GOOGLE,
        include_private=False,
        overwrite_existing=False
    )

    for doc in results:
        print(f"{doc.element_name}: {doc.docstring}")

asyncio.run(generate())
```

## Performance

docpilot is designed for production use with large codebases:

- **Parallel Processing**: Processes multiple files concurrently
- **Smart Caching**: Avoids redundant LLM calls
- **Rate Limiting**: Respects API rate limits automatically
- **Incremental Updates**: Only processes changed files

**Typical Performance:**
- Small project (50 functions): ~2-3 minutes with OpenAI
- Medium project (500 functions): ~20-30 minutes with OpenAI
- Large project (5000 functions): ~3-4 hours with OpenAI
- Local LLM: 2-3x slower but free

## Troubleshooting

### API Key Issues

```bash
# Verify API key is set
echo $OPENAI_API_KEY

# Test connection
docpilot test-connection --provider openai
```

### Rate Limiting

docpilot automatically handles rate limits, but you can adjust concurrency:

```toml
[docpilot]
llm_timeout = 60  # Increase timeout
llm_max_tokens = 1000  # Reduce token usage
```

### Quality Issues

If generated docstrings aren't meeting your standards:

1. **Try a better model**: Switch from `gpt-3.5-turbo` to `gpt-4`
2. **Provide context**: Set `project_name` and `project_description` in config
3. **Lower temperature**: Reduce `llm_temperature` to 0.3 for more focused output
4. **Add custom instructions**: Use `custom_instructions` in config

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/yourusername/docpilot.git
cd docpilot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run type checking
mypy src/docpilot

# Run linting
ruff check src/
black --check src/
```

## Roadmap

- [ ] Support for JavaScript/TypeScript
- [ ] Visual Studio Code extension
- [ ] Documentation website generation
- [ ] Custom LLM prompt templates
- [ ] Docstring quality scoring
- [ ] Automated documentation updates on code changes
- [ ] Integration with Sphinx/MkDocs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI
- Powered by [OpenAI](https://openai.com/), [Anthropic](https://www.anthropic.com/), and [Ollama](https://ollama.ai/)
- Terminal UI by [Rich](https://rich.readthedocs.io/)

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/docpilot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/docpilot/discussions)
- **Documentation**: [Read the Docs](https://docpilot.readthedocs.io)

---

If docpilot saves you time, please consider giving it a star on GitHub!
