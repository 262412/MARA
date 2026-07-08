param(
    [string]$VenvPath = ".venv",
    [switch]$SkipInit,
    [switch]$InstallCodex,
    [switch]$InstallClaudeCode
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $scriptRoot $VenvPath

function Get-PythonCommand {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @("py", "-3.10")
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @("python")
    }

    throw "Python 3.10+ was not found on PATH."
}

$pythonCmd = Get-PythonCommand

if (-not (Test-Path $venvDir)) {
    if ($pythonCmd.Length -gt 1) {
        & $pythonCmd[0] $pythonCmd[1] -m venv $venvDir
    } else {
        & $pythonCmd[0] -m venv $venvDir
    }
}

$venvPython = Join-Path $venvDir "Scripts\\python.exe"
$venvKotaemon = Join-Path $venvDir "Scripts\\kotaemon.exe"
$venvMARA = Join-Path $venvDir "Scripts\\MARA.exe"

& $venvPython -m pip install --upgrade pip

$localKtem = Join-Path $scriptRoot "libs\\ktem\\pyproject.toml"
$localKotaemon = Join-Path $scriptRoot "libs\\kotaemon\\pyproject.toml"
$localSlideCli = Join-Path $scriptRoot "libs\\slide_cli\\pyproject.toml"
if ((Test-Path $localKtem) -and (Test-Path $localKotaemon)) {
    & $venvPython -m pip install (Join-Path $scriptRoot "libs\\ktem")
    & $venvPython -m pip install ((Join-Path $scriptRoot "libs\\kotaemon") + "[all]")
    if (Test-Path $localSlideCli) {
        & $venvPython -m pip install (Join-Path $scriptRoot "libs\\slide_cli")
    }
} else {
    & $venvPython -m pip install "mara-app[mara]"
}

if (-not $SkipInit) {
    if (Test-Path $venvMARA) {
        & $venvMARA app init
    } else {
        & $venvKotaemon app init
    }
}

if (Test-Path $venvMARA) {
    & $venvMARA app doctor
} else {
    & $venvKotaemon app doctor
}

if ($InstallCodex) {
    if (Test-Path $venvMARA) {
        & $venvMARA platform install --platform codex --mode full --yes
    } else {
        & $venvKotaemon platform install --platform codex --mode full --yes
    }
}

if ($InstallClaudeCode) {
    if (Test-Path $venvMARA) {
        & $venvMARA platform install --platform claude-code --mode full --yes
    } else {
        & $venvKotaemon platform install --platform claude-code --mode full --yes
    }
}

Write-Host ""
if (Test-Path $venvMARA) {
    Write-Host "MARA is ready."
    Write-Host "Run '$venvMARA app run' to launch the Web UI."
    Write-Host "Run '$venvMARA docqa doctor' to validate the shared DocQA runtime."
    Write-Host "Run '$venvMARA doctor' to validate the MARA runtime."
} else {
    Write-Host "Kotaemon is ready."
    Write-Host "Run '$venvKotaemon app run' to launch the Web UI."
    Write-Host "Run '$venvKotaemon docqa doctor' to validate the shared DocQA runtime."
}
