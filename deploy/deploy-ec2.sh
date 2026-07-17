#!/usr/bin/env bash
# Fast redeploy: push your local changes to GitHub first (git push), then
# run this to pull + rebuild on the EC2 instance. See ../DEPLOY_EC2.md.
#
# Usage:
#   EC2_HOST=ubuntu@<public-ip> EC2_KEY=/path/to/key.pem ./deploy/deploy-ec2.sh
set -euo pipefail

EC2_HOST="${EC2_HOST:?set EC2_HOST=ubuntu@<ec2-public-ip>}"
EC2_KEY="${EC2_KEY:?set EC2_KEY=/path/to/key.pem}"
REMOTE_DIR="${REMOTE_DIR:-~/Dashboard_app}"

ssh -i "$EC2_KEY" "$EC2_HOST" \
  "cd $REMOTE_DIR && git pull && docker compose up -d --build --force-recreate"
