param(
    [ValidateSet("doctor", "install", "start", "stop", "restart", "status", "logs")]
    [string]$Command = "doctor",
    [switch]$SkipFrontend,
    [switch]$NoBrowser,
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

function Write-Info($Message) { Write-Host "[INFO] $Message" -ForegroundColor Cyan }
function Write-Ok($Message) { Write-Host "[OK]   $Message" -ForegroundColor Green }
function Write-WarnMsg($Message) { Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Fail($Message) { Write-Host "[FAIL] $Message" -ForegroundColor Red }

function Get-ProjectRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Get-FrontendPath {
    param([string]$ProjectRoot)
    return Join-Path $ProjectRoot "frontend"
}

function Get-LogsPath {
    param([string]$ProjectRoot)
    return Join-Path $ProjectRoot "logs"
}

function Get-RuntimePath {
    param([string]$ProjectRoot)
    return Join-Path (Get-LogsPath $ProjectRoot) "runtime.json"
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        [System.IO.Directory]::CreateDirectory($Path) | Out-Null
    }
}

function Test-CommandExists {
    param([string]$CommandName)
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-PythonRunnable {
    param([string]$PythonExe)

    try {
        & $PythonExe --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Get-ProjectPythonCandidates {
    param([string]$ProjectRoot)

    $candidates = @(
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot "venv\Scripts\python.exe")
    )

    foreach ($target in @("Process", "User", "Machine")) {
        $envPython = [Environment]::GetEnvironmentVariable("BILIBILI_RAG_PYTHON", $target)
        if ($envPython) {
            $candidates += $envPython
        }
    }

    $candidates += "C:\ProgramData\anaconda3\envs\bilibili-rag\python.exe"
    $candidates += "python"

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($candidate in $candidates) {
        if ($candidate -and $seen.Add($candidate)) {
            $candidate
        }
    }
}

function Test-BackendApplicationImport {
    param(
        [string]$PythonExe,
        [string]$ProjectRoot
    )

    Push-Location -LiteralPath $ProjectRoot
    try {
        & $PythonExe -c "import app.main" *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
    finally {
        Pop-Location
    }
}

function Resolve-ProjectPython {
    param(
        [string]$ProjectRoot,
        [switch]$RequireBackendDependencies,
        [ref]$RejectedCandidates
    )

    if ($RejectedCandidates) {
        $RejectedCandidates.Value = @()
    }

    foreach ($candidate in @(Get-ProjectPythonCandidates -ProjectRoot $ProjectRoot)) {
        if (-not (Test-PythonRunnable -PythonExe $candidate)) {
            continue
        }
        if ($RequireBackendDependencies -and -not (Test-BackendApplicationImport -PythonExe $candidate -ProjectRoot $ProjectRoot)) {
            if ($RejectedCandidates) {
                $RejectedCandidates.Value += [pscustomobject]@{
                    candidate = $candidate
                    reason = "cannot import app.main"
                }
            }
            continue
        }
        return $candidate
    }

    return $null
}

function Test-BackendDependencies {
    param(
        [string]$PythonExe,
        [string]$ProjectRoot = (Get-ProjectRoot)
    )

    return Test-BackendApplicationImport -PythonExe $PythonExe -ProjectRoot $ProjectRoot
}

function Write-RejectedPythonCandidates {
    param([object[]]$Candidates)

    foreach ($entry in @($Candidates)) {
        Write-WarnMsg "Rejected Python candidate: $($entry.candidate) ($($entry.reason))"
    }
}

function Test-FfmpegRunnable {
    try {
        if (-not (Test-CommandExists "ffmpeg")) {
            return $false
        }

        ffmpeg -version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)

    try {
        $result = netstat -ano | Select-String ":$Port\s+.*LISTENING"
        return [bool]$result
    }
    catch {
        return $false
    }
}

function Resolve-WindowsHttpProxy {
    try {
        $settings = Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -ErrorAction SilentlyContinue
        if (-not $settings -or [int]$settings.ProxyEnable -ne 1 -or -not $settings.ProxyServer) {
            return $null
        }

        $rawProxy = "" + $settings.ProxyServer
        $candidate = $rawProxy
        foreach ($part in ($rawProxy -split ";")) {
            $trimmed = $part.Trim()
            if ($trimmed -match "^(?:https?|socks)=([^;]+)$") {
                $candidate = $Matches[1]
                break
            }
        }
        if ($candidate -notmatch "^[a-zA-Z][a-zA-Z0-9+.-]*://") {
            $candidate = "http://$candidate"
        }
        return $candidate
    }
    catch {
        return $null
    }
}

function Ensure-HttpProxyEnvironment {
    $proxy = Resolve-WindowsHttpProxy
    if (-not $proxy) {
        return
    }

    foreach ($name in @("HTTP_PROXY", "HTTPS_PROXY")) {
        if (-not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $proxy, "Process")
        }
    }
    foreach ($name in @("NO_PROXY", "no_proxy")) {
        $current = [Environment]::GetEnvironmentVariable($name, "Process")
        if (-not $current) {
            [Environment]::SetEnvironmentVariable($name, "localhost,127.0.0.1,::1", "Process")
        }
        elseif ($current -notmatch "(^|,)127\.0\.0\.1(,|$)") {
            [Environment]::SetEnvironmentVariable(
                $name,
                "$current,localhost,127.0.0.1,::1",
                "Process"
            )
        }
    }
}

function Get-LanIPv4Address {
    try {
        $lines = ipconfig | Select-String "IPv4"
        foreach ($line in $lines) {
            $text = "" + $line
            $match = [regex]::Match($text, "(\d{1,3}(?:\.\d{1,3}){3})")
            if ($match.Success) {
                $ip = $match.Groups[1].Value
                if ($ip -like "192.168.*" -or $ip -like "10.*" -or $ip -match "^172\.(1[6-9]|2\d|3[0-1])\.") {
                    return $ip
                }
            }
        }
    }
    catch {
        return $null
    }

    return $null
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
    if ($proc) {
        return "" + $proc.CommandLine
    }

    return ""
}

function Get-ProcessExecutableDirectory {
    param([int]$ProcessId)

    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcessId" -ErrorAction SilentlyContinue
        if ($process -and $process.ExecutablePath) {
            return "" + (Split-Path -Parent $process.ExecutablePath)
        }
    }
    catch {
        return ""
    }

    return ""
}

function Test-PathWithinProject {
    param(
        [string]$Path,
        [string]$ProjectRoot
    )

    if (-not $Path) {
        return $false
    }

    $normalizedRoot = Resolve-Path -LiteralPath $ProjectRoot -ErrorAction SilentlyContinue
    if ($normalizedRoot) {
        $root = $normalizedRoot.Path.TrimEnd("\", "/").ToLowerInvariant()
    }
    else {
        $root = $ProjectRoot.TrimEnd("\", "/").ToLowerInvariant()
    }

    $candidate = $Path.TrimEnd("\", "/").ToLowerInvariant()
    return $candidate -eq $root -or $candidate.StartsWith("$root\")
}

function Test-ProjectCommandLine {
    param(
        [string]$CommandLine,
        [string]$ProjectRoot
    )

    if (-not $CommandLine) {
        return $false
    }

    $commandLine = $CommandLine.ToLowerInvariant()
    $normalizedRoot = Resolve-Path -LiteralPath $ProjectRoot -ErrorAction SilentlyContinue
    if ($normalizedRoot) {
        $root = $normalizedRoot.Path.ToLowerInvariant()
    }
    else {
        $root = $ProjectRoot.ToLowerInvariant()
    }

    $startIndex = 0
    while ($true) {
        $index = $commandLine.IndexOf($root, $startIndex, [System.StringComparison]::OrdinalIgnoreCase)
        if ($index -lt 0) {
            return $false
        }

        $beforeIsBoundary = $index -eq 0
        if (-not $beforeIsBoundary) {
            $before = $commandLine[$index - 1]
            $beforeIsBoundary = $before -eq '"' -or $before -eq "'" -or [char]::IsWhiteSpace($before)
        }

        $afterIndex = $index + $root.Length
        if ($beforeIsBoundary -and $afterIndex -ge $commandLine.Length) {
            return $true
        }

        $after = $commandLine[$afterIndex]
        if ($beforeIsBoundary -and ($after -eq "\" -or $after -eq "/" -or $after -eq '"' -or $after -eq "'" -or [char]::IsWhiteSpace($after))) {
            return $true
        }

        $startIndex = $index + 1
    }
}

function Test-ProjectProcess {
    param(
        [int]$ProcessId,
        [string]$ProjectRoot
    )

    $commandLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (Test-ProjectCommandLine -CommandLine $commandLine -ProjectRoot $ProjectRoot) {
        return $true
    }

    $executableDirectory = Get-ProcessExecutableDirectory -ProcessId $ProcessId
    return Test-PathWithinProject -Path $executableDirectory -ProjectRoot $ProjectRoot
}

function Test-ProjectPortProcess {
    param(
        [int]$ProcessId,
        [string]$ProjectRoot,
        [int]$Port
    )

    $commandLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (Test-ProjectProcess -ProcessId $ProcessId -ProjectRoot $ProjectRoot) {
        return $true
    }

    $frontendPath = Get-FrontendPath $ProjectRoot
    $lower = $commandLine.ToLowerInvariant()
    if ($Port -eq 8000 -and $lower.Contains("uvicorn") -and $lower.Contains("app.main:app")) {
        return $true
    }
    if ($Port -eq 3000 -and (
            $lower.Contains("npm run dev") -or
            $lower.Contains("next dev") -or
            ($lower.Contains("next") -and $lower.Contains(" dev"))
        )) {
        return $true
    }

    $executableDirectory = Get-ProcessExecutableDirectory -ProcessId $ProcessId
    return (Test-PathWithinProject -Path $executableDirectory -ProjectRoot $ProjectRoot) -or (Test-PathWithinProject -Path $executableDirectory -ProjectRoot $frontendPath)
}

function Get-ListeningProcessIds {
    param([int]$Port)

    $ids = @()
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            if ($connection.OwningProcess) {
                $ids += [int]$connection.OwningProcess
            }
        }
    }
    catch {
        $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
        foreach ($line in $lines) {
            $parts = ("" + $line).Trim() -split "\s+"
            $ids += [int]$parts[-1]
        }
    }

    return @($ids | Select-Object -Unique)
}

function Stop-ProjectPortListeners {
    param(
        [string]$ProjectRoot,
        [switch]$Quiet
    )

    foreach ($port in @(8000, 3000)) {
        foreach ($processId in (Get-ListeningProcessIds -Port $port)) {
            if (Test-ProjectPortProcess -ProcessId $processId -ProjectRoot $ProjectRoot -Port $port) {
                Stop-ProjectPid -ProcessId $processId -ProjectRoot $ProjectRoot -Quiet:$Quiet -AllowPortMatch
            }
            elseif (-not $Quiet) {
                Write-WarnMsg "Port $port is used by PID $processId, but it is not recognized as this project."
            }
        }
    }
}

function Save-RuntimeState {
    param(
        [string]$ProjectRoot,
        [System.Diagnostics.Process]$BackendProcess,
        [System.Diagnostics.Process]$FrontendProcess,
        [string]$PythonExe
    )

    $startedAt = (Get-Date).ToString("o")
    $frontendPath = Get-FrontendPath $ProjectRoot
    $quotedProjectRoot = '"' + ($ProjectRoot -replace '"', '\"') + '"'
    $runtime = [ordered]@{
        project_root = $ProjectRoot
        python = $PythonExe
        backend = [ordered]@{
            pid = $BackendProcess.Id
            port = 8000
            command = "python -m uvicorn app.main:app --app-dir $quotedProjectRoot --host 0.0.0.0 --port 8000"
            started_at = $startedAt
        }
        frontend = [ordered]@{
            pid = $FrontendProcess.Id
            port = 3000
            command = "cd /d `"$frontendPath`" && npm run dev"
            started_at = $startedAt
        }
    }

    $runtimePath = Get-RuntimePath $ProjectRoot
    Ensure-Directory ([System.IO.Path]::GetDirectoryName($runtimePath))
    $runtime | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $runtimePath -Encoding UTF8
}

function Read-RuntimeState {
    param([string]$ProjectRoot)

    $runtimePath = Get-RuntimePath $ProjectRoot
    if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
        return $null
    }

    return Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
}

function Remove-RuntimeState {
    param([string]$ProjectRoot)

    $runtimePath = Get-RuntimePath $ProjectRoot
    Remove-Item -LiteralPath $runtimePath -Force -ErrorAction SilentlyContinue
}

function Wait-Port {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-PortListening $Port) {
            return $true
        }

        Start-Sleep -Seconds 1
    }

    return $false
}

function Show-LogTail {
    param(
        [string]$Path,
        [int]$Tail = 40
    )

    if (Test-Path -LiteralPath $Path -PathType Leaf) {
        Write-Info "Last $Tail lines: $Path"
        Get-Content -LiteralPath $Path -Tail $Tail
    }
    else {
        Write-WarnMsg "Log file does not exist: $Path"
    }
}

function Invoke-Doctor {
    param([string]$ProjectRoot)

    $failed = $false
    $frontendPath = Get-FrontendPath $ProjectRoot
    $logsPath = Get-LogsPath $ProjectRoot
    $rejectedCandidates = @()
    $pythonExe = Resolve-ProjectPython -ProjectRoot $ProjectRoot -RequireBackendDependencies -RejectedCandidates ([ref]$rejectedCandidates)
    Write-RejectedPythonCandidates -Candidates $rejectedCandidates

    Write-Info "Project root: $ProjectRoot"

    if (Test-Path -LiteralPath $ProjectRoot -PathType Container) {
        Write-Ok "Project root exists."
    }
    else {
        $failed = $true
        Write-Fail "Project root missing."
        throw "doctor found failed checks."
    }

    if (Test-Path -LiteralPath $frontendPath -PathType Container) {
        Write-Ok "Frontend directory exists."
    }
    else {
        $failed = $true
        Write-Fail "Frontend directory missing: $frontendPath"
    }

    if ($pythonExe) {
        $pythonVersion = & $pythonExe --version 2>&1
        Write-Ok "Python: $pythonVersion ($pythonExe)"
        Write-Ok "Backend application import is healthy."
    }
    else {
        $failed = $true
        Write-Fail "No healthy Python can import app.main. Run scripts\dev.ps1 install or set BILIBILI_RAG_PYTHON to a healthy environment."
    }

    if (Test-CommandExists "node") {
        Write-Ok "Node.js: $(node --version)"
    }
    else {
        $failed = $true
        Write-Fail "Node.js is missing."
    }

    if (Test-CommandExists "npm") {
        Write-Ok "npm: $(npm --version)"
    }
    else {
        $failed = $true
        Write-Fail "npm is missing."
    }

    if (Test-Path -LiteralPath (Join-Path $frontendPath "node_modules") -PathType Container) {
        Write-Ok "Frontend dependencies are installed."
    }
    else {
        Write-WarnMsg "frontend\node_modules is missing. Run install before start."
    }

    if (Test-FfmpegRunnable) {
        Write-Ok "ffmpeg is available."
    }
    else {
        Write-WarnMsg "ffmpeg is missing. ASR local fallback may not work."
    }

    try {
        Ensure-Directory $logsPath
        $probePath = Join-Path $logsPath ".doctor-write-test"
        Set-Content -LiteralPath $probePath -Value "ok" -Encoding ASCII
        Remove-Item -LiteralPath $probePath -Force -ErrorAction SilentlyContinue
        Write-Ok "Logs directory is writable: $logsPath"
    }
    catch {
        $failed = $true
        Write-Fail "Logs directory is not writable: $logsPath"
    }

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            Write-WarnMsg "Port $port is already listening. Run status to inspect ownership."
        }
        else {
            Write-Ok "Port $port is free."
        }
    }

    if ($failed) {
        throw "doctor found failed checks."
    }
}

function Invoke-Install {
    param(
        [string]$ProjectRoot,
        [switch]$SkipFrontend
    )

    $frontendPath = Get-FrontendPath $ProjectRoot
    $requirementsPath = Join-Path $ProjectRoot "requirements.txt"
    $pythonExe = Resolve-ProjectPython $ProjectRoot

    if (-not $pythonExe) {
        throw "No runnable Python found. Install Python or set BILIBILI_RAG_PYTHON."
    }
    if (-not (Test-Path -LiteralPath $requirementsPath -PathType Leaf)) {
        throw "Missing requirements file: $requirementsPath"
    }
    if (-not (Test-Path -LiteralPath $frontendPath -PathType Container)) {
        throw "Missing frontend directory: $frontendPath"
    }

    Write-Ok "Using Python: $(& $pythonExe --version 2>&1) ($pythonExe)"
    Write-Info "Upgrading pip..."
    & $pythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "pip upgrade failed."
    }

    Write-Info "Installing backend dependencies..."
    & $pythonExe -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        throw "Backend dependency installation failed."
    }

    if (-not $SkipFrontend) {
        if (-not (Test-CommandExists "npm")) {
            throw "npm is missing. Install Node.js LTS."
        }

        Write-Info "Installing frontend dependencies..."
        Push-Location -LiteralPath $frontendPath
        try {
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency installation failed."
            }
        }
        finally {
            Pop-Location
        }
    }

    Write-Ok "Dependency installation completed."
}

function Invoke-Start {
    param(
        [string]$ProjectRoot,
        [switch]$NoBrowser
    )

    $frontendPath = Get-FrontendPath $ProjectRoot
    $logsPath = Get-LogsPath $ProjectRoot
    $backendLog = Join-Path $logsPath "backend-start.log"
    $backendErrLog = Join-Path $logsPath "backend-start.err.log"
    $frontendLog = Join-Path $logsPath "frontend-start.log"
    $frontendErrLog = Join-Path $logsPath "frontend-start.err.log"
    $rejectedCandidates = @()
    $pythonExe = Resolve-ProjectPython -ProjectRoot $ProjectRoot -RequireBackendDependencies -RejectedCandidates ([ref]$rejectedCandidates)
    Write-RejectedPythonCandidates -Candidates $rejectedCandidates
    $quotedProjectRoot = '"' + ($ProjectRoot -replace '"', '\"') + '"'
    $backendProcess = $null
    $frontendProcess = $null

    if (-not $pythonExe) {
        throw "No healthy Python can import app.main. Run scripts\dev.ps1 install or set BILIBILI_RAG_PYTHON to a healthy environment."
    }
    if (-not (Test-CommandExists "npm")) {
        throw "npm is missing. Install Node.js LTS."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendPath "node_modules") -PathType Container)) {
        throw "Frontend dependencies are missing. Run scripts\dev.ps1 install."
    }
    Ensure-Directory $logsPath
    Invoke-Stop -ProjectRoot $ProjectRoot -Quiet

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            throw "Port $port is already listening. Stop the existing service before running start."
        }
    }

    Remove-Item -LiteralPath $backendLog, $backendErrLog, $frontendLog, $frontendErrLog -Force -ErrorAction SilentlyContinue

    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")
    Ensure-HttpProxyEnvironment

    try {
        Write-Info "Starting backend..."
        $backendProcess = Start-Process -FilePath $pythonExe `
            -ArgumentList @("-m", "uvicorn", "app.main:app", "--app-dir", $quotedProjectRoot, "--host", "0.0.0.0", "--port", "8000") `
            -WorkingDirectory $ProjectRoot `
            -RedirectStandardOutput $backendLog `
            -RedirectStandardError $backendErrLog `
            -WindowStyle Hidden `
            -PassThru

        Write-Info "Starting frontend..."
        $frontendCommand = "cd /d `"$frontendPath`" && npm run dev"
        $frontendProcess = Start-Process -FilePath "cmd.exe" `
            -ArgumentList @("/d", "/c", $frontendCommand) `
            -WorkingDirectory $frontendPath `
            -RedirectStandardOutput $frontendLog `
            -RedirectStandardError $frontendErrLog `
            -WindowStyle Hidden `
            -PassThru

        if (-not (Wait-Port -Port 8000 -TimeoutSeconds 60)) {
            Show-LogTail $backendLog
            Show-LogTail $backendErrLog
            throw "Backend did not become ready on port 8000."
        }

        if (-not (Wait-Port -Port 3000 -TimeoutSeconds 60)) {
            Show-LogTail $frontendLog
            Show-LogTail $frontendErrLog
            throw "Frontend did not become ready on port 3000."
        }

        Save-RuntimeState -ProjectRoot $ProjectRoot -BackendProcess $backendProcess -FrontendProcess $frontendProcess -PythonExe $pythonExe
        $lanIp = Get-LanIPv4Address
        Write-Ok "Backend ready: http://127.0.0.1:8000 (LAN: http://<电脑IP>:8000)"
        Write-Ok "Frontend ready: http://localhost:3000"
        if ($lanIp) {
            Write-Ok "Mobile local connection address: http://$lanIp:8000"
            Write-Ok "Mobile browser preview: http://$lanIp:3000"
            Write-Ok "Mobile QR connect page: http://$lanIp:8000/local-connection/mobile-connect?api=http%3A%2F%2F$lanIp%3A8000"
        }

        if (-not $NoBrowser) {
            Start-Process "http://localhost:3000"
        }
    }
    catch {
        foreach ($process in @($backendProcess, $frontendProcess)) {
            if ($process -and -not $process.HasExited) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }

        Get-CimInstance Win32_Process | Where-Object {
            $_.Name -in @("python.exe", "node.exe", "cmd.exe")
        } | ForEach-Object {
            if (Test-ProjectProcess -ProcessId ([int]$_.ProcessId) -ProjectRoot $ProjectRoot) {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
            }
        }

        throw
    }
}

function Stop-ProjectPid {
    param(
        [int]$ProcessId,
        [string]$ProjectRoot,
        [switch]$Quiet,
        [switch]$AllowPortMatch
    )

    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        return
    }

    if (-not $AllowPortMatch -and -not (Test-ProjectProcess -ProcessId $ProcessId -ProjectRoot $ProjectRoot)) {
        if (-not $Quiet) {
            Write-WarnMsg "Refusing to stop PID $ProcessId because it is not owned by this project."
        }
        return
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    if (-not $Quiet) {
        Write-Ok "Stopped PID $ProcessId."
    }
}

function Invoke-Stop {
    param(
        [string]$ProjectRoot,
        [switch]$Quiet
    )

    $runtime = Read-RuntimeState $ProjectRoot
    if ($runtime) {
        if ($runtime.backend -and $runtime.backend.pid) {
            Stop-ProjectPid -ProcessId ([int]$runtime.backend.pid) -ProjectRoot $ProjectRoot -Quiet:$Quiet
        }
        if ($runtime.frontend -and $runtime.frontend.pid) {
            Stop-ProjectPid -ProcessId ([int]$runtime.frontend.pid) -ProjectRoot $ProjectRoot -Quiet:$Quiet
        }

        Remove-RuntimeState $ProjectRoot
    }

    Stop-ProjectPortListeners -ProjectRoot $ProjectRoot -Quiet:$Quiet

    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -in @("python.exe", "node.exe", "cmd.exe")
    } | ForEach-Object {
        $processId = [int]$_.ProcessId
        if (Test-ProjectProcess -ProcessId $processId -ProjectRoot $ProjectRoot) {
            Stop-ProjectPid -ProcessId $processId -ProjectRoot $ProjectRoot -Quiet:$Quiet
        }
    }

    if (-not $Quiet) {
        Write-Ok "Project processes stopped."
    }
}

function Invoke-Status {
    param([string]$ProjectRoot)

    $runtime = Read-RuntimeState $ProjectRoot
    $pythonExe = $null
    $pythonRunnable = $false
    $usingRecordedPython = [bool]($runtime -and $runtime.python)
    if ($usingRecordedPython) {
        $pythonExe = $runtime.python
        $pythonRunnable = Test-PythonRunnable -PythonExe $pythonExe
    }
    else {
        $pythonExe = Resolve-ProjectPython -ProjectRoot $ProjectRoot -RequireBackendDependencies
        if ($pythonExe) {
            $pythonRunnable = $true
        }
    }

    Write-Info "Project root: $ProjectRoot"

    if ($usingRecordedPython -and -not $pythonRunnable) {
        Write-WarnMsg "Python: unavailable (recorded: $pythonExe)"
    }
    elseif ($pythonExe) {
        Write-Ok "Python: $(& $pythonExe --version 2>&1) ($pythonExe)"
    }
    else {
        Write-WarnMsg "Python: not found"
    }

    if (Test-CommandExists "node") {
        Write-Ok "Node.js: $(node --version)"
    }
    else {
        Write-WarnMsg "Node.js: not found"
    }

    if ($runtime) {
        Write-Info "Runtime metadata: $(Get-RuntimePath $ProjectRoot)"
        foreach ($name in @("backend", "frontend")) {
            $entry = $runtime.$name
            if ($entry -and $entry.pid) {
                $processId = [int]$entry.pid
                $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if ($proc -and (Test-ProjectProcess -ProcessId $processId -ProjectRoot $ProjectRoot)) {
                    Write-Ok "$name running: PID $processId, port $($entry.port)"
                }
                else {
                    Write-WarnMsg "$name metadata is stale: PID $processId"
                }
            }
        }
    }
    else {
        Write-WarnMsg "No runtime metadata found."
    }

    foreach ($port in @(8000, 3000)) {
        if (Test-PortListening $port) {
            Write-WarnMsg "Port $port is listening."
        }
        else {
            Write-Ok "Port $port is not listening."
        }
    }
}

function Invoke-Logs {
    param(
        [string]$ProjectRoot,
        [switch]$Follow
    )

    $logsPath = Get-LogsPath $ProjectRoot
    $files = @(
        (Join-Path $logsPath "backend-start.log"),
        (Join-Path $logsPath "backend-start.err.log"),
        (Join-Path $logsPath "frontend-start.log"),
        (Join-Path $logsPath "frontend-start.err.log")
    )

    foreach ($file in $files) {
        Write-Info $file
        if (Test-Path -LiteralPath $file -PathType Leaf) {
            Get-Content -LiteralPath $file -Tail 80
        }
        else {
            Write-WarnMsg "Missing log file."
        }
    }

    if ($Follow) {
        $existing = @($files | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
        if ($existing.Count -gt 0) {
            Get-Content -LiteralPath $existing -Tail 20 -Wait
        }
    }
}

function Invoke-CommandByName {
    param([string]$Command)

    $projectRoot = Get-ProjectRoot
    switch ($Command) {
        "doctor" { Invoke-Doctor -ProjectRoot $projectRoot }
        "install" { Invoke-Install -ProjectRoot $projectRoot -SkipFrontend:$SkipFrontend }
        "start" { Invoke-Start -ProjectRoot $projectRoot -NoBrowser:$NoBrowser }
        "stop" { Invoke-Stop -ProjectRoot $projectRoot }
        "restart" {
            Invoke-Stop -ProjectRoot $projectRoot
            Invoke-Start -ProjectRoot $projectRoot -NoBrowser:$NoBrowser
        }
        "status" { Invoke-Status -ProjectRoot $projectRoot }
        "logs" { Invoke-Logs -ProjectRoot $projectRoot -Follow:$Follow }
        default { throw "Unknown command: $Command" }
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Invoke-CommandByName -Command $Command
}
