/**
 * Telegram Mini App: PGP Shipping Address Encryption
 *
 * Encrypts user's shipping address with PGP public key client-side
 * before sending to bot via Telegram.WebApp.sendData()
 */

(function() {
    'use strict';

    // Initialize Telegram WebApp
    const tg = window.Telegram.WebApp;
    tg.expand();
    tg.ready();

    // Apply Telegram theme colors
    applyTelegramTheme();

    // DOM Elements
    const addressInput = document.getElementById('address');
    const encryptBtn = document.getElementById('encryptBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    const statusDiv = document.getElementById('status');

    // Event Listeners
    encryptBtn.addEventListener('click', handleEncrypt);
    cancelBtn.addEventListener('click', handleCancel);

    // Enable/disable encrypt button based on input
    addressInput.addEventListener('input', () => {
        encryptBtn.disabled = !addressInput.value.trim();
    });

    // Initialize button state
    encryptBtn.disabled = true;

    /**
     * Apply Telegram theme colors from WebApp API
     */
    function applyTelegramTheme() {
        if (!tg.themeParams) return;

        const root = document.documentElement;
        const theme = tg.themeParams;

        if (theme.bg_color) root.style.setProperty('--tg-theme-bg-color', theme.bg_color);
        if (theme.text_color) root.style.setProperty('--tg-theme-text-color', theme.text_color);
        if (theme.hint_color) root.style.setProperty('--tg-theme-hint-color', theme.hint_color);
        if (theme.link_color) root.style.setProperty('--tg-theme-link-color', theme.link_color);
        if (theme.button_color) root.style.setProperty('--tg-theme-button-color', theme.button_color);
        if (theme.button_text_color) root.style.setProperty('--tg-theme-button-text-color', theme.button_text_color);
        if (theme.secondary_bg_color) root.style.setProperty('--tg-theme-secondary-bg-color', theme.secondary_bg_color);
    }

    /**
     * Show status message
     */
    function showStatus(message, type = 'loading') {
        statusDiv.textContent = message;
        statusDiv.className = `status-message visible ${type}`;
    }

    /**
     * Hide status message
     */
    function hideStatus() {
        statusDiv.className = 'status-message';
    }

    /**
     * Handle encrypt button click
     */
    async function handleEncrypt() {
        const address = addressInput.value.trim();

        if (!address) {
            showStatus(STRINGS.error_empty, 'error');
            tg.HapticFeedback.notificationOccurred('error');
            return;
        }

        // Disable buttons during encryption
        encryptBtn.disabled = true;
        cancelBtn.disabled = true;

        try {
            showStatus(STRINGS.encrypting, 'loading');
            tg.HapticFeedback.impactOccurred('medium');

            // Encrypt address with PGP
            const encryptedAddress = await encryptWithPGP(address);

            // Show success briefly
            showStatus(STRINGS.success, 'success');
            tg.HapticFeedback.notificationOccurred('success');

            // Send encrypted data back to bot
            setTimeout(() => {
                tg.sendData(JSON.stringify({
                    encrypted_address: encryptedAddress,
                    encryption_mode: 'pgp'
                }));
            }, 500);

        } catch (error) {
            console.error('Encryption error:', error);
            showStatus(STRINGS.error_encryption, 'error');
            tg.HapticFeedback.notificationOccurred('error');

            // Re-enable buttons on error
            encryptBtn.disabled = false;
            cancelBtn.disabled = false;
        }
    }

    /**
     * Handle cancel button click
     */
    function handleCancel() {
        tg.HapticFeedback.impactOccurred('light');
        tg.close();
    }

    /**
     * Encrypt text with PGP public key using OpenPGP.js
     *
     * @param {string} plaintext - Address to encrypt
     * @returns {Promise<string>} - ASCII-armored PGP message
     */
    async function encryptWithPGP(plaintext) {
        try {
            // Read public key
            const publicKey = await openpgp.readKey({
                armoredKey: PGP_PUBLIC_KEY
            });

            // Encrypt message
            const encrypted = await openpgp.encrypt({
                message: await openpgp.createMessage({ text: plaintext }),
                encryptionKeys: publicKey,
                format: 'armored' // ASCII-armored output
            });

            return encrypted;

        } catch (error) {
            console.error('PGP encryption failed:', error);
            throw new Error('PGP encryption failed');
        }
    }

    /**
     * Handle back button (Telegram native)
     */
    tg.BackButton.onClick(() => {
        tg.close();
    });

    // Show back button
    tg.BackButton.show();

})();
