from pathlib import Path
import subprocess


def _dev_script() -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "scripts" / "dev.ps1").read_text(encoding="utf-8")


def _dot_source_dev_script(command: str) -> subprocess.CompletedProcess[str]:
    project_root = Path(__file__).resolve().parents[1]
    script_path = project_root / "scripts" / "dev.ps1"
    escaped_path = str(script_path).replace("'", "''")
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f". '{escaped_path}'; {command}",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _function_block(source: str, name: str) -> str:
    marker = f"function {name} "
    start = source.index(marker)
    next_start = source.find("\nfunction ", start + len(marker))
    if next_start == -1:
        return source[start:]
    return source[start:next_start]


def test_start_cleans_project_processes_before_rejecting_busy_ports():
    source = _dev_script()
    start_block = _function_block(source, "Invoke-Start")

    cleanup_index = start_block.index("Invoke-Stop -ProjectRoot $ProjectRoot -Quiet")
    port_check_index = start_block.index("foreach ($port in @(8000, 3000))")

    assert cleanup_index < port_check_index


def test_dev_script_can_be_dot_sourced_without_dispatching_a_command():
    result = _dot_source_dev_script("Write-Output 'DOT_SOURCE_OK'")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "DOT_SOURCE_OK"


def test_python_candidates_keep_required_precedence_without_resolving_names_early():
    source = _dev_script()
    candidates_block = _function_block(source, "Get-ProjectPythonCandidates")

    ordered_markers = [
        'Join-Path $ProjectRoot ".venv\\Scripts\\python.exe"',
        'Join-Path $ProjectRoot "venv\\Scripts\\python.exe"',
        '@("Process", "User", "Machine")',
        '"C:\\ProgramData\\anaconda3\\envs\\bilibili-rag\\python.exe"',
        '$candidates += "python"',
    ]
    indexes = [candidates_block.index(marker) for marker in ordered_markers]

    assert indexes == sorted(indexes)
    assert "OrdinalIgnoreCase" in candidates_block
    assert "Resolve-Path" not in candidates_block


def test_backend_application_import_runs_from_project_root_and_restores_location():
    source = _dev_script()
    import_block = _function_block(source, "Test-BackendApplicationImport")

    assert "Push-Location -LiteralPath $ProjectRoot" in import_block
    assert '& $PythonExe -c "import app.main"' in import_block
    assert "finally" in import_block
    assert "Pop-Location" in import_block


def test_commands_choose_python_with_the_expected_health_policy():
    source = _dev_script()
    doctor_block = _function_block(source, "Invoke-Doctor")
    install_block = _function_block(source, "Invoke-Install")
    start_block = _function_block(source, "Invoke-Start")

    assert "-RequireBackendDependencies" in doctor_block
    assert "-RequireBackendDependencies" in start_block
    assert "-RequireBackendDependencies" not in install_block
    assert "Test-BackendDependencies" not in doctor_block
    assert "Test-BackendDependencies" not in start_block
    assert "Write-RejectedPythonCandidates" in doctor_block
    assert "Write-RejectedPythonCandidates" in start_block


def test_project_process_detection_checks_command_line_and_executable_directory():
    source = _dev_script()

    assert "function Get-ProcessExecutableDirectory" in source
    assert "Get-ProcessExecutableDirectory -ProcessId $ProcessId" in source

    project_process_block = _function_block(source, "Test-ProjectProcess")
    command_line_index = project_process_block.index(
        "Get-ProcessCommandLine -ProcessId $ProcessId"
    )
    executable_directory_index = project_process_block.index(
        "Get-ProcessExecutableDirectory -ProcessId $ProcessId"
    )

    assert command_line_index < executable_directory_index


def test_stop_checks_project_owned_dev_port_listeners():
    source = _dev_script()

    assert "function Get-ListeningProcessIds" in source
    assert "function Stop-ProjectPortListeners" in source

    stop_block = _function_block(source, "Invoke-Stop")
    assert "Stop-ProjectPortListeners -ProjectRoot $ProjectRoot" in stop_block

    port_listener_block = _function_block(source, "Stop-ProjectPortListeners")
    assert "8000" in port_listener_block
    assert "3000" in port_listener_block
    assert (
        "Test-ProjectPortProcess -ProcessId $processId -ProjectRoot $ProjectRoot -Port $port"
        in port_listener_block
    )

    port_process_block = _function_block(source, "Test-ProjectPortProcess")
    assert "$Port -eq 8000" in port_process_block
    assert "$Port -eq 3000" in port_process_block
