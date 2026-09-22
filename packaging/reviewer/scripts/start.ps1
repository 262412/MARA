param([int]$Port = 7860, [switch]$NoBrowser)
. (Join-Path $PSScriptRoot 'common.ps1')
$result = 0
try {
    Assert-Bundle
    Set-BundleEnvironment
    Start-BundleLog 'start'
    if (-not (Test-Path -LiteralPath (Join-Path $RuntimeRoot 'installed.json'))) {
        throw 'Run Install.cmd successfully before starting MARA.'
    }
    $installed = Get-Content -LiteralPath (Join-Path $RuntimeRoot 'installed.json') -Raw | ConvertFrom-Json
    if ($installed.bundle_id -ne $Manifest.bundle_id) { throw 'Run Install.cmd for this bundle version.' }
    $command = @('app', 'run', '--host', '127.0.0.1', '--port', [string]$Port)
    if ($NoBrowser) { $command += '--no-browser' }
    Write-Host "Open http://127.0.0.1:$Port after startup. Close this window to stop MARA."
    Invoke-Checked $MaraExe $command
} catch {
    Write-Host ("START FAILED: " + $_.Exception.Message) -ForegroundColor Red
    $result = 1
} finally {
    if (Get-Variable LogPath -Scope Script -ErrorAction SilentlyContinue) {
        Stop-Transcript | Out-Null
    }
}
exit $result
