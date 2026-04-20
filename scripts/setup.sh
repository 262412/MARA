#!/bin/bash
set -eo pipefail

# ============================================================================
# Kotaemon System Dependencies Setup Script
# ============================================================================
# This script installs system-level dependencies required for Kotaemon:
# - LibreOffice (required for Office document preview)
# - Poppler (optional, for PDF processing)
# - Tesseract (optional, for OCR text recognition)
# ============================================================================

echo "============================================================"
echo "Kotaemon System Dependencies Setup"
echo "============================================================"
echo ""

# Detect operating system
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
elif [ "$(uname)" == "Darwin" ]; then
    OS="macos"
else
    echo "❌ Unable to detect operating system"
    exit 1
fi

echo "Detected OS: $OS"
echo ""

# ----------------------------------------------------------------------------
# Install LibreOffice
# ----------------------------------------------------------------------------
install_libreoffice() {
    echo "📦 Installing LibreOffice..."

    case $OS in
        ubuntu|debian|linuxmint)
            echo "Installing via apt..."
            sudo apt-get update
            sudo apt-get install -y libreoffice libreoffice-script-provider-python
            ;;
        fedora|centos|rhel)
            echo "Installing via dnf/yum..."
            sudo dnf install -y libreoffice-core || sudo yum install -y libreoffice-core
            ;;
        opensuse-leap|opensuse-tumbleweed)
            echo "Installing via zypper..."
            sudo zypper install -y libreoffice
            ;;
        macos)
            if command -v brew &> /dev/null; then
                echo "Installing via Homebrew..."
                brew install --cask libreoffice
            else
                echo "❌ Homebrew not found. Please install it first: https://brew.sh"
                exit 1
            fi
            ;;
        *)
            echo "❌ Unsupported OS: $OS"
            echo "   Please install LibreOffice manually: https://www.libreoffice.org/download/"
            exit 1
            ;;
    esac

    # Verify installation
    if command -v soffice &> /dev/null; then
        SOFFICE_VERSION=$(soffice --version)
        echo "✅ LibreOffice installed successfully! Version: $SOFFICE_VERSION"
    else
        echo "❌ LibreOffice installation failed. Please check error messages above."
        exit 1
    fi
}

# ----------------------------------------------------------------------------
# Install Poppler (PDF utilities)
# ----------------------------------------------------------------------------
install_poppler() {
    echo "📦 Installing Poppler (optional PDF utilities)..."

    case $OS in
        ubuntu|debian|linuxmint)
            sudo apt-get install -y poppler-utils
            ;;
        fedora|centos|rhel)
            sudo dnf install -y poppler-utils
            ;;
        macos)
            brew install poppler
            ;;
    esac

    echo "✅ Poppler installed successfully"
}

# ----------------------------------------------------------------------------
# Install Tesseract OCR
# ----------------------------------------------------------------------------
install_tesseract() {
    echo "📦 Installing Tesseract OCR (optional text recognition)..."

    case $OS in
        ubuntu|debian|linuxmint)
            sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
            ;;
        fedora|centos|rhel)
            sudo dnf install -y tesseract
            ;;
        macos)
            brew install tesseract
            ;;
    esac

    echo "✅ Tesseract installed successfully"
}

# ----------------------------------------------------------------------------
# Main menu
# ----------------------------------------------------------------------------
echo "Please select components to install:"
echo "1) LibreOffice (Required for Office document preview)"
echo "2) Poppler (Optional, PDF processing tools)"
echo "3) Tesseract (Optional, OCR text recognition)"
echo "4) Install All (Recommended)"
echo "5) Skip"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        install_libreoffice
        ;;
    2)
        install_poppler
        ;;
    3)
        install_tesseract
        ;;
    4)
        install_libreoffice
        install_poppler
        install_tesseract
        ;;
    5)
        echo "Installation skipped."
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

echo ""
echo "============================================================"
echo "✅ Dependencies installation completed!"
echo ""
echo "Next steps:"
echo "1. Run: bash scripts/run_linux.sh (or run_macos.sh)"
echo "2. Visit: http://localhost:7860"
echo "============================================================"
