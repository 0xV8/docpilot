"""Interactive approval mode for docstring generation.

This module provides interactive user interfaces for reviewing and approving
docstrings before they are written to files.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

if TYPE_CHECKING:
    from docpilot.core.models import CodeElement, GeneratedDocstring


class ApprovalAction(str, Enum):
    """Actions that can be taken when reviewing a docstring."""

    ACCEPT = "accept"
    REJECT = "reject"
    EDIT = "edit"
    QUIT = "quit"


@dataclass
class ApprovalResult:
    """Result of an interactive approval.

    Attributes:
        action: The action taken by the user
        docstring: The final docstring (possibly edited)
        element_name: Name of the code element
    """

    action: ApprovalAction
    docstring: str
    element_name: str


@dataclass
class InteractiveStats:
    """Statistics for interactive approval session.

    Attributes:
        accepted: Number of docstrings accepted
        rejected: Number of docstrings rejected
        edited: Number of docstrings edited
        skipped: Number of docstrings skipped (quit)
    """

    accepted: int = 0
    rejected: int = 0
    edited: int = 0
    skipped: int = 0

    @property
    def total_processed(self) -> int:
        """Total number of docstrings processed."""
        return self.accepted + self.rejected + self.edited

    @property
    def total_written(self) -> int:
        """Total number of docstrings written to files."""
        return self.accepted + self.edited


class InteractiveApprover:
    """Interactive approval interface for docstrings.

    This class provides a rich terminal interface for reviewing generated
    docstrings, showing diffs, and allowing users to approve, reject, or edit
    each docstring before it's written to the file.

    Attributes:
        console: Rich console for output
        stats: Statistics tracker for the session
    """

    def __init__(self, console: Console | None = None) -> None:
        """Initialize the interactive approver.

        Args:
            console: Rich console instance (creates new one if not provided)
        """
        self.console = console or Console()
        self.stats = InteractiveStats()

    def review_docstring(
        self,
        element: CodeElement,
        generated: GeneratedDocstring,
        file_path: Path,
    ) -> ApprovalResult:
        """Review a generated docstring and get user approval.

        Args:
            element: The code element being documented
            generated: The generated docstring to review
            file_path: Path to the file containing the element

        Returns:
            ApprovalResult with the user's decision and final docstring
        """
        # Clear screen for better UX
        self.console.clear()

        # Display header
        self._display_header(file_path, element, generated)

        # Display current docstring if any
        if element.has_docstring and element.docstring:
            self._display_section(
                "Current Docstring",
                element.docstring,
                "yellow",
            )

        # Display new docstring
        self._display_section(
            "Generated Docstring",
            generated.docstring,
            "green",
        )

        # Display diff if there's an existing docstring
        if element.has_docstring and element.docstring:
            self._display_diff(element.docstring, generated.docstring)

        # Display warnings if any
        if generated.warnings:
            self._display_warnings(generated.warnings)

        # Prompt for action
        action, final_docstring = self._prompt_action(generated.docstring)

        # Update statistics
        self._update_stats(action)

        return ApprovalResult(
            action=action,
            docstring=final_docstring,
            element_name=element.name,
        )

    def display_final_stats(self) -> None:
        """Display final statistics for the interactive session."""
        if self.stats.total_processed == 0:
            self.console.print("\n[yellow]No docstrings were processed.[/yellow]")
            return

        # Create statistics table
        table = Table(
            title="[bold cyan]Interactive Session Statistics[/bold cyan]",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Action", style="cyan", justify="left")
        table.add_column("Count", style="magenta", justify="right")
        table.add_column("Percentage", style="green", justify="right")

        total = self.stats.total_processed + self.stats.skipped

        # Add rows
        table.add_row(
            "Accepted",
            str(self.stats.accepted),
            f"{self._percentage(self.stats.accepted, total)}%",
        )
        table.add_row(
            "Rejected",
            str(self.stats.rejected),
            f"{self._percentage(self.stats.rejected, total)}%",
        )
        table.add_row(
            "Edited",
            str(self.stats.edited),
            f"{self._percentage(self.stats.edited, total)}%",
        )
        table.add_row(
            "Skipped (Quit)",
            str(self.stats.skipped),
            f"{self._percentage(self.stats.skipped, total)}%",
        )

        self.console.print("\n")
        self.console.print(table)

        # Summary message
        summary_parts = []
        if self.stats.total_written > 0:
            summary_parts.append(
                f"[green]{self.stats.total_written} docstrings written[/green]"
            )
        if self.stats.rejected > 0:
            summary_parts.append(
                f"[yellow]{self.stats.rejected} rejected[/yellow]"
            )
        if self.stats.skipped > 0:
            summary_parts.append(
                f"[red]{self.stats.skipped} skipped[/red]"
            )

        if summary_parts:
            self.console.print(f"\n{', '.join(summary_parts)}")

    def _display_header(
        self,
        file_path: Path,
        element: CodeElement,
        generated: GeneratedDocstring,
    ) -> None:
        """Display header with file and element information.

        Args:
            file_path: Path to the file
            element: Code element being documented
            generated: Generated docstring
        """
        element_full_name = (
            f"{element.parent_class}.{element.name}"
            if element.parent_class
            else element.name
        )

        header_text = f"""[bold]File:[/bold] {file_path}
[bold]Element:[/bold] {element_full_name}
[bold]Type:[/bold] {element.element_type.value}
[bold]Style:[/bold] {generated.style.value}
[bold]Confidence:[/bold] {generated.confidence_score:.1%}"""

        panel = Panel(
            header_text,
            title="[bold blue]Docstring Review[/bold blue]",
            border_style="blue",
        )
        self.console.print(panel)
        self.console.print()

    def _display_section(
        self,
        title: str,
        docstring: str,
        border_color: str,
    ) -> None:
        """Display a docstring section with syntax highlighting.

        Args:
            title: Section title
            docstring: Docstring content
            border_color: Border color for the panel
        """
        syntax = Syntax(
            docstring,
            "python",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
        )

        panel = Panel(
            syntax,
            title=f"[bold {border_color}]{title}[/bold {border_color}]",
            border_style=border_color,
        )
        self.console.print(panel)
        self.console.print()

    def _display_diff(self, old_docstring: str, new_docstring: str) -> None:
        """Display a diff between old and new docstrings.

        Args:
            old_docstring: Current docstring
            new_docstring: Generated docstring
        """
        import difflib

        # Generate unified diff
        old_lines = old_docstring.splitlines(keepends=True)
        new_lines = new_docstring.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="current",
            tofile="generated",
            lineterm="",
        )

        diff_text = "".join(diff)

        if diff_text:
            syntax = Syntax(
                diff_text,
                "diff",
                theme="monokai",
                line_numbers=False,
            )

            panel = Panel(
                syntax,
                title="[bold magenta]Diff[/bold magenta]",
                border_style="magenta",
            )
            self.console.print(panel)
            self.console.print()

    def _display_warnings(self, warnings: list[str]) -> None:
        """Display warnings about the generated docstring.

        Args:
            warnings: List of warning messages
        """
        warning_text = "\n".join(f"• {w}" for w in warnings)

        panel = Panel(
            warning_text,
            title="[bold yellow]Warnings[/bold yellow]",
            border_style="yellow",
        )
        self.console.print(panel)
        self.console.print()

    def _prompt_action(self, docstring: str) -> tuple[ApprovalAction, str]:
        """Prompt user for action on the docstring.

        Args:
            docstring: The generated docstring

        Returns:
            Tuple of (action, final_docstring)
        """
        while True:
            choice = Prompt.ask(
                "\n[bold cyan]What would you like to do?[/bold cyan]",
                choices=["a", "r", "e", "q"],
                default="a",
                show_choices=True,
                show_default=True,
            )

            choice = choice.lower()

            if choice == "a":
                return ApprovalAction.ACCEPT, docstring
            elif choice == "r":
                return ApprovalAction.REJECT, docstring
            elif choice == "e":
                edited_docstring = self._edit_docstring(docstring)
                if edited_docstring != docstring:
                    return ApprovalAction.EDIT, edited_docstring
                else:
                    # User didn't make changes, prompt again
                    self.console.print(
                        "[yellow]No changes made. Please choose another action.[/yellow]"
                    )
                    continue
            elif choice == "q":
                if self._confirm_quit():
                    return ApprovalAction.QUIT, docstring
                else:
                    continue

    def _edit_docstring(self, docstring: str) -> str:
        """Open docstring in editor for manual editing.

        Args:
            docstring: Original docstring

        Returns:
            Edited docstring
        """
        # Determine editor
        editor = self._get_editor()

        if not editor:
            self.console.print(
                "[red]No editor found. Set EDITOR environment variable.[/red]"
            )
            return docstring

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8",
        ) as tmp_file:
            # Write docstring with instructions
            tmp_file.write("# Edit the docstring below, then save and close\n")
            tmp_file.write("# Lines starting with # will be ignored\n")
            tmp_file.write('"""\n')
            tmp_file.write(docstring)
            tmp_file.write('\n"""\n')
            tmp_path = tmp_file.name

        try:
            # Open in editor
            subprocess.run([editor, tmp_path], check=True)

            # Read edited content
            with open(tmp_path, encoding="utf-8") as f:
                edited_content = f.read()

            # Extract docstring from edited content
            edited_docstring = self._extract_docstring_from_edited(edited_content)

            return edited_docstring

        except subprocess.CalledProcessError:
            self.console.print("[red]Editor exited with error.[/red]")
            return docstring
        except Exception as e:
            self.console.print(f"[red]Failed to edit docstring: {e}[/red]")
            return docstring
        finally:
            # Clean up temporary file
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

    def _get_editor(self) -> str | None:
        """Get the user's preferred editor.

        Returns:
            Editor command or None if not found
        """
        import os

        # Try EDITOR environment variable
        editor = os.environ.get("EDITOR")
        if editor:
            return editor

        # Try common editors
        common_editors = ["vim", "vi", "nano", "emacs", "code", "subl"]
        for editor in common_editors:
            if self._command_exists(editor):
                return editor

        return None

    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH.

        Args:
            command: Command name

        Returns:
            True if command exists, False otherwise
        """
        import shutil

        return shutil.which(command) is not None

    def _extract_docstring_from_edited(self, content: str) -> str:
        """Extract docstring from edited file content.

        Args:
            content: Edited file content

        Returns:
            Extracted docstring
        """
        lines = content.splitlines()

        # Remove comment lines
        lines = [line for line in lines if not line.strip().startswith("#")]

        # Find docstring boundaries
        in_docstring = False
        docstring_lines = []

        for line in lines:
            if '"""' in line or "'''" in line:
                if not in_docstring:
                    in_docstring = True
                    # Check if docstring starts on same line
                    after_quotes = line.split('"""', 1)[-1] if '"""' in line else line.split("'''", 1)[-1]
                    if after_quotes.strip() and '"""' not in after_quotes and "'''" not in after_quotes:
                        docstring_lines.append(after_quotes)
                else:
                    # End of docstring
                    before_quotes = line.split('"""', 1)[0] if '"""' in line else line.split("'''", 1)[0]
                    if before_quotes.strip():
                        docstring_lines.append(before_quotes)
                    break
            elif in_docstring:
                docstring_lines.append(line)

        return "\n".join(docstring_lines).strip()

    def _confirm_quit(self) -> bool:
        """Confirm that user wants to quit.

        Returns:
            True if user confirms quit, False otherwise
        """
        from rich.prompt import Confirm

        return Confirm.ask(
            "\n[bold yellow]Are you sure you want to quit? Remaining docstrings will be skipped.[/bold yellow]",
            default=False,
        )

    def _update_stats(self, action: ApprovalAction) -> None:
        """Update statistics based on action.

        Args:
            action: The action taken
        """
        if action == ApprovalAction.ACCEPT:
            self.stats.accepted += 1
        elif action == ApprovalAction.REJECT:
            self.stats.rejected += 1
        elif action == ApprovalAction.EDIT:
            self.stats.edited += 1
        elif action == ApprovalAction.QUIT:
            self.stats.skipped += 1

    def _percentage(self, value: int, total: int) -> str:
        """Calculate percentage as string.

        Args:
            value: Value to calculate percentage for
            total: Total value

        Returns:
            Percentage string with 1 decimal place
        """
        if total == 0:
            return "0.0"
        return f"{(value / total * 100):.1f}"
