# Deploying LeadScout to a VPS

A simple guide to run LeadScout on any Linux VPS (Ubuntu/Debian shown). Two
options: **Docker** (recommended) or **bare Python + systemd**. Then an optional
**Nginx + HTTPS** reverse proxy.

---

## 0. Requirements

- A VPS with Ubuntu 22.04+ (DigitalOcean, Hetzner, Linode, etc.).
- A domain name pointing at the server (optional, needed for HTTPS).
- SSH access.

---

## Option A — Docker (recommended)

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER    # log out/in so this takes effect
```

### 2. Get the code

```bash
git clone <your-repo-url> leadscout
cd leadscout
cp .env.example .env
# edit .env — set USER_AGENT to include your email
nano .env
```

### 3. Run

```bash
docker compose up --build -d
```

The app is now on `http://<server-ip>:8000`. The database persists in `./data`.

### Updating

```bash
git pull
docker compose up --build -d
```

### Logs / stop

```bash
docker compose logs -f
docker compose down
```

---

## Option B — Bare Python + systemd

### 1. Install Python & clone

```bash
sudo apt update && sudo apt install -y python3-venv git
git clone <your-repo-url> leadscout && cd leadscout
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env
```

### 2. Create a systemd service

```bash
sudo tee /etc/systemd/system/leadscout.service >/dev/null <<'EOF'
[Unit]
Description=LeadScout
After=network.target

[Service]
WorkingDirectory=/home/YOURUSER/leadscout
EnvironmentFile=/home/YOURUSER/leadscout/.env
ExecStart=/home/YOURUSER/leadscout/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
User=YOURUSER

[Install]
WantedBy=multi-user.target
EOF
```

Replace `YOURUSER`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now leadscout
sudo systemctl status leadscout
```

---

## Optional — Nginx reverse proxy + HTTPS

Serve on ports 80/443 with a free Let's Encrypt certificate.

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

Create `/etc/nginx/sites-available/leadscout`:

```nginx
server {
    server_name leads.example.com;   # your domain

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

> If you used Docker, keep the `-p 8000:8000` mapping; the proxy still targets
> `127.0.0.1:8000`. For extra safety you can bind Docker to localhost only by
> changing the compose port mapping to `"127.0.0.1:8000:8000"`.

Enable it and get a certificate:

```bash
sudo ln -s /etc/nginx/sites-available/leadscout /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d leads.example.com
```

Certbot rewrites the config for HTTPS and sets up auto-renewal.

---

## Firewall (optional but recommended)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'   # or: sudo ufw allow 8000  (Docker without proxy)
sudo ufw enable
```

---

## Backups

The entire database is a single SQLite file. Back it up by copying it:

```bash
cp data/leadscout.db data/leadscout-$(date +%F).db
```

---

## Scaling / heavy use

The public Nominatim and Overpass servers have fair-use limits. If you run many
searches:

- Set a real `USER_AGENT` (with contact email) in `.env`.
- Lower `ANALYZE_CONCURRENCY` if you get rate-limited.
- For serious volume, **self-host** Nominatim and an Overpass instance and point
  `NOMINATIM_URL` / `OVERPASS_URLS` at them.
```
