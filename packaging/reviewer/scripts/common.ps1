$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$BundleRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $BundleRoot 'runtime'
$Uv = Join-Path $BundleRoot 'tools\uv.exe'
$EnvironmentPath = Join-Path $RuntimeRoot 'environment'
$PythonExe = Join-Path $EnvironmentPath 'Scripts\python.exe'
$MaraExe = Join-Path $EnvironmentPath 'Scripts\MARA.exe'

function Assert-Bundle {
    if (-not [Environment]::Is64BitOperatingSystem -or
        $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'This bundle requires Windows x64.'
    }
    $manifestPath = Join-Path $BundleRoot 'manifest.json'
    $script:Manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $prefix = [IO.Path]::GetFullPath($BundleRoot) + [IO.Path]::DirectorySeparatorChar
    foreach ($entry in $Manifest.files.PSObject.Properties) {
        $path = [IO.Path]::GetFullPath((Join-Path $BundleRoot $entry.Name))
        if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Invalid manifest path: $($entry.Name)"
        }
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing bundle file: $($entry.Name). Extract the complete ZIP."
        }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.Value) {
            throw "Checksum mismatch: $($entry.Name). Download and extract a fresh ZIP."
        }
    }
}

function Set-BundleEnvironment {
    # These are process-local changes; existing installations and user PATH stay intact.
    Get-ChildItem Env: | Where-Object {
        $_.Name -match '^(KH_|MARA_DESKTOP_|THEFLOW_|KOTAEMON_|UV_)' -or
        $_.Name -in @('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')
    } | ForEach-Object { Remove-Item -LiteralPath ("Env:" + $_.Name) }
    $appHome = Join-Path $RuntimeRoot 'app'
    $cache = Join-Path $RuntimeRoot 'cache'
    New-Item -ItemType Directory -Path $RuntimeRoot,$appHome,$cache -Force | Out-Null
    $env:MARA_APP_HOME = $appHome
    $env:MARA_RUNTIME_DIR = $appHome
    $env:KH_APP_DATA_DIR = Join-Path $appHome 'data'
    $env:THEFLOW_SETTINGS_MODULE = 'ktem.default_flowsettings'
    $env:THEFLOW_TEMP_PATH = Join-Path $cache 'theflow'
    $env:GRADIO_TEMP_DIR = Join-Path $cache 'gradio'
    $env:GRADIO_ANALYTICS_ENABLED = 'False'
    $env:HF_HOME = Join-Path $cache 'huggingface'
    $env:TORCH_HOME = Join-Path $cache 'torch'
    $env:XDG_CACHE_HOME = $cache
    $env:UV_CACHE_DIR = Join-Path $cache 'uv'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $RuntimeRoot 'python'
    $env:UV_PYTHON_DOWNLOADS = 'automatic'
    $env:UV_LINK_MODE = 'copy'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:NO_PROXY = 'localhost,127.0.0.1,::1'
    Set-Location -LiteralPath $BundleRoot
}

function Invoke-Checked {
    param([string]$Executable, [string[]]$ToolArgs)
    & $Executable @ToolArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE. See the log above."
    }
}

function Start-BundleLog {
    param([string]$Action)
    $logs = Join-Path $RuntimeRoot 'logs'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $script:LogPath = Join-Path $logs ("$Action-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
    Start-Transcript -LiteralPath $LogPath -Force | Out-Null
    Write-Host "Log: $LogPath"
}
