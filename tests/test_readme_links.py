from pathlib import Path


def test_readme_references_existing_local_docs_and_scripts():
    project_root = Path(__file__).resolve().parents[1]
    readme = (project_root / "README.md").read_text(encoding="utf-8")

    for doc_link in [
        "docs/功能大纲.md",
        "docs/大版本完善执行方案.md",
        "docs/移动端发布检查清单.md",
    ]:
        assert f"]({doc_link})" in readme
        assert (project_root / doc_link).exists()

    for stale_reference in [
        "docs/frontend-ui-optimization.md",
        "setup_dependencies.bat",
        "start.bat",
        "stop.bat",
        "status.bat",
        "logs.bat",
    ]:
        assert stale_reference not in readme


def test_readme_windows_bat_launchers_exist_and_delegate_to_dev_script():
    project_root = Path(__file__).resolve().parents[1]
    launcher_commands = {
        "安装依赖.bat": "install",
        "启动.bat": "start",
        "停止.bat": "stop",
        "状态.bat": "status",
        "日志.bat": "logs",
    }

    for filename, command in launcher_commands.items():
        launcher = project_root / filename
        assert launcher.exists()
        content = launcher.read_text(encoding="utf-8")
        assert "scripts\\dev.ps1" in content
        assert f"-Command {command}" in content
