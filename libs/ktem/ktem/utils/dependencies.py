"""
External dependency checker for Kotaemon.

This module provides utilities to check if required external dependencies
are available on the system, such as LibreOffice and PDF.js.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple


COMMON_SOFFICE_PATHS = (
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/snap/bin/soffice",
    "/opt/libreoffice/program/soffice",
    "/usr/lib/libreoffice/program/soffice",
    "/usr/lib64/libreoffice/program/soffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/Applications/OpenOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    r"C:\Program Files\OpenOffice\program\soffice.exe",
    r"C:\Program Files (x86)\OpenOffice\program\soffice.exe",
)


def find_soffice_binary() -> str:
    """Locate the LibreOffice/OpenOffice CLI across supported platforms."""
    env_path = os.environ.get("SOFFICE_PATH", "").strip()
    if env_path and Path(env_path).is_file():
        return env_path

    for command in ("soffice", "soffice.exe"):
        discovered = shutil.which(command)
        if discovered and Path(discovered).is_file():
            return discovered

    for candidate in COMMON_SOFFICE_PATHS:
        if Path(candidate).is_file():
            return candidate

    return ""


class DependencyChecker:
    """Check external dependencies availability."""

    @staticmethod
    def check_libreoffice() -> Tuple[bool, Optional[str]]:
        """
        Check if LibreOffice is installed.

        Returns:
            Tuple of (is_available, version_or_error_message)
        """
        try:
            soffice_path = find_soffice_binary()
            if not soffice_path:
                return False, None

            # Get version information
            result = subprocess.run(
                [soffice_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            return False, None

        except Exception:
            return False, None

    @staticmethod
    def check_pdfjs() -> Tuple[bool, Optional[str]]:
        """
        Check if PDF.js is available.

        Returns:
            Tuple of (is_available, path_or_error_message)
        """
        try:
            from ktem.assets import PDFJS_PREBUILT_DIR

            if not PDFJS_PREBUILT_DIR.exists():
                return False, f"Directory not found: {PDFJS_PREBUILT_DIR}"

            viewer_html = PDFJS_PREBUILT_DIR / "web" / "viewer.html"
            if not viewer_html.exists():
                return False, f"viewer.html not found: {viewer_html}"

            return True, str(PDFJS_PREBUILT_DIR)

        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_installation_guide() -> str:
        """
        Get installation guide for missing dependencies.

        Returns:
            Formatted installation guide string
        """
        guide = []
        guide.append("\n" + "=" * 60)
        guide.append("Dependencies Installation Guide")
        guide.append("=" * 60)

        guide.append("\nLibreOffice (Required for Office document preview)")
        guide.append("\n   Quick installation:")
        guide.append("   - Windows: Run scripts\\setup.ps1")
        guide.append("   - Linux:   Run bash scripts/setup.sh")
        guide.append("   - macOS:   Run bash scripts/setup.sh")
        guide.append("\n   Or install manually:")
        guide.append("   - Windows: https://www.libreoffice.org/download/")
        guide.append("   - Linux:   sudo apt-get install libreoffice")
        guide.append("   - macOS:   brew install --cask libreoffice")

        guide.append("\nPDF.js (Built-in, no installation required)")
        guide.append("   Location: libs/ktem/ktem/assets/prebuilt/pdfjs-4.0.379-dist/")

        guide.append("\n" + "=" * 60)

        return "\n".join(guide)

    @classmethod
    def check_all(cls, verbose: bool = True) -> bool:
        """
        Check all dependencies and report status.

        Args:
            verbose: If True, print detailed status messages

        Returns:
            True if all critical dependencies are available
        """
        all_ok = True

        # Check LibreOffice
        lo_available, lo_info = cls.check_libreoffice()
        if not lo_available:
            if verbose:
                print("\n[WARN] LibreOffice not detected!")
                print("   Office document preview will NOT work.")
            all_ok = False
        elif verbose:
            print(f"\n[OK] LibreOffice: {lo_info}")

        # Check PDF.js
        pdfjs_available, pdfjs_info = cls.check_pdfjs()
        if not pdfjs_available:
            if verbose:
                print("\n[WARN] PDF.js not detected!")
                print(f"   {pdfjs_info}")
            all_ok = False
        elif verbose:
            print(f"[OK] PDF.js: {pdfjs_info}")

        # Print installation guide if needed
        if not all_ok and verbose:
            print(cls.get_installation_guide())

        return all_ok
