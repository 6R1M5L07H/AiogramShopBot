#!/bin/bash
set -e

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

echo "⚠️  PRODUCTION DEPLOYMENT"
echo "========================"
echo "This will deploy to PRODUCTION environment."
echo ""
echo "📍 Deploying branch: $CURRENT_BRANCH"
echo ""

read -p "Continue deployment? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

echo "🔄 Pulling latest changes from origin/$CURRENT_BRANCH..."
git pull origin $CURRENT_BRANCH

echo "🔨 Building bot container..."
docker-compose -f docker-compose.prod.yml build bot

echo "🚀 Restarting bot..."
docker-compose -f docker-compose.prod.yml up -d bot

echo "✅ Deploy completed!"
echo ""
echo "📋 View logs:"
echo "   docker logs shopbot-prod -f"
