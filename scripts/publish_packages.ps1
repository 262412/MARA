param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCandidates = @(
    (Join-Path $scriptRoot "..\\.venv\\Scripts\\python.exe"),
    "py",
    "python"
)

$pythonCommand = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -like "*.exe" -and (Test-Path $candidate)) {
        $pythonCommand = @($candidate)
        break
    }
    $resolved = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($resolved) {
        if ($candidate -eq "py") {
            $pythonCommand = @("py", "-3.10")
        } else {
            $pythonCommand = @($candidate)
        }
        break
    }
}

if (-not $pythonCommand) {
    throw "Python 3.10+ was not found on PATH."
}

$scriptPath = Join-Path $scriptRoot "publish_packages.py"
$pythonArgs = @()
if ($pythonCommand.Length -gt 1) {
    $pythonArgs = @($pythonCommand[1..($pythonCommand.Length - 1)] | Where-Object { $_ })
}
& $pythonCommand[0] @pythonArgs $scriptPath @Args
