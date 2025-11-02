"""Click CLI commands for docpilot.

This module implements the command-line interface using Click,
providing commands for generating, analyzing, and managing docstrings.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Optional

import click
import structlog

from docpilot import __version__
from docpilot.cli.ui import DocpilotUI, get_ui
from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.generator import DocstringGenerator
from docpilot.core.models import DocstringStyle
from docpilot.llm.base import LLMProvider, create_provider
from docpilot.utils.config import (
    DocpilotConfig,
    load_config,
    create_default_config,
    get_api_key,
)
from docpilot.utils.file_ops import FileOperations


logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Optional[Path],
    verbose: bool,
    quiet: bool,
) -> None:
    """docpilot - AI-powered docstring generator for Python.

    Generate comprehensive, formatted docstrings for your Python code
    using state-of-the-art LLMs.
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    # Initialize UI
    ui = get_ui(verbose=verbose, quiet=quiet)

    # Store in context
    ctx.ensure_object(dict)
    ctx.obj["ui"] = ui
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--style",
    type=click.Choice(["google", "numpy", "sphinx", "auto"], case_sensitive=False),
    default="google",
    help="Docstring style",
)
@click.option("--overwrite", is_flag=True, help="Overwrite existing docstrings")
@click.option("--include-private", is_flag=True, help="Include private elements")
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local", "mock"], case_sensitive=False),
    help="LLM provider",
)
@click.option("--model", help="LLM model name")
@click.option("--api-key", help="API key for LLM provider")
@click.option("--dry-run", is_flag=True, help="Show changes without applying them")
@click.option("--diff", is_flag=True, help="Show diffs of changes")
@click.pass_context
def generate(
    ctx: click.Context,
    path: Path,
    style: str,
    overwrite: bool,
    include_private: bool,
    provider: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    dry_run: bool,
    diff: bool,
) -> None:
    """Generate docstrings for Python files.

    PATH can be a file or directory. If a directory, all Python files
    will be processed recursively.
    """
    ui: DocpilotUI = ctx.obj["ui"]
    config_path: Optional[Path] = ctx.obj["config_path"]

    ui.print_banner()

    # Load configuration
    config = load_config(
        config_path,
        style=DocstringStyle(style),
        overwrite=overwrite,
        include_private=include_private,
        llm_provider=LLMProvider(provider) if provider else None,
        llm_model=model,
        llm_api_key=api_key,
    )

    # Get API key from environment if not provided
    if not config.llm_api_key:
        config.llm_api_key = get_api_key(config.llm_provider)

    if ctx.obj["verbose"]:
        ui.display_config(config.model_dump())

    # Find files
    ui.print_info(f"Scanning [cyan]{path}[/cyan]...")

    file_ops = FileOperations(dry_run=dry_run)

    if path.is_file():
        files = [path]
    else:
        files = file_ops.find_python_files(
            path,
            config.file_pattern,
            config.exclude_patterns,
        )

    if not files:
        ui.print_warning("No Python files found")
        sys.exit(0)

    ui.display_file_list(files)

    # Confirm if not dry run
    if not dry_run and not ui.prompt_confirm(
        f"Generate docstrings for {len(files)} file(s)?", default=True
    ):
        ui.print_info("Cancelled")
        sys.exit(0)

    # Initialize generator
    try:
        llm_config = config.to_llm_config()
        llm = create_provider(llm_config)
        generator = DocstringGenerator(llm_provider=llm)

        ui.print_success(
            f"Initialized {config.llm_provider.value} provider with model {config.llm_model}"
        )

    except Exception as e:
        ui.print_error(f"Failed to initialize LLM provider: {e}")
        sys.exit(1)

    # Process files
    start_time = time.time()
    total_generated = 0
    total_skipped = 0
    total_errors = 0

    with ui.create_progress() as progress:
        task = progress.add_task(
            f"[cyan]Generating docstrings...",
            total=len(files),
        )

        for file_path in files:
            try:
                progress.update(
                    task,
                    description=f"[cyan]Processing {file_path.name}...",
                )

                # Generate docstrings
                generated = asyncio.run(
                    generator.generate_for_file(
                        file_path,
                        style=config.style,
                        include_private=config.include_private,
                        overwrite_existing=config.overwrite,
                    )
                )

                total_generated += len(generated)

                # Show results
                for doc in generated:
                    if ctx.obj["verbose"]:
                        ui.display_generation_result(doc, show_content=diff)

                progress.advance(task)

            except Exception as e:
                ui.print_error(f"Error processing {file_path}: {e}")
                logger.error("file_processing_error", file=str(file_path), error=str(e))
                total_errors += 1
                progress.advance(task)

    duration = time.time() - start_time

    # Display statistics
    ui.display_statistics(
        total_files=len(files),
        total_elements=total_generated + total_skipped,
        generated_count=total_generated,
        skipped_count=total_skipped,
        error_count=total_errors,
        duration_seconds=duration,
    )

    if dry_run:
        ui.print_info("Dry run completed. No files were modified.")

    sys.exit(0 if total_errors == 0 else 1)


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--include-private", is_flag=True, help="Include private elements")
@click.option("--show-complexity", is_flag=True, help="Show complexity scores")
@click.option("--show-patterns", is_flag=True, help="Show detected patterns")
@click.pass_context
def analyze(
    ctx: click.Context,
    path: Path,
    include_private: bool,
    show_complexity: bool,
    show_patterns: bool,
) -> None:
    """Analyze Python code without generating docstrings.

    Displays code structure, complexity metrics, and detected patterns.
    """
    ui: DocpilotUI = ctx.obj["ui"]

    ui.print_info(f"Analyzing [cyan]{path}[/cyan]...")

    analyzer = CodeAnalyzer()

    if path.is_file():
        result = analyzer.analyze_file(path)
        ui.display_file_summary(result)
        ui.display_element_tree(result)

        if show_complexity or show_patterns:
            for element in result.elements:
                if not include_private and not element.is_public:
                    continue

                ui.print_info(f"\n[bold]{element.name}[/bold]")

                if show_complexity and element.complexity_score:
                    ui.print_info(f"  Complexity: {element.complexity_score}")

                if show_patterns and element.metadata.get("patterns"):
                    patterns = element.metadata["patterns"]
                    ui.print_info(f"  Patterns: {', '.join(patterns)}")

    else:
        results = analyzer.analyze_project(path)
        ui.print_success(f"Analyzed {len(results)} files")

        total_elements = sum(len(r.elements) for r in results)
        public_elements = sum(len(r.public_elements) for r in results)

        ui.print_info(f"Total elements: {total_elements}")
        ui.print_info(f"Public elements: {public_elements}")


@cli.command()
@click.argument("output", type=click.Path(path_type=Path), default="docpilot.toml")
def init(output: Path) -> None:
    """Initialize a new docpilot configuration file.

    Creates a default configuration file with common settings.
    """
    ui = get_ui()

    try:
        create_default_config(output)
        ui.print_success(f"Created configuration file: [cyan]{output}[/cyan]")
        ui.print_info("Edit the file to customize settings for your project")

    except FileExistsError:
        ui.print_error(f"Configuration file already exists: {output}")
        sys.exit(1)

    except Exception as e:
        ui.print_error(f"Failed to create configuration: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic", "local"], case_sensitive=False),
    required=True,
    help="LLM provider to test",
)
@click.option("--model", help="Model name")
@click.option("--api-key", help="API key")
@click.pass_context
def test_connection(
    ctx: click.Context,
    provider: str,
    model: Optional[str],
    api_key: Optional[str],
) -> None:
    """Test connection to an LLM provider.

    Verifies that API credentials are valid and the provider is accessible.
    """
    ui: DocpilotUI = ctx.obj["ui"]

    # Default models
    default_models = {
        "openai": "gpt-3.5-turbo",
        "anthropic": "claude-3-haiku-20240307",
        "local": "llama2",
    }

    model = model or default_models.get(provider, "")

    ui.print_info(f"Testing connection to [cyan]{provider}[/cyan]...")

    # Get API key from environment if not provided
    if not api_key:
        api_key = get_api_key(LLMProvider(provider))

    try:
        from docpilot.llm.base import LLMConfig

        config = LLMConfig(
            provider=LLMProvider(provider),
            model=model,
            api_key=api_key,
        )

        llm = create_provider(config)

        # Test connection
        result = asyncio.run(llm.test_connection())

        if result:
            ui.print_success(
                f"Successfully connected to {provider} with model {model}"
            )
        else:
            ui.print_error("Connection test failed")
            sys.exit(1)

    except Exception as e:
        ui.print_error(f"Connection test failed: {e}")
        logger.error("connection_test_failed", provider=provider, error=str(e))
        sys.exit(1)


@cli.command()
@click.pass_context
def version(ctx: click.Context) -> None:
    """Show version information."""
    ui: DocpilotUI = ctx.obj["ui"]

    ui.console.print(f"[bold cyan]docpilot[/bold cyan] version [green]{__version__}[/green]")
    ui.console.print("\nA production-grade AI-powered docstring generator for Python")
    ui.console.print("\nSupported styles: Google, NumPy, Sphinx")
    ui.console.print("Supported providers: OpenAI, Anthropic, Local (Ollama)")


def main() -> None:
    """Entry point for the CLI."""
    try:
        cli(obj={})
    except KeyboardInterrupt:
        ui = get_ui()
        ui.print_warning("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        ui = get_ui()
        ui.print_error(f"Unexpected error: {e}")
        logger.exception("cli_error")
        sys.exit(1)


if __name__ == "__main__":
    main()
