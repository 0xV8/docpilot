# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**DO NOT** open a public issue for security vulnerabilities.

Instead, please report security issues via GitHub Security Advisories or email the maintainers directly.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will respond within 48 hours and provide a timeline for fixing the issue.

## Security Measures

### API Key Protection
- Never commit API keys to version control
- Use environment variables for sensitive data
- API keys are never logged

### Input Validation
- All file paths are validated to prevent traversal
- Code inputs are parsed safely using Python's AST module
- Size limits enforced on file uploads

### Dependency Security
- Dependencies scanned with `safety` and `pip-audit`
- Automated dependency updates via Dependabot
- Security advisories monitored

### Rate Limiting
- LLM API calls are rate-limited
- Configurable timeouts for all external requests
- Retry logic with exponential backoff

## Best Practices for Users

1. **Store API Keys Securely**
   ```bash
   # Use environment variables
   export OPENAI_API_KEY="your-key"

   # Or use .env file (add to .gitignore!)
   echo "OPENAI_API_KEY=your-key" > .env
   ```

2. **Limit File Access**
   ```toml
   [docpilot]
   include = ["src/**/*.py"]  # Explicit allowlist
   exclude = ["**/.env", "**/secrets/**"]
   ```

3. **Review Generated Documentation**
   - Always review before committing
   - May contain code patterns from training data
   - Verify no sensitive info exposed
