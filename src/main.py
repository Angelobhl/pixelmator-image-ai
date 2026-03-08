"""
Gemini Vision Bridge for Pixelmator Pro
Application entry point.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    """Main entry point."""
    from src.gui.main_window import main as run_app
    run_app()


if __name__ == "__main__":
    main()