#!/bin/bash
set -e

echo "⚠️  PRODUCTION DEPLOYMENT"
echo "========================"
echo "This will deploy to PRODUCTION environment."
echo ""
read -p "Continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

echo "🔄 Pulling latest changes..."
git pull

echo "🔨 Building bot container..."
docker-compose -f docker-compose.prod.yml build bot

echo "🚀 Restarting bot..."
docker-compose -f docker-compose.prod.yml up -d bot

echo "✅ Deploy completed!"
echo ""
echo "📋 View logs:"
echo "   docker logs shopbot-prod -f"
