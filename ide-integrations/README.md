# docpilot IDE Integration

This directory contains IDE integrations for docpilot, enabling seamless docstring generation directly in your editor.

## Supported Editors

- **VSCode** - Full support with extension
- **PyCharm** - LSP-based support
- **Vim/Neovim** - LSP-based support
- **Emacs** - LSP-based support
- **Sublime Text** - LSP-based support

## VSCode Extension

### Installation

#### From Marketplace (Coming Soon)
1. Open VSCode
2. Go to Extensions (Ctrl+Shift+X / Cmd+Shift+X)
3. Search for "docpilot"
4. Click Install

#### From Source
```bash
cd ide-integrations/vscode
npm install
npm run compile
code --install-extension .
```

### Configuration

Add to your VSCode `settings.json`:

```json
{
  "docpilot.enabled": true,
  "docpilot.style": "google",
  "docpilot.lsp.enabled": true,
  "docpilot.includePrivate": false,
  "docpilot.overwrite": false,
  "docpilot.showPatterns": true
}
```

### Usage

#### Keyboard Shortcuts
- **Generate Docstring**: `Ctrl+Shift+D` (Windows/Linux) / `Cmd+Shift+D` (Mac)

#### Commands
- **docpilot: Generate Docstring for Current Function** - Generate for function/class at cursor
- **docpilot: Generate Docstrings for File** - Generate for entire file
- **docpilot: Analyze Code Patterns** - Show detected patterns and complexity

#### Context Menu
Right-click in a Python file and select "docpilot: Generate Docstring"

### Features

- **Real-time Pattern Detection**: Identifies design patterns and anti-patterns
- **Hover Information**: Preview generated docstrings
- **Code Actions**: Quick-fix style docstring generation
- **Template Completion**: Auto-complete docstring templates
- **Multiple Styles**: Google, NumPy, Sphinx, reStructuredText, Epytext

## PyCharm Integration

### Setup

1. Install docpilot:
```bash
pip install docpilot
```

2. Configure External Tool:
   - Go to Settings → Tools → External Tools
   - Click "+" to add new tool
   - Name: "Generate Docstring"
   - Program: `docpilot`
   - Arguments: `generate $FilePath$ --style google`
   - Working directory: `$ProjectFileDir$`

3. Assign Keyboard Shortcut (optional):
   - Go to Settings → Keymap
   - Search for "Generate Docstring"
   - Right-click → Add Keyboard Shortcut

### LSP Support (Alternative)

1. Install LSP Support plugin from JetBrains Marketplace
2. Configure LSP server:
   - Settings → Languages & Frameworks → Language Server Protocol
   - Add server:
     - Extension: `py`
     - Command: `docpilot lsp`

## Vim/Neovim Integration

### Using coc.nvim

1. Install docpilot:
```bash
pip install docpilot
```

2. Add to `coc-settings.json`:
```json
{
  "languageserver": {
    "docpilot": {
      "command": "docpilot",
      "args": ["lsp"],
      "filetypes": ["python"],
      "rootPatterns": ["pyproject.toml", "setup.py", ".git/"]
    }
  }
}
```

3. Restart coc: `:CocRestart`

### Using vim-lsp

1. Add to `.vimrc` or `init.vim`:
```vim
if executable('docpilot')
  au User lsp_setup call lsp#register_server({
    \ 'name': 'docpilot',
    \ 'cmd': {server_info->['docpilot', 'lsp']},
    \ 'allowlist': ['python'],
    \ })
endif
```

### Using nvim-lspconfig (Neovim)

1. Add to `init.lua`:
```lua
local lspconfig = require('lspconfig')
local configs = require('lspconfig.configs')

-- Define docpilot LSP
if not configs.docpilot then
  configs.docpilot = {
    default_config = {
      cmd = {'docpilot', 'lsp'},
      filetypes = {'python'},
      root_dir = lspconfig.util.root_pattern('pyproject.toml', 'setup.py', '.git'),
      settings = {},
    },
  }
end

-- Setup docpilot LSP
lspconfig.docpilot.setup{}
```

### Manual Commands

Add to `.vimrc` for quick commands:
```vim
" Generate docstring for current function
nnoremap <leader>gd :!docpilot generate % --style google<CR>

" Generate docstrings for entire file
nnoremap <leader>ga :!docpilot generate %<CR>

" Analyze code patterns
nnoremap <leader>ap :!docpilot analyze % --show-patterns<CR>
```

## Emacs Integration

### Using lsp-mode

1. Install docpilot:
```bash
pip install docpilot
```

2. Add to your Emacs config:
```elisp
(require 'lsp-mode)

;; Register docpilot LSP server
(lsp-register-client
 (make-lsp-client
  :new-connection (lsp-stdio-connection '("docpilot" "lsp"))
  :major-modes '(python-mode)
  :server-id 'docpilot))

;; Enable for Python files
(add-hook 'python-mode-hook #'lsp)

;; Optional: Key bindings
(with-eval-after-load 'python
  (define-key python-mode-map (kbd "C-c d g") 'docpilot-generate-docstring)
  (define-key python-mode-map (kbd "C-c d a") 'docpilot-analyze))

;; Custom commands
(defun docpilot-generate-docstring ()
  "Generate docstring for current function."
  (interactive)
  (shell-command (format "docpilot generate %s --style google" (buffer-file-name)))
  (revert-buffer t t))

(defun docpilot-analyze ()
  "Analyze code patterns."
  (interactive)
  (shell-command (format "docpilot analyze %s --show-patterns --show-complexity" (buffer-file-name))))
```

## Sublime Text Integration

### LSP Setup

1. Install LSP package:
   - Package Control → Install Package → LSP

2. Install docpilot:
```bash
pip install docpilot
```

3. Configure LSP settings (Preferences → Package Settings → LSP → Settings):
```json
{
  "clients": {
    "docpilot": {
      "enabled": true,
      "command": ["docpilot", "lsp"],
      "selector": "source.python",
      "schemes": ["file"]
    }
  }
}
```

### Build System (Alternative)

1. Tools → Build System → New Build System
2. Save as `docpilot.sublime-build`:
```json
{
  "cmd": ["docpilot", "generate", "$file", "--style", "google"],
  "file_regex": "^(..[^:]*):([0-9]+):?([0-9]+)?:? (.*)$",
  "working_dir": "${project_path}",
  "selector": "source.python"
}
```

3. Use with Ctrl+B / Cmd+B

## Generic LSP Configuration

For any editor with LSP support:

1. **Server Command**: `docpilot lsp`
2. **File Types**: `python` (`.py` files)
3. **Root Patterns**: `pyproject.toml`, `setup.py`, `.git/`

### LSP Features Available

- **Code Actions**: Generate docstrings
- **Hover**: Preview docstring generation
- **Completion**: Docstring templates
- **Diagnostics**: Pattern detection and suggestions (future)

## Troubleshooting

### LSP Server Won't Start

1. Verify docpilot is installed:
```bash
which docpilot
docpilot --version
```

2. Test LSP server manually:
```bash
docpilot lsp
```

3. Check editor LSP logs for errors

### Commands Not Working

1. Ensure docpilot is in PATH:
```bash
echo $PATH
```

2. Try with full path:
```bash
/full/path/to/docpilot generate file.py
```

3. Check file permissions:
```bash
ls -la $(which docpilot)
```

### Pattern Detection Not Showing

1. Enable pattern detection in configuration:
```json
{
  "docpilot.showPatterns": true
}
```

2. Regenerate with `--overwrite` flag
3. Check docpilot version supports patterns (v0.2.0+)

## Configuration Options

### Style Selection

Available docstring styles:
- `google` - Google Style (default)
- `numpy` - NumPy Style
- `sphinx` - Sphinx Style
- `rest` - reStructuredText
- `epytext` - Epytext

### Flags

- `--overwrite` - Overwrite existing docstrings
- `--include-private` - Include private functions/methods
- `--dry-run` - Preview changes without applying
- `--diff` - Show diff of changes
- `--show-patterns` - Display detected patterns
- `--show-complexity` - Show complexity metrics

## Contributing

To add support for a new editor:

1. Check if editor supports LSP
2. If yes, use the generic LSP configuration
3. If no, create custom integration
4. Submit PR with documentation

## Support

- **Issues**: https://github.com/yourusername/docpilot/issues
- **Discussions**: https://github.com/yourusername/docpilot/discussions
- **Documentation**: https://docpilot.readthedocs.io

## License

MIT License - see LICENSE file for details
