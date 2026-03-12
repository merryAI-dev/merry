#!/bin/bash
# Merry production deploy script
# Usage: ./deploy.sh

set -e

PRODUCTION_DOMAIN="mysc-merry-inv.vercel.app"

echo "🚀 Deploying from web/ directory..."
cd "$(dirname "$0")/web"

DEPLOY_URL=$(npx vercel --prod 2>&1 | grep "Production:" | awk '{print $2}')

if [ -z "$DEPLOY_URL" ]; then
  echo "❌ Deploy failed - no production URL found"
  exit 1
fi

echo "✅ Deployed to: $DEPLOY_URL"
echo "🔗 Setting alias: $PRODUCTION_DOMAIN → $DEPLOY_URL"

npx vercel alias set "$DEPLOY_URL" "$PRODUCTION_DOMAIN"

echo "✅ Done! https://$PRODUCTION_DOMAIN is now live."
