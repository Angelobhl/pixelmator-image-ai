"""
AppleScript bridge module.
Provides interface to run AppleScript commands.
"""

import subprocess
from pathlib import Path
from typing import Optional, Tuple


class AppleScriptRunner:
    """Runner for AppleScript commands."""

    @staticmethod
    def run(script: str) -> Tuple[bool, str]:
        """
        Run an AppleScript command.

        Args:
            script: AppleScript code to execute

        Returns:
            Tuple of (success, output_or_error)
        """
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "AppleScript execution timed out"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def run_file(script_path: Path) -> Tuple[bool, str]:
        """
        Run an AppleScript file.

        Args:
            script_path: Path to .scpt or .as file

        Returns:
            Tuple of (success, output_or_error)
        """
        try:
            result = subprocess.run(
                ['osascript', str(script_path)],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip()

        except subprocess.TimeoutExpired:
            return False, "AppleScript execution timed out"
        except Exception as e:
            return False, str(e)