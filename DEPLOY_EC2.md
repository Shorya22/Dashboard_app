# Deploy to AWS EC2 — Quick Reference

## 1. Launch instance (console)

- AMI: Ubuntu LTS, 64-bit (x86)
- Instance type: `c7i-flex.large` (or `t3.small` if no credits)
- Key pair: create/select, `chmod 400 key.pem` locally
- Security group inbound — add these as **Custom TCP / Type** rules
  explicitly, don't rely on the wizard's HTTP/HTTPS checkboxes (easy to
  leave those checked instead and end up with 80/443 open but 8080
  missing, which is a silent "site can't be reached" with no error on
  the server side):
  - SSH — Type: SSH, Port 22, Source: Anywhere
  - **Type: Custom TCP, Port range: 8080, Source: Anywhere** ← the actual
    app port, easy to miss
  - Leave HTTP (80) / HTTPS (443) unchecked — nothing listens on them
- Launch → note the **Public IPv4**
- **If the app doesn't load after deploying**: go to the instance's
  Security Group → Inbound rules and confirm the 8080 row actually
  exists (`EC2 → Security Groups → <group> → Inbound rules`). This was
  the exact issue the first time through — HTTP/HTTPS were checked by
  habit and 8080 never got added.

## 2. SSH in

```bash
ssh -i "/path/to/key.pem" ubuntu@<PUBLIC_IP>
```

(Quote the key path if it has spaces.)

## 3. First-time server setup

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
sudo apt-get update && sudo apt-get install -y docker-compose-plugin git

git clone https://github.com/Shorya22/Dashboard_app.git
cd Dashboard_app
git checkout dev   # docker-compose.yml only exists on dev, not master
```

## 4. Copy `.env` to server

From your Mac, in a separate terminal:

```bash
scp -i "/path/to/key.pem" "/Users/shoryasharma/AI Projects/Dashboard_app/.env" ubuntu@<PUBLIC_IP>:~/Dashboard_app/.env
```

On the server, edit `.env`:

```bash
nano ~/Dashboard_app/.env
```

- Remove/blank `COMPOSE_PROFILES=quick`
- Replace `JWT_SECRET_KEY` with output of `openssl rand -hex 32`

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

## 5. First deploy

```bash
cd ~/Dashboard_app
docker compose up -d --build
docker compose ps
```

**If the build dies with `failed to execute bake: signal: killed`**: that's
an out-of-memory kill — Compose builds both images (pandas/numpy install +
npm/vite build) in parallel, which can exceed 4GB RAM. Fix:

```bash
# 1. Add 2GB swap (one-time, cheap insurance)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. Build one image at a time instead of both at once
docker compose build backend
docker compose build frontend
docker compose up -d
```

Visit: `http://<PUBLIC_IP>:8080`

## 6. Every time you update code (the loop)

```
local change → git push → git pull on EC2 → docker compose up -d --build --force-recreate
```

**On the server:**
```bash
cd ~/Dashboard_app
git pull
docker compose up -d --build --force-recreate
```

**Or, one command from your Mac** (uses `deploy/deploy-ec2.sh`):
```bash
EC2_HOST=ubuntu@<PUBLIC_IP> EC2_KEY="/path/to/key.pem" ./deploy/deploy-ec2.sh
```

## Useful checks

```bash
docker compose ps                 # container status
docker compose logs -f backend    # tail backend logs
docker compose restart backend    # pick up new data files without rebuild
```
