import os

"""Test configuration to set environment variables for the pytest suite.
This ensures required settings are present before importing modules
that depend on them."""

# Flag application is running in test mode
os.environ.setdefault("TESTING", "1")

# Provide a deterministic encryption master key for the encryption service
os.environ.setdefault(
    "ENCRYPTION_MASTER_KEY",
    "dGVzdF9tYXN0ZXJfa2V5XzEyMzQ1Njc4OTA="
)

# Secret used by webhook verification during tests
os.environ.setdefault("WEBHOOK_SECRET", "test_webhook_secret_key")

# Set a predictable order timeout for tests
os.environ.setdefault("ORDER_TIMEOUT_MINUTES", "30")

# Minimal configuration required by config.py
os.environ.setdefault("CURRENCY", "USD")
os.environ.setdefault("WEBHOOK_PATH", "/test-webhook")
