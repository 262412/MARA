param()
. (Join-Path $PSScriptRoot 'common.ps1')
$result = 0
try {
    Assert-Bundle
    Set-BundleEnvironment
    Start-BundleLog 'install'
    Write-Host "Installing $($Manifest.bundle_id)"
    $marker = Join-Path $RuntimeRoot 'installed.json'
    if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker }
    Invoke-Checked $Uv @('--no-config', 'python', 'install', $Manifest.python_version, '--no-bin', '--no-registry')
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Invoke-Checked $Uv @('--no-config', 'venv', '--managed-python', '--python', $Manifest.python_version, $EnvironmentPath)
    }
    Invoke-Checked $Uv @('--no-config', 'pip', 'sync', '--python', $PythonExe,
        '--require-hashes', '--only-binary', ':all:', '--default-index', 'https://pypi.org/simple',
        '--find-links', (Join-Path $BundleRoot 'wheels'), (Join-Path $BundleRoot 'runtime-requirements.txt'))
    Invoke-Checked $Uv @('--no-config', 'pip', 'install', '--python', $PythonExe,
        '--no-deps', '--no-index', '--require-hashes', '--requirement', (Join-Path $BundleRoot 'application-requirements.txt'))
    Invoke-Checked $Uv @('--no-config', 'pip', 'check', '--python', $PythonExe)
    Invoke-Checked $MaraExe @('--help')
    if (-not (Test-Path -LiteralPath (Join-Path $env:MARA_APP_HOME 'config\flowsettings.py'))) {
        Invoke-Checked $MaraExe @('app', 'init', '--auth-mode', 'local')
    }
    Invoke-Checked $PythonExe @((Join-Path $BundleRoot 'scripts\verify_runtime.py'))
    @{ bundle_id = $Manifest.bundle_id; installed_at = (Get-Date).ToUniversalTime().ToString('o') } |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $RuntimeRoot 'installed.json') -Encoding UTF8
    Write-Host 'Installation checks passed. Run Start.cmd, then configure your model and embedding providers.'
    Write-Host 'No model credentials, model weights, or generated answers are included.'
} catch {
    Write-Host ("INSTALL FAILED: " + $_.Exception.Message) -ForegroundColor Red
    $result = 1
} finally {
    if (Get-Variable LogPath -Scope Script -ErrorAction SilentlyContinue) {
        Stop-Transcript | Out-Null
    }
}
exit $result
