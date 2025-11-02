"""Rich UI components for the CLI.

This module provides beautiful terminal UI components using Rich library
for progress bars, tables, panels, and formatted output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree
from rich import box

from docpilot.core.models import (
    CodeElementType,
    GeneratedDocstring,
    ParseResult,
    DocstringStyle,
)


class DocpilotUI:
    """Rich terminal UI for docpilot.

    Provides methods for displaying progress, results, and interactive
    prompts in a beautiful terminal interface.

    Attributes:
        console: Rich console instance
        verbose: Enable verbose output
        quiet: Suppress non-error output
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        verbose: bool = False,
        quiet: bool = False,
    ) -> None:
        """Initialize the UI.

        Args:
            console: Rich console (creates new one if not provided)
            verbose: Enable verbose output
            quiet: Suppress non-error output
        """
        self.console = console or Console()
        self.verbose = verbose
        self.quiet = quiet

    def print_banner(self) -> None:
        """Print docpilot banner."""
        if self.quiet:
            return

        banner = """
[bold blue]╔═══════════════════════════════════════╗
║                                       ║
║         🚀 docpilot                  ║
║   AI-Powered Documentation Generator  ║
║                                       ║
╚═══════════════════════════════════════╝[/bold blue]
"""
        self.console.print(banner)

    def print_info(self, message: str, **kwargs: Any) -> None:
        """Print an info message.

        Args:
            message: Message to print
            **kwargs: Additional style arguments
        """
        if not self.quiet:
            self.console.print(f"[blue]ℹ[/blue] {message}", **kwargs)

    def print_success(self, message: str, **kwargs: Any) -> None:
        """Print a success message.

        Args:
            message: Message to print
            **kwargs: Additional style arguments
        """
        if not self.quiet:
            self.console.print(f"[green]✓[/green] {message}", **kwargs)

    def print_warning(self, message: str, **kwargs: Any) -> None:
        """Print a warning message.

        Args:
            message: Message to print
            **kwargs: Additional style arguments
        """
        if not self.quiet:
            self.console.print(f"[yellow]⚠[/yellow] {message}", **kwargs)

    def print_error(self, message: str, **kwargs: Any) -> None:
        """Print an error message.

        Args:
            message: Message to print
            **kwargs: Additional style arguments
        """
        self.console.print(f"[red]✗[/red] {message}", **kwargs)

    def print_debug(self, message: str, **kwargs: Any) -> None:
        """Print a debug message.

        Args:
            message: Message to print
            **kwargs: Additional style arguments
        """
        if self.verbose:
            self.console.print(f"[dim]🔍 {message}[/dim]", **kwargs)

    def create_progress(self) -> Progress:
        """Create a progress bar.

        Returns:
            Rich Progress instance
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

    def display_file_summary(self, result: ParseResult) -> None:
        """Display summary of parsed file.

        Args:
            result: Parse result to display
        """
        if self.quiet:
            return

        panel = Panel(
            f"""[bold]File:[/bold] {result.file_path}
[bold]Module:[/bold] {result.module_path}
[bold]Elements:[/bold] {len(result.elements)} ({len(result.public_elements)} public)
[bold]Lines:[/bold] {result.total_lines} total, {result.code_lines} code
[bold]Errors:[/bold] {len(result.parse_errors)}""",
            title="[bold cyan]Parse Result[/bold cyan]",
            border_style="cyan",
        )
        self.console.print(panel)

        if result.parse_errors and self.verbose:
            self.console.print("\n[bold red]Parse Errors:[/bold red]")
            for error in result.parse_errors:
                self.console.print(f"  • {error}")

    def display_generation_result(
        self,
        docstring: GeneratedDocstring,
        show_content: bool = False,
    ) -> None:
        """Display result of docstring generation.

        Args:
            docstring: Generated docstring to display
            show_content: Whether to show the full docstring content
        """
        if self.quiet:
            return

        # Build summary
        summary_lines = [
            f"[bold]Element:[/bold] {docstring.element_name}",
            f"[bold]Type:[/bold] {docstring.element_type.value}",
            f"[bold]Style:[/bold] {docstring.style.value}",
            f"[bold]Confidence:[/bold] {docstring.confidence_score:.1%}",
        ]

        if docstring.warnings:
            summary_lines.append(
                f"[bold yellow]Warnings:[/bold yellow] {len(docstring.warnings)}"
            )

        panel = Panel(
            "\n".join(summary_lines),
            title="[bold green]Generated Docstring[/bold green]",
            border_style="green",
        )
        self.console.print(panel)

        # Show warnings
        if docstring.warnings and self.verbose:
            self.console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in docstring.warnings:
                self.console.print(f"  • {warning}")

        # Show docstring content
        if show_content or self.verbose:
            syntax = Syntax(
                docstring.docstring,
                "python",
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
            self.console.print("\n[bold]Docstring Content:[/bold]")
            self.console.print(syntax)

    def display_statistics(
        self,
        total_files: int,
        total_elements: int,
        generated_count: int,
        skipped_count: int,
        error_count: int,
        duration_seconds: float,
    ) -> None:
        """Display overall statistics.

        Args:
            total_files: Number of files processed
            total_elements: Total code elements found
            generated_count: Number of docstrings generated
            skipped_count: Number of elements skipped
            error_count: Number of errors encountered
            duration_seconds: Total duration in seconds
        """
        if self.quiet:
            return

        table = Table(title="[bold cyan]Generation Statistics[/bold cyan]", box=box.ROUNDED)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta", justify="right")

        table.add_row("Files Processed", str(total_files))
        table.add_row("Total Elements", str(total_elements))
        table.add_row("Generated", f"[green]{generated_count}[/green]")
        table.add_row("Skipped", f"[yellow]{skipped_count}[/yellow]")
        table.add_row("Errors", f"[red]{error_count}[/red]" if error_count > 0 else "0")
        table.add_row("Duration", f"{duration_seconds:.2f}s")

        if generated_count > 0:
            rate = generated_count / duration_seconds
            table.add_row("Rate", f"{rate:.2f}/s")

        self.console.print(table)

    def display_element_tree(self, result: ParseResult) -> None:
        """Display code elements as a tree.

        Args:
            result: Parse result with elements
        """
        if self.quiet:
            return

        tree = Tree(
            f"[bold cyan]{result.module_path}[/bold cyan]",
            guide_style="dim",
        )

        # Group by type
        classes = result.get_elements_by_type(CodeElementType.CLASS)
        functions = result.get_elements_by_type(CodeElementType.FUNCTION)
        methods = result.get_elements_by_type(CodeElementType.METHOD)

        # Add classes and their methods
        for cls in classes:
            icon = "📦" if cls.is_public else "🔒"
            class_node = tree.add(f"{icon} [bold]{cls.name}[/bold]")

            # Find methods of this class
            class_methods = [m for m in methods if m.parent_class == cls.name]
            for method in class_methods:
                method_icon = "🔒" if not method.is_public else ("⚙️" if method.is_property else "🔧")
                method_node = class_node.add(f"{method_icon} {method.name}")

        # Add standalone functions
        if functions:
            func_node = tree.add("[bold]Functions[/bold]")
            for func in functions:
                icon = "🔒" if not func.is_public else "⚡"
                func_node.add(f"{icon} {func.name}")

        self.console.print(tree)

    def display_diff(self, diff_text: str) -> None:
        """Display a diff with syntax highlighting.

        Args:
            diff_text: Unified diff text
        """
        if self.quiet:
            return

        syntax = Syntax(
            diff_text,
            "diff",
            theme="monokai",
            line_numbers=False,
        )
        self.console.print(syntax)

    def prompt_confirm(self, message: str, default: bool = False) -> bool:
        """Prompt user for yes/no confirmation.

        Args:
            message: Prompt message
            default: Default value if user just presses enter

        Returns:
            True if user confirmed, False otherwise
        """
        if self.quiet:
            return default

        default_str = "Y/n" if default else "y/N"
        response = self.console.input(f"{message} [{default_str}]: ").strip().lower()

        if not response:
            return default

        return response in ("y", "yes")

    def display_config(self, config: dict[str, Any]) -> None:
        """Display configuration as a table.

        Args:
            config: Configuration dictionary
        """
        if self.quiet:
            return

        table = Table(title="[bold cyan]Configuration[/bold cyan]", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")

        for key, value in sorted(config.items()):
            # Hide sensitive values
            if "api_key" in key.lower() and value:
                value = "***" + str(value)[-4:] if len(str(value)) > 4 else "***"

            table.add_row(key, str(value))

        self.console.print(table)

    def display_file_list(
        self,
        files: list[Path],
        title: str = "Files to Process",
    ) -> None:
        """Display a list of files.

        Args:
            files: List of file paths
            title: Table title
        """
        if self.quiet:
            return

        table = Table(title=f"[bold cyan]{title}[/bold cyan]", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("File Path", style="cyan")
        table.add_column("Size", style="magenta", justify="right")

        for idx, file in enumerate(files, 1):
            size = file.stat().st_size
            size_str = self._format_size(size)
            table.add_row(str(idx), str(file), size_str)

        self.console.print(table)

    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format.

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted size string
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"


# Global UI instance
_ui: Optional[DocpilotUI] = None


def get_ui(
    console: Optional[Console] = None,
    verbose: bool = False,
    quiet: bool = False,
) -> DocpilotUI:
    """Get or create the global UI instance.

    Args:
        console: Rich console
        verbose: Enable verbose output
        quiet: Suppress non-error output

    Returns:
        DocpilotUI instance
    """
    global _ui
    if _ui is None:
        _ui = DocpilotUI(console=console, verbose=verbose, quiet=quiet)
    return _ui
