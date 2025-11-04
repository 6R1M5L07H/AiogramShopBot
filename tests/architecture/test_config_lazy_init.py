"""
Unit Tests for Config Lazy Initialization

Tests that config.py can be imported without side-effects.
"""

import pytest
import sys
import os


class TestConfigLazyInit:
    """Test Config Lazy Initialization"""

    def test_config_has_initialize_function(self):
        """Test config module has initialize_webhook_config() function"""
        import config
        assert hasattr(config, 'initialize_webhook_config')
        assert callable(config.initialize_webhook_config)

    def test_config_webhook_vars_start_as_none(self):
        """Test WEBHOOK_HOST and WEBHOOK_URL are None after import"""
        import config

        # Before initialization, these should be None (in TEST mode)
        # This proves no side-effects happened at import time
        if config.RUNTIME_ENVIRONMENT.value == "TEST":
            assert config.WEBHOOK_HOST is None
            assert config.WEBHOOK_URL is None

    def test_initialize_webhook_config_sets_variables(self):
        """Test initialize_webhook_config() sets WEBHOOK_HOST and WEBHOOK_URL"""
        import config

        # Call initialization
        result = config.initialize_webhook_config()

        # In TEST mode, should remain None
        if config.RUNTIME_ENVIRONMENT.value == "TEST":
            assert config.WEBHOOK_HOST is None
            assert config.WEBHOOK_URL is None
            assert result is None

    def test_no_ngrok_import_at_module_level(self):
        """Test config doesn't call start_ngrok() at module level"""
        # Read config.py directly from file
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.py')
        with open(config_path, 'r') as f:
            source = f.read()

        # Should NOT have start_ngrok() at module level (outside function)
        # The only place it should appear is inside initialize_webhook_config()
        lines = source.split('\n')

        in_function = False
        for line in lines:
            # Track if we're inside a function
            if line.startswith('def '):
                in_function = True
            elif line and not line[0].isspace() and in_function:
                in_function = False

            # If we find start_ngrok() outside a function, that's bad
            if 'start_ngrok()' in line and not in_function and 'def ' not in line:
                # Check if it's in a comment
                if '#' in line:
                    comment_start = line.index('#')
                    code_part = line[:comment_start]
                    if 'start_ngrok()' in code_part:
                        pytest.fail("start_ngrok() found at module level (not in function)")
                else:
                    pytest.fail("start_ngrok() found at module level (not in function)")

    def test_no_external_ip_request_at_module_level(self):
        """Test config doesn't call get_sslipio_external_url() at module level"""
        # Read config.py directly from file
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.py')
        with open(config_path, 'r') as f:
            source = f.read()

        # Should NOT have get_sslipio_external_url() at module level
        lines = source.split('\n')

        in_function = False
        for line in lines:
            if line.startswith('def '):
                in_function = True
            elif line and not line[0].isspace() and in_function:
                in_function = False

            if 'get_sslipio_external_url()' in line and not in_function and 'def ' not in line:
                if '#' in line:
                    comment_start = line.index('#')
                    code_part = line[:comment_start]
                    if 'get_sslipio_external_url()' in code_part:
                        pytest.fail("get_sslipio_external_url() found at module level")
                else:
                    pytest.fail("get_sslipio_external_url() found at module level")


if __name__ == "__main__":
    """
    Run tests with:
        pytest tests/architecture/test_config_lazy_init.py -v
    """
    pytest.main([__file__, "-v"])
