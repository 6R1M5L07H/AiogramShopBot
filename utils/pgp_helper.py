"""
PGP Public Key Helper Utility

Provides functionality to parse and extract metadata from PGP public keys.
Used for displaying shop's public key information to users.
"""
import base64
import logging
from datetime import datetime
from typing import Optional


class PGPKeyHelper:
    """Helper class for PGP public key operations"""

    @staticmethod
    def parse_public_key(base64_key: str) -> dict:
        """
        Parse PGP public key and extract metadata.

        Args:
            base64_key: Base64-encoded PGP public key (ASCII-armored)

        Returns:
            dict with:
            - fingerprint: str (formatted with spaces every 4 chars)
            - expiration: str (DD.MM.YYYY or "Unbegrenzt"/"Never expires")
            - key_shortened: str (~400 chars for display)
            - key_full: str (complete ASCII-armored key)
            - error: Optional[str] (error message if parsing failed)

        Example:
            >>> result = PGPKeyHelper.parse_public_key(config.PGP_PUBLIC_KEY_BASE64)
            >>> print(result['fingerprint'])
            'AB12 CD34 EF56 7890 1234 5678 90AB CDEF 1234 5678'
        """
        result = {
            'fingerprint': None,
            'expiration': None,
            'key_shortened': None,
            'key_full': None,
            'error': None
        }

        try:
            # Decode base64 to get ASCII-armored key
            key_ascii = base64.b64decode(base64_key).decode('utf-8')
            result['key_full'] = key_ascii

            # Try to import pgpy and parse key
            try:
                import pgpy
                key, _ = pgpy.PGPKey.from_blob(key_ascii)

                # Extract fingerprint (40 hex chars) and format with spaces
                fingerprint_hex = key.fingerprint.replace(' ', '')
                result['fingerprint'] = PGPKeyHelper._format_fingerprint(fingerprint_hex)

                # Extract expiration date
                if key.expires_at:
                    result['expiration'] = key.expires_at.strftime('%d.%m.%Y')
                else:
                    # Will be replaced by localization key
                    result['expiration'] = None

            except ImportError:
                logging.warning("pgpy library not available - GPG key metadata extraction disabled")
                result['error'] = "pgpy_not_installed"
            except Exception as parse_error:
                logging.error(f"Failed to parse PGP key: {parse_error}")
                result['error'] = "parse_failed"

            # Create shortened version for display (~400 chars)
            result['key_shortened'] = PGPKeyHelper._shorten_key(key_ascii)

        except Exception as e:
            logging.error(f"Failed to decode PGP key from base64: {e}")
            result['error'] = "decode_failed"

        return result

    @staticmethod
    def _format_fingerprint(fingerprint_hex: str) -> str:
        """
        Format fingerprint with spaces every 4 characters.

        Args:
            fingerprint_hex: 40-character hex string

        Returns:
            Formatted fingerprint (e.g., "AB12 CD34 EF56 7890 ...")

        Example:
            >>> PGPKeyHelper._format_fingerprint("AB12CD34EF567890")
            'AB12 CD34 EF56 7890'
        """
        # Ensure uppercase
        fingerprint_hex = fingerprint_hex.upper()

        # Split into groups of 4
        groups = [fingerprint_hex[i:i+4] for i in range(0, len(fingerprint_hex), 4)]

        return ' '.join(groups)

    @staticmethod
    def _shorten_key(key_ascii: str) -> str:
        """
        Shorten PGP key for display while keeping structure intact.

        Keeps header, footer, and first ~300 chars of key data.

        Args:
            key_ascii: Full ASCII-armored PGP key

        Returns:
            Shortened key suitable for Telegram display

        Example:
            -----BEGIN PGP PUBLIC KEY BLOCK-----

            mQINBGcX...
            [shortened]
            ...END KEY-----
        """
        lines = key_ascii.strip().split('\n')

        # Find header and footer lines
        header_idx = next((i for i, line in enumerate(lines) if line.startswith('-----BEGIN')), 0)
        footer_idx = next((i for i, line in enumerate(lines) if line.startswith('-----END')), len(lines) - 1)

        # Extract header (including Version line if present)
        header_lines = []
        for i in range(header_idx, len(lines)):
            header_lines.append(lines[i])
            # Stop after header and optional Version/Comment lines
            if lines[i].startswith('-----BEGIN') or lines[i].startswith('Version:') or lines[i].startswith('Comment:'):
                continue
            if lines[i].strip() == '':
                break

        # Extract key data (between header and footer)
        key_data_lines = []
        for i in range(header_idx + len(header_lines), footer_idx):
            if lines[i].strip():  # Skip empty lines
                key_data_lines.append(lines[i])

        # Take first ~6 lines of key data (roughly 300-400 chars)
        shortened_data = key_data_lines[:6]

        # Add ellipsis if truncated
        if len(key_data_lines) > 6:
            shortened_data.append('[...]')

        # Reconstruct shortened key
        result_lines = header_lines + shortened_data + [lines[footer_idx]]

        return '\n'.join(result_lines)