"""
Local schwab package - Schwab API integration modules for portfolio management

This package contains local modules for Schwab integration. When external
schwab-py package components (auth, client, etc.) are imported, we redirect
to the external package to avoid naming conflicts.
"""

# When importing schwab.auth or other schwab-py components, redirect to external package
# This handles the case where code does "from schwab import auth"
import sys as _sys
from pathlib import Path as _Path

# Remove this directory from path temporarily to import external schwab package
_this_dir = str(_Path(__file__).parent.parent)
_saved_path = _sys.path.copy()
_sys.path = [p for p in _sys.path if _this_dir not in p and 'Portfolio Scripts Schwab' not in p]

try:
    # Import external schwab-py package
    import schwab as _external_schwab
    # Re-export commonly used components
    auth = _external_schwab.auth
    client = _external_schwab.client
finally:
    # Restore path
    _sys.path = _saved_path
    del _this_dir, _saved_path, _sys, _Path

# Clean up namespace
del _external_schwab
