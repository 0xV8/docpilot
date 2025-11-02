# 🚁 docpilot

> AI-powered documentation autopilot for Python projects

[![PyPI version](https://badge.fury.io/py/docpilot.svg)](https://badge.fury.io/py/docpilot)
[![Python Versions](https://img.shields.io/pypi/pyversions/docpilot.svg)](https://pypi.org/project/docpilot/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/yourusername/docpilot/workflows/CI/badge.svg)](https://github.com/yourusername/docpilot/actions)
[![Coverage](https://codecov.io/gh/yourusername/docpilot/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/docpilot)

**docpilot** automatically generates professional docstrings and documentation for your Python code using AI. Stop writing docs manually—let docpilot do it for you!

## ✨ Features

- 🤖 **AI-Powered**: Uses GPT-4, Claude, or local LLMs to generate intelligent docstrings
- 📝 **Multi-Style Support**: Google, NumPy, and Sphinx docstring formats
- 🎨 **Beautiful CLI**: Rich terminal UI with progress tracking
- 📊 **Coverage Tracking**: Monitor and improve documentation coverage
- 🔄 **GitHub Actions**: Auto-generate docs on every push
- 🚀 **Fast & Free**: Local LLM support—no API costs
- 🎯 **Smart Context**: Understands your codebase for better docs
- ✅ **Validation**: Ensure existing docs meet quality standards

## 🚀 Quick Start

### Installation

```bash
# Basic installation
pip install docpilot

# With LLM support (OpenAI, Anthropic)
pip install "docpilot[llm]"

# With local LLM support (Ollama)
pip install "docpilot[local]"

# Everything
pip install "docpilot[all]"
```

### Usage

```bash
# Generate docstrings for your project
docpilot generate ./my_project

# Generate README.md
docpilot readme ./my_project --output README.md

# Check documentation coverage
docpilot coverage ./my_project --min-coverage 80

# Generate full documentation
docpilot docs ./my_project --output-dir ./docs

# Initialize configuration
docpilot init
```

## 📖 Example

**Before:**
```python
def calculate_compound_interest(principal, rate, time, frequency):
    return principal * (1 + rate / frequency) ** (frequency * time)
```

**After:**
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
        frequency (int): Number of times interest is compounded per year.

    Returns:
        float: The total amount after interest, including the principal.

    Examples:
        >>> calculate_compound_interest(1000, 0.05, 10, 12)
        1647.01
    """
    return principal * (1 + rate / frequency) ** (frequency * time)
```

## 🎯 Why docpilot?

| Problem | Solution |
|---------|----------|
| Writing docs is tedious | AI generates them automatically |
| Inconsistent doc styles | Enforces team-wide standards |
| Legacy code has no docs | Retroactively document entire codebases |
| API costs are high | Local LLM support (100% free) |
| Manual coverage tracking | Automated coverage reports |

## 🛠️ Configuration

Create `docpilot.toml` in your project root:

```toml
[docpilot]
style = "google"  # google, numpy, or sphinx
llm_provider = "openai"  # openai, anthropic, ollama, or none
llm_model = "gpt-4"
min_coverage = 80

include = ["**/*.py"]
exclude = ["tests/**", "**/venv/**"]

[llm]
temperature = 0.3
max_tokens = 500
include_examples = true
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🌟 Star History

If you find docpilot useful, please consider giving it a star! ⭐

---

**Made with ❤️ by the docpilot community**
