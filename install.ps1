param(
    [string]$VenvPath = ".venv",
    [string]$Python = "3.10",
    [switch]$SkipInit,
    [switch]$InstallCodex,
    [switch]$InstallClaudeCode
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $scriptRoot $VenvPath

if (-not (Test-Path (Join-Path $scriptRoot "pyproject.toml")) -or
    -not (Test-Path (Join-Path $scriptRoot "uv.lock"))) {
    Write-Error "install.ps1 supports a verified MARA source checkout with uv.lock."
    exit 64
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required. Install a verified uv release with your package manager."
    exit 69
}
$env:UV_PYTHON_DOWNLOADS = "never"
& uv python find $Python *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "A local Python $Python interpreter is required; automatic downloads are disabled."
    exit 69
}

$env:UV_PROJECT_ENVIRONMENT = $venvDir
& uv sync --project $scriptRoot --frozen --no-dev --extra mara --python $Python
$syncExit = $LASTEXITCODE
if ($syncExit -ne 0) {
    [Console]::Error.WriteLine("The frozen uv sync failed with exit code $syncExit.")
    exit $syncExit
}

$venvMARA = Join-Path $venvDir "Scripts\MARA.exe"
if (-not (Test-Path $venvMARA)) {
    Write-Error "The frozen sync did not create $venvMARA."
    exit 70
}

if (-not $SkipInit) {
    & $venvMARA app init
    $initExit = $LASTEXITCODE
    if ($initExit -ne 0) {
        [Console]::Error.WriteLine("MARA app init failed with exit code $initExit.")
        exit $initExit
    }
}
& $venvMARA app doctor
$doctorExit = $LASTEXITCODE
if ($doctorExit -ne 0) {
    [Console]::Error.WriteLine("MARA app doctor failed with exit code $doctorExit.")
    exit $doctorExit
}

if ($InstallCodex) {
    & $venvMARA platform install --platform codex --mode full --yes
    $codexExit = $LASTEXITCODE
    if ($codexExit -ne 0) {
        [Console]::Error.WriteLine("Codex platform install failed with exit code $codexExit.")
        exit $codexExit
    }
}
if ($InstallClaudeCode) {
    & $venvMARA platform install --platform claude-code --mode full --yes
    $claudeExit = $LASTEXITCODE
    if ($claudeExit -ne 0) {
        [Console]::Error.WriteLine("Claude Code platform install failed with exit code $claudeExit.")
        exit $claudeExit
    }
}

Write-Host ""
Write-Host "MARA is ready."
Write-Host "Run '$venvMARA app run' to launch the Web UI."
Write-Host "Run '$venvMARA docqa doctor' to validate the shared DocQA runtime."
Write-Host "Run '$venvMARA doctor' to validate the MARA runtime."
