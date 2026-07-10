@ECHO off
ECHO scripts\run_windows.bat is retired because it used mutable, unchecked installers. 1>&2
ECHO From a verified source checkout, run install.ps1 and then .venv\Scripts\MARA.exe app run. 1>&2
REM The canonical path resolves KH_APP_DATA_DIR via ktem.runtime_bootstrap and
REM materializes bundled assets with ktem.assets.pdfjs_assets.
EXIT /B 64
