"""Click CLI commands for docpilot.

This module implements the command-line interface using Click,
providing commands for generating, analyzing, and managing docstrings.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

import click
import structlog

from docpilot import __version__
from docpilot.cli.interactive import ApprovalAction, InteractiveApprover
from docpilot.cli.ui import DocpilotUI, get_ui
from docpilot.core.analyzer import CodeAnalyzer
from docpilot.core.generator import DocstringGenerator
from docpilot.core.models import DocstringStyle
from docpilot.llm.base import LLMProvider, create_provider
from docpilot.utils.config import (
    create_default_config,
    get_api_key,
    load_config,
)
from docpilot.utils.file_ops import FileOperations

logger = structlog.get_logger(__name__)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),  # type: ignore[type-var]
    help="Path to configuration file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode")
@click.pass_context
def cli(
    ctx: click.Context,
    config: Path | None,
    verbose: bool,
    quiet: bool,
) -> None:
    """docpilot - AI-powered docstring generator for Python.

    Generate comprehensive, formatted docstrings for your Python code
    using state-of-the-art LLMs.
    """
    # Setup logging based on verbose/quiet flags
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    logger.debug("logging_configured", level=logging.getLevelName(log_level))

    # Initialize UI
    ui = get_ui(verbose=verbose, quiet=quiet)

    # Store in context
    ctx.ensure_object(dict)
    ctx.obj["ui"] = ui
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@cli.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
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
@click.option("--interactive", "-i", is_flag=True, help="Review and approve each docstring before writing")
@click.pass_context
def generate(
    ctx: click.Context,
    paths: tuple[Path, ...],
    style: str,
    overwrite: bool,
    include_private: bool,
    provider: str | None,
    model: str | None,
    api_key: str | None,
    dry_run: bool,
    diff: bool,
    interactive: bool,
) -> None:
    """Generate docstrings for Python files.

    PATHS can be one or more files or directories. If a directory is provided,
    all Python files will be processed recursively. Supports shell glob patterns
    like *.py or src/**/*.py (when expanded by the shell).

    Examples:
        docpilot generate file.py
        docpilot generate file1.py file2.py file3.py
        docpilot generate src/
        docpilot generate *.py
    """
    ui: DocpilotUI = ctx.obj["ui"]
    config_path: Path | None = ctx.obj["config_path"]

    # Validate flag combinations
    if interactive and dry_run:
        ui.print_error("Cannot use --interactive with --dry-run")
        sys.exit(1)

    ui.print_banner()

    # Build overrides dict - only include values that were explicitly provided via CLI
    # Click's context stores which params were provided by the user
    overrides = {}

    # Always set style if provided (has a default value in Click)
    if style:
        overrides["style"] = DocstringStyle(style)

    # For boolean flags, check if they were explicitly set by checking Click's default
    # If the param was explicitly provided, it will be in ctx.params
    if ctx.get_parameter_source("overwrite") == click.core.ParameterSource.COMMANDLINE:
        overrides["overwrite"] = overwrite
    if ctx.get_parameter_source("include_private") == click.core.ParameterSource.COMMANDLINE:
        overrides["include_private"] = include_private

    # For optional arguments, only include if not None
    if provider:
        overrides["llm_provider"] = LLMProvider(provider)
    if model:
        overrides["llm_model"] = model
    if api_key:
        overrides["llm_api_key"] = api_key

    # Load configuration
    logger.debug("loading_configuration", config_path=str(config_path) if config_path else "default", overrides=list(overrides.keys()))
    config = load_config(config_path, **overrides)

    # Get API key from environment if not provided
    if not config.llm_api_key:
        logger.debug("fetching_api_key_from_env", provider=config.llm_provider.value)
        config.llm_api_key = get_api_key(config.llm_provider)

    if ctx.obj["verbose"]:
        ui.display_config(config.model_dump())
        logger.debug("config_displayed")

    # Find files from all provided paths
    ui.print_info(f"Scanning {len(paths)} path(s)...")

    file_ops = FileOperations(dry_run=dry_run)
    files: list[Path] = []

    for path in paths:
        if path.is_file():
            # Single file - add directly
            if path not in files:  # Avoid duplicates
                files.append(path)
        else:
            # Directory - find all Python files recursively
            found_files = file_ops.find_python_files(
                path,
                config.file_pattern,
                config.exclude_patterns,
            )
            # Add files, avoiding duplicates
            for f in found_files:
                if f not in files:
                    files.append(f)

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
        logger.info("initializing_generator", provider=config.llm_provider.value, model=config.llm_model)
        llm_config = config.to_llm_config()
        llm = create_provider(llm_config)
        generator = DocstringGenerator(llm_provider=llm)

        ui.print_success(
            f"Initialized {config.llm_provider.value} provider with model {config.llm_model}"
        )
        logger.info("generator_initialized_successfully")

    except Exception as e:
        logger.error("generator_initialization_failed", error=str(e))
        ui.print_error(f"Failed to initialize LLM provider: {e}")
        sys.exit(1)

    # Process files
    logger.info("starting_file_processing", total_files=len(files))
    start_time = time.time()
    total_generated = 0
    total_skipped = 0
    total_errors = 0

    with ui.create_progress() as progress:
        task = progress.add_task(
            "[cyan]Generating docstrings...",
            total=len(files),
        )

        for idx, file_path in enumerate(files, 1):
            try:
                logger.debug("processing_file_started", file=str(file_path), progress=f"{idx}/{len(files)}")
                progress.update(
                    task,
                    description=f"[cyan]Processing {file_path.name}...",
                )

                # Parse file first to get element info
                parse_result = generator.parser.parse_file(file_path)
                logger.debug("file_parsed", file=str(file_path), elements_found=len(parse_result.elements))

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
                logger.info("file_processed", file=str(file_path), docstrings_generated=len(generated))

                # Write docstrings to file
                for doc in generated:
                    try:
                        # Find element to get parent_class
                        # First check top-level elements
                        element = next(
                            (
                                e
                                for e in parse_result.elements
                                if e.name == doc.element_name
                            ),
                            None,
                        )

                        # If not found, check methods within classes
                        if element is None:
                            for class_element in parse_result.elements:
                                if hasattr(class_element, 'methods'):
                                    element = next(
                                        (
                                            m
                                            for m in class_element.methods
                                            if m.name == doc.element_name
                                        ),
                                        None,
                                    )
                                    if element:
                                        break

                        if element:
                            parent_class = element.parent_class
                            # Write to file
                            file_ops.insert_docstring(
                                file_path=file_path,
                                element_name=doc.element_name,
                                docstring=doc.docstring,
                                parent_class=parent_class,
                            )
                        else:
                            ui.print_warning(
                                f"Element {doc.element_name} not found in parse result"
                            )
                            total_errors += 1

                        if ctx.obj["verbose"]:
                            ui.display_generation_result(doc, show_content=diff)

                    except Exception as e:
                        ui.print_error(f"Failed to write {doc.element_name}: {e}")
                        logger.error(
                            "docstring_write_error",
                            file=str(file_path),
                            element=doc.element_name,
                            error=str(e),
                        )
                        total_errors += 1

                progress.advance(task)

            except Exception as e:
                ui.print_error(f"Error processing {file_path}: {e}")
                logger.error("file_processing_error", file=str(file_path), error=str(e))
                total_errors += 1
                progress.advance(task)

    duration = time.time() - start_time

    logger.info(
        "processing_complete",
        total_files=len(files),
        total_generated=total_generated,
        total_skipped=total_skipped,
        total_errors=total_errors,
        duration_seconds=round(duration, 2),
    )

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
        logger.info("dry_run_completed")

    sys.exit(0 if total_errors == 0 else 1)


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))  # type: ignore[type-var]
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
@click.argument("output", type=click.Path(path_type=Path), default="docpilot.toml")  # type: ignore[type-var]
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
    model: str | None,
    api_key: str | None,
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
        logger.debug("fetching_api_key_for_test", provider=provider)
        api_key = get_api_key(LLMProvider(provider))

    try:
        logger.info("testing_connection", provider=provider, model=model)
        from docpilot.llm.base import LLMConfig

        config = LLMConfig(
            provider=LLMProvider(provider),
            model=model,
            api_key=api_key,
        )

        llm = create_provider(config)

        # Test connection
        logger.debug("running_connection_test")
        result = asyncio.run(llm.test_connection())

        if result:
            logger.info("connection_test_passed", provider=provider, model=model)
            ui.print_success(f"Successfully connected to {provider} with model {model}")
        else:
            logger.error("connection_test_failed_no_result", provider=provider, model=model)
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

    ui.console.print(
        f"[bold cyan]docpilot[/bold cyan] version [green]{__version__}[/green]"
    )
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
    except SyntaxError as e:
        ui = get_ui()
        # Clean, user-friendly syntax error message
        file_info = f" in {e.filename}" if e.filename else ""
        line_info = f":{e.lineno}" if e.lineno else ""
        ui.print_error(f"Syntax error{file_info}{line_info}")
        if e.text and e.offset:
            # Show the problematic line with pointer
            ui.console.print(f"  {e.text.rstrip()}")
            ui.console.print(f"  {' ' * (e.offset - 1)}^")
        if e.msg:
            ui.console.print(f"  {e.msg}")
        # Only show full traceback in verbose mode
        if "--verbose" in sys.argv or "-v" in sys.argv or "--debug" in sys.argv:
            logger.exception("syntax_error")
        sys.exit(1)
    except Exception as e:
        ui = get_ui()
        ui.print_error(f"Unexpected error: {e}")
        # Only show full traceback in verbose mode
        if "--verbose" in sys.argv or "-v" in sys.argv or "--debug" in sys.argv:
            logger.exception("cli_error")
        sys.exit(1)


if __name__ == "__main__":
    main()
