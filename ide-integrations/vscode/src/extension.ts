/**
 * VSCode extension for docpilot
 *
 * Provides IDE integration for AI-powered docstring generation with features:
 * - Generate docstrings for functions, classes, and methods
 * - Real-time code analysis with pattern detection
 * - LSP integration for hover and completion support
 */

import * as vscode from 'vscode';
import * as path from 'path';
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
    TransportKind
} from 'vscode-languageclient/node';

let client: LanguageClient | undefined;

/**
 * Activate the extension
 */
export function activate(context: vscode.ExtensionContext) {
    console.log('docpilot extension is now active');

    // Register commands
    const generateDocstringCommand = vscode.commands.registerCommand(
        'docpilot.generateDocstring',
        generateDocstring
    );

    const generateAllDocstringsCommand = vscode.commands.registerCommand(
        'docpilot.generateAllDocstrings',
        generateAllDocstrings
    );

    const analyzeCodeCommand = vscode.commands.registerCommand(
        'docpilot.analyzeCode',
        analyzeCode
    );

    context.subscriptions.push(
        generateDocstringCommand,
        generateAllDocstringsCommand,
        analyzeCodeCommand
    );

    // Start LSP client if enabled
    const config = vscode.workspace.getConfiguration('docpilot');
    if (config.get('lsp.enabled')) {
        startLSPClient(context);
    }
}

/**
 * Start the LSP client for real-time features
 */
function startLSPClient(context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('docpilot');
    let docpilotPath = config.get<string>('lsp.path') || 'docpilot';

    // Server options - launch docpilot LSP server
    const serverOptions: ServerOptions = {
        command: docpilotPath,
        args: ['lsp'],
        transport: TransportKind.stdio
    };

    // Client options
    const clientOptions: LanguageClientOptions = {
        documentSelector: [{ scheme: 'file', language: 'python' }],
        synchronize: {
            fileEvents: vscode.workspace.createFileSystemWatcher('**/*.py')
        }
    };

    // Create the language client
    client = new LanguageClient(
        'docpilot',
        'docpilot LSP Server',
        serverOptions,
        clientOptions
    );

    // Start the client
    client.start().catch(err => {
        vscode.window.showErrorMessage(
            `Failed to start docpilot LSP server: ${err.message}`
        );
    });
}

/**
 * Generate docstring for the current function/class
 */
async function generateDocstring() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'python') {
        vscode.window.showErrorMessage('Please open a Python file');
        return;
    }

    const config = vscode.workspace.getConfiguration('docpilot');
    const style = config.get<string>('style') || 'google';
    const overwrite = config.get<boolean>('overwrite') || false;

    try {
        // Show progress
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Generating docstring...",
            cancellable: false
        }, async (progress) => {
            // Get current cursor position
            const position = editor.selection.active;
            const document = editor.document;

            // Execute docpilot command
            const terminal = vscode.window.createTerminal({
                name: 'docpilot',
                hideFromUser: true
            });

            const filePath = document.uri.fsPath;
            const args = [
                'generate',
                filePath,
                '--style', style
            ];

            if (overwrite) {
                args.push('--overwrite');
            }

            const command = `docpilot ${args.join(' ')}`;
            terminal.sendText(command);

            // Wait for completion (simplified - real implementation would monitor output)
            await new Promise(resolve => setTimeout(resolve, 2000));
            terminal.dispose();

            // Reload the file to show changes
            await vscode.commands.executeCommand('workbench.action.files.revert');

            vscode.window.showInformationMessage('Docstring generated successfully!');
        });
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to generate docstring: ${error}`);
    }
}

/**
 * Generate docstrings for all functions/classes in the file
 */
async function generateAllDocstrings() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'python') {
        vscode.window.showErrorMessage('Please open a Python file');
        return;
    }

    const config = vscode.workspace.getConfiguration('docpilot');
    const style = config.get<string>('style') || 'google';
    const overwrite = config.get<boolean>('overwrite') || false;
    const includePrivate = config.get<boolean>('includePrivate') || false;

    try {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Generating docstrings for entire file...",
            cancellable: false
        }, async (progress) => {
            const terminal = vscode.window.createTerminal({
                name: 'docpilot',
                hideFromUser: true
            });

            const filePath = editor.document.uri.fsPath;
            const args = [
                'generate',
                filePath,
                '--style', style
            ];

            if (overwrite) {
                args.push('--overwrite');
            }

            if (includePrivate) {
                args.push('--include-private');
            }

            const command = `docpilot ${args.join(' ')}`;
            terminal.sendText(command);

            await new Promise(resolve => setTimeout(resolve, 3000));
            terminal.dispose();

            await vscode.commands.executeCommand('workbench.action.files.revert');

            vscode.window.showInformationMessage('Docstrings generated for entire file!');
        });
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to generate docstrings: ${error}`);
    }
}

/**
 * Analyze code patterns in the current file
 */
async function analyzeCode() {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'python') {
        vscode.window.showErrorMessage('Please open a Python file');
        return;
    }

    try {
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "Analyzing code patterns...",
            cancellable: false
        }, async (progress) => {
            const terminal = vscode.window.createTerminal('docpilot-analyze');
            const filePath = editor.document.uri.fsPath;

            terminal.sendText(`docpilot analyze ${filePath} --show-patterns --show-complexity`);
            terminal.show();

            vscode.window.showInformationMessage('Code analysis started. Check terminal for results.');
        });
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to analyze code: ${error}`);
    }
}

/**
 * Deactivate the extension
 */
export function deactivate(): Thenable<void> | undefined {
    if (!client) {
        return undefined;
    }
    return client.stop();
}
