#!/bin/bash

# Development Environment Variables Setup Script
# WARNING: This script contains placeholder values for development only
# DO NOT use these values in production environments

echo "Setting development environment variables..."

# Telegram Bot Configuration
export BOT_TOKEN="7696600032:AAGnHTvivdEoK1r1zy0Glub7KYHRAOejEag"
export ADMIN_IDS="595507864"
export WEBHOOK_SECRET="dev-webhook-secret-12345"

# Database Configuration
export DATABASE_PASSWORD="dev-database-password-123"

# NGROK Configuration (for development tunneling)
export NGROK_AUTH_TOKEN="2mfwqjOgqpHukrezd5L5CtAEU5Y_4aLS8BgH9vAV8558REWSc"

# KryptoExpress API Configuration
export KRYPTO_API_KEY="dev-krypto-api-key-placeholder"
export KRYPTO_API_SECRET="dev-krypto-secret-placeholder-123"

# Redis Configuration
export REDIS_AUTH_PASSWORD="dev-redis-password-123"

echo "Development environment variables have been set."
echo ""
echo "Current sensitive environment variables:"
echo "BOT_TOKEN: ${BOT_TOKEN:0:10}..."
echo "ADMIN_IDS: $ADMIN_IDS"
echo "DATABASE_PASSWORD: ${DATABASE_PASSWORD:0:5}..."
echo "NGROK_AUTH_TOKEN: ${NGROK_AUTH_TOKEN:0:10}..."
echo "KRYPTO_API_KEY: ${KRYPTO_API_KEY:0:10}..."
echo "KRYPTO_API_SECRET: ${KRYPTO_API_SECRET:0:10}..."
echo "REDIS_AUTH_PASSWORD: ${REDIS_AUTH_PASSWORD:0:5}..."
echo ""
echo "To use these variables, run: source ./set-dev-env.sh"
echo "Then start the bot with: python run.py"