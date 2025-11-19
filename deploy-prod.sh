#!/bin/bash
set -e

# Configure deployment branch
DEPLOY_BRANCH="master"

echo "⚠️  PRODUCTION DEPLOYMENT"
echo "========================"
echo "This will deploy to PRODUCTION environment."
echo ""

# Show current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "📍 Current branch: $CURRENT_BRANCH"
echo "🎯 Target branch:  $DEPLOY_BRANCH"
echo ""

# Warn if not on deploy branch
if [[ "$CURRENT_BRANCH" != "$DEPLOY_BRANCH" ]]; then
    echo "⚠️  WARNING: You are NOT on the $DEPLOY_BRANCH branch!"
    echo "   Current: $CURRENT_BRANCH"
    echo "   Expected: $DEPLOY_BRANCH"
    echo ""
    read -p "Switch to $DEPLOY_BRANCH and continue? (yes/no): " -r
    echo ""
    if [[ $REPLY =~ ^[Yy]es$ ]]; then
        echo "🔀 Switching to $DEPLOY_BRANCH..."
        git checkout $DEPLOY_BRANCH
    else
        echo "❌ Deployment cancelled."
        exit 1
    fi
fi

read -p "Continue deployment? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "❌ Deployment cancelled."
    exit 1
fi

echo "🔄 Pulling latest changes from origin/$DEPLOY_BRANCH..."
git pull origin $DEPLOY_BRANCH

echo "🔨 Building bot container..."
docker-compose -f docker-compose.prod.yml build bot

echo "🚀 Restarting bot..."
docker-compose -f docker-compose.prod.yml up -d bot

echo "✅ Deploy completed!"
echo ""
echo "📋 View logs:"
echo "   docker logs shopbot-prod -f"
