# ============================================================================
# Kotaemon System Dependencies Setup Script (Windows PowerShell)
# ============================================================================
# This script installs system-level dependencies required for Kotaemon:
# - LibreOffice (required for Office document preview)
# - Poppler (optional, for PDF processing)
# - Tesseract (optional, for OCR text recognition)
# ============================================================================

[CmdletBinding()]
param()

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Kotaemon System Dependencies Setup (Windows)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ----------------------------------------------------------------------------
# Check administrator privileges
# ----------------------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(`
    [Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "❌ Please run this script as Administrator" -ForegroundColor Red
    Write-Host "   Right-click on the script -> 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# ----------------------------------------------------------------------------
# Install LibreOffice
# ----------------------------------------------------------------------------
function Install-LibreOffice {
    Write-Host "📦 Downloading and installing LibreOffice..." -ForegroundColor Cyan

    $downloadUrl = "https://download.documentfoundation.org/libreoffice/stable/24.2.7/win/x86_64/LibreOffice_24.2.7_Win_x86-64.msi"
    $installerPath = "$env:TEMP\LibreOffice_Installer.msi"

    try {
        # Download installer
        Write-Host "Download URL: $downloadUrl" -ForegroundColor Gray
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath

        # Silent installation
        Write-Host "Installing..." -ForegroundColor Cyan
        Start-Process -FilePath "msiexec.exe" `
            -ArgumentList "/i `"$installerPath`" /quiet /norestart" `
            -Wait

        # Cleanup installer
        Remove-Item $installerPath -Force

        # Verify installation
        $sofficePath = "C:\Program Files\LibreOffice\program\soffice.exe"
        if (Test-Path $sofficePath) {
            $version = & $sofficePath --version
            Write-Host "✅ LibreOffice installed successfully! Version: $version" -ForegroundColor Green

            # Add to system PATH if not already present
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            if ($currentPath -notlike "*C:\Program Files\LibreOffice\program*") {
                [Environment]::SetEnvironmentVariable(
                    "Path",
                    "$currentPath;C:\Program Files\LibreOffice\program",
                    "Machine"
                )
                Write-Host "✅ Added to system PATH" -ForegroundColor Green
            }
        } else {
            throw "Installation failed"
        }
    }
    catch {
        Write-Host "❌ LibreOffice installation failed: $_" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please install manually:" -ForegroundColor Yellow
        Write-Host "1. Visit: https://www.libreoffice.org/download/download/" -ForegroundColor Yellow
        Write-Host "2. Download and install Windows version" -ForegroundColor Yellow
        exit 1
    }
}

# ----------------------------------------------------------------------------
# Install Poppler (PDF utilities)
# ----------------------------------------------------------------------------
function Install-Poppler {
    Write-Host "📦 Installing Poppler (optional PDF utilities)..." -ForegroundColor Cyan

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install -y poppler
        Write-Host "✅ Poppler installed successfully" -ForegroundColor Green
    } elseif (Get-Command scoop -ErrorAction SilentlyContinue) {
        scoop install poppler
        Write-Host "✅ Poppler installed successfully" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Chocolatey or Scoop not found. Skipping Poppler installation." -ForegroundColor Yellow
        Write-Host "   To install manually: choco install poppler" -ForegroundColor Yellow
    }
}

# ----------------------------------------------------------------------------
# Install Tesseract OCR
# ----------------------------------------------------------------------------
function Install-Tesseract {
    Write-Host "📦 Installing Tesseract OCR (optional text recognition)..." -ForegroundColor Cyan

    if (Get-Command choco -ErrorAction SilentlyContinue) {
        choco install -y tesseract
        Write-Host "✅ Tesseract installed successfully" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Chocolatey not found. Skipping Tesseract installation." -ForegroundColor Yellow
        Write-Host "   To install manually: choco install tesseract" -ForegroundColor Yellow
    }
}

# ----------------------------------------------------------------------------
# Main menu
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "Please select components to install:" -ForegroundColor Cyan
Write-Host "1) LibreOffice (Required for Office document preview)"
Write-Host "2) Poppler (Optional, PDF processing tools)"
Write-Host "3) Tesseract (Optional, OCR text recognition)"
Write-Host "4) Install All (Recommended)"
Write-Host "5) Skip"
Write-Host ""
$choice = Read-Host "Enter your choice (1-5)"

switch ($choice) {
    "1" { Install-LibreOffice }
    "2" { Install-Poppler }
    "3" { Install-Tesseract }
    "4" {
        Install-LibreOffice
        Install-Poppler
        Install-Tesseract
    }
    "5" {
        Write-Host "Installation skipped." -ForegroundColor Yellow
        exit 0
    }
    default {
        Write-Host "Invalid option" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "✅ Dependencies installation completed!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Reopen PowerShell (to refresh PATH)" -ForegroundColor White
Write-Host "2. Run: .\scripts\run_windows.bat" -ForegroundColor White
Write-Host "3. Visit: http://localhost:7860" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
