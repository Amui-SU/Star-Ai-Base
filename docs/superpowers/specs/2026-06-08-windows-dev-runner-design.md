# Windows Dev Runner Design

Date: 2026-06-08

## Goal

Provide a Windows-only local startup and shutdown workflow that is reliable for people who clone the project and want to run it without understanding the backend/frontend process details.

The runner should keep the current double-click experience, but move the actual logic into a maintainable PowerShell script. The design prioritizes predictable environment selection, clear diagnostics, precise process cleanup, and useful logs.

## Non-Goals

- No Windows Service, tray app, or installer in this phase.
- No macOS/Linux support in this phase.
- No production deployment workflow.
- No changes to backend or frontend runtime behavior beyond startup orchestration.

## Entry Points

The main implementation should live in:

- `scripts/dev.ps1`

The convenience wrappers should call that script:

- `安装依赖.bat` calls `scripts\dev.ps1 install`
- `启动.bat` calls `scripts\dev.ps1 start`
- `停止.bat` calls `scripts\dev.ps1 stop`
- `状态.bat` calls `scripts\dev.ps1 status`
- `日志.bat` calls `scripts\dev.ps1 logs`

The wrappers are optional thin launchers. They should contain as little logic as possible so future fixes happen in one place.

## Commands

`scripts/dev.ps1` should support:

- `doctor`: inspect the local environment and print actionable diagnostics.
- `install`: install backend and frontend dependencies into the same environment that `start` will use.
- `start`: start backend and frontend, wait for readiness, and open the browser after both are ready.
- `stop`: stop only this project's backend/frontend processes.
- `restart`: run `stop`, then `start`.
- `status`: show process, port, Python, Node, and log state.
- `logs`: show or tail backend/frontend logs.

## Python Selection

The runner should use the same Python selection order everywhere:

1. `<project>\.venv\Scripts\python.exe`
2. `<project>\venv\Scripts\python.exe`
3. `BILIBILI_RAG_PYTHON`
4. `C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe`
5. `python` from `PATH`

The selected Python must be runnable. For `start`, it must also pass a backend dependency health check.

The health check should verify more than `uvicorn` import. It should import key dependencies and run a passlib bcrypt hash:

```python
import fastapi, uvicorn, cryptography, jose
from passlib.context import CryptContext
CryptContext(schemes=["bcrypt"], deprecated="auto").hash("dependency-check")
```

This catches both missing `cryptography` and the `passlib`/`bcrypt` compatibility failure that can otherwise appear only during user registration.

## Install Behavior

`install` should:

- Resolve the same Python that `start` will use.
- Upgrade pip for that Python.
- Run `python -m pip install -r requirements.txt`.
- Run `npm install` in `frontend`.
- Print the resolved Python, Node, npm, and ffmpeg versions.

It should not install backend dependencies into a different Python than `start` uses.

## Doctor Behavior

`doctor` should check:

- Project root and frontend directory exist.
- Selected Python exists and runs.
- Backend dependency health check passes.
- Node and npm exist.
- `frontend\node_modules` exists.
- ffmpeg exists and is runnable.
- Ports `8000` and `3000` are free or owned by this project.
- Logs directory is writable.

The output should be concise and action oriented:

- `OK`: usable as-is.
- `WARN`: usable with limitation, for example missing ffmpeg.
- `FAIL`: startup would fail, with the exact command to fix.

## Start Behavior

`start` should:

1. Resolve project root.
2. Resolve Python.
3. Run the backend dependency health check.
4. Check Node/npm and frontend dependencies.
5. Ensure `logs` exists.
6. Stop stale project-owned processes if needed.
7. Start backend:
   - command: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
   - working directory: project root
   - log: `logs\backend-start.log`
   - environment: `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`
8. Start frontend:
   - command: `npm run dev`
   - working directory: `frontend`
   - log: `logs\frontend-start.log`
9. Wait until backend `8000` and frontend `3000` are listening.
10. Write runtime metadata to `logs\runtime.json`.
11. Open `http://localhost:3000` only after both services are ready.

If startup fails, show a short failure message and the last relevant log lines. Avoid forcing the user to inspect a long traceback first.

## Runtime Metadata

`logs\runtime.json` should include:

```json
{
  "backend": {
    "pid": 1234,
    "port": 8000,
    "command": "...",
    "started_at": "2026-06-08T00:00:00+08:00"
  },
  "frontend": {
    "pid": 5678,
    "port": 3000,
    "command": "...",
    "started_at": "2026-06-08T00:00:00+08:00"
  },
  "project_root": "C:\\Users\\...\\bilibili-rag-main",
  "python": "C:\\ProgramData\\anaconda3\\envs\\bilibili-rag\\python.exe"
}
```

The file is used for precise shutdown and status reporting. It is runtime state and should not be committed.

## Stop Behavior

`stop` should:

1. Read `logs\runtime.json` if present.
2. Stop the recorded backend and frontend PIDs only if their command line still points to this project.
3. If runtime metadata is missing or stale, find processes by command line and project root.
4. Avoid killing arbitrary processes solely because they use ports `8000` or `3000`.
5. Remove stale `runtime.json` after shutdown.

This prevents accidental termination of other local projects.

## Status Behavior

`status` should display:

- Backend running: yes/no
- Frontend running: yes/no
- Backend PID and port
- Frontend PID and port
- Selected Python path
- Node/npm versions
- Log file paths
- Whether ports `8000` and `3000` are occupied by this project or something else

## Logs Behavior

`logs` should support a simple default view:

- show paths for backend and frontend logs
- print the last 80 lines of each log

An optional later enhancement can add `-Follow` to tail logs live.

## Error Handling

Common failures should map to specific messages:

- Missing Python: run installer or set `BILIBILI_RAG_PYTHON`.
- Missing backend dependency: run `scripts\dev.ps1 install`.
- `passlib`/`bcrypt` failure: run `scripts\dev.ps1 install`; verify `bcrypt==4.0.1`.
- Port conflict: run `scripts\dev.ps1 status`; stop the conflicting process only if it belongs to this project.
- Frontend dependencies missing: run `scripts\dev.ps1 install`.
- Startup timeout: show last backend/frontend log lines.

## Testing

Implementation should verify:

- `doctor` reports the selected Python and dependency state.
- `install -SkipFrontend` or an equivalent test mode can install backend dependencies without starting services.
- `start` can launch backend and frontend, then detect readiness.
- `stop` stops only project-owned processes.
- `status` reports useful state before start, after start, and after stop.
- Existing backend tests still pass.
- Frontend lint still has zero errors.

## Migration Plan

1. Add `scripts/dev.ps1` while leaving current VBS/BAT files usable.
2. Add thin BAT wrappers for install/start/stop/status/logs.
3. Update README startup docs to make `scripts/dev.ps1` the canonical path.
4. Keep old VBS files as compatibility launchers or replace their internals with calls to `scripts/dev.ps1`.
5. After a few successful local runs, remove duplicated logic from old scripts.

## Wrapper Decision

The first implementation should prefer BAT wrappers over VBS wrappers unless silent no-console startup is required. BAT wrappers are simpler to inspect and debug. If silent startup remains important, the VBS wrapper should only call PowerShell and should not contain environment or process-management logic.
