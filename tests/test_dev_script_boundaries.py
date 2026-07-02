from pathlib import Path


def _dev_script() -> str:
    project_root = Path(__file__).resolve().parents[1]
    return (project_root / "scripts" / "dev.ps1").read_text(encoding="utf-8")


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
