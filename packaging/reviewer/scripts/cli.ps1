param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CommandArgs)
. (Join-Path $PSScriptRoot 'common.ps1')
try {
    Assert-Bundle
    Set-BundleEnvironment
    if (-not (Test-Path -LiteralPath $MaraExe)) { throw 'Run Install.cmd first.' }
    Invoke-Checked $MaraExe $CommandArgs
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
