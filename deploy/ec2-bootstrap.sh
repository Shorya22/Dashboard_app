#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04 EC2 instance. Run this ON the
# instance (paste over SSH, or `scp` this file up and run it there).
# See ../DEPLOY_EC2.md for the full walkthrough (security group, .env, etc).
set -euo pipefail

REPO_URL="https://github.com/Shorya22/Dashboard_app.git"
REPO_DIR="$HOME/Dashboard_app"

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"

sudo apt-get update
sudo apt-get install -y docker-compose-plugin git

if [ -d "$REPO_DIR" ]; then
  echo "Repo already exists at $REPO_DIR, skipping clone."
else
  git clone "$REPO_URL" "$REPO_DIR"
fi

cat <<EOF

Docker installed. Log out and back in (or run 'newgrp docker') so your
shell picks up the docker group membership, then:

  scp -i /path/to/key.pem .env ubuntu@<this-instance-ip>:$REPO_DIR/.env

...edit COMPOSE_PROFILES and JWT_SECRET_KEY in that .env as described in
DEPLOY_EC2.md, then:

  cd $REPO_DIR && docker compose up -d --build

EOF
