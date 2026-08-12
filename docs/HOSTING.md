# Hosting LeadScout online (auto-deploy)

## Can it run on Cloudflare Workers? No.

Cloudflare **Workers** run JavaScript in a sandbox with **no filesystem, no
long-running server, and no raw sockets**. LeadScout is a **Python FastAPI
server** that needs a SQLite file, long-running website scans, and (locally)
SMTP. None of that can run on Workers. There is no config or "embed" that
changes this — it would require rewriting the whole backend in JavaScript.

The **only** Cloudflare product that can run this app is **Cloudflare
Containers** (it runs your Docker image, fronted by a Worker). Caveats:
- It requires a **paid Workers plan** (Containers is not on the free tier).
- Cloudflare's network **blocks SMTP**, so **email sending won't work there** —
  keep sending on your local Mac app, or use an HTTP email API instead.

If you have the paid plan and want Cloudflare specifically, install `wrangler`,
follow Cloudflare's current "Containers" docs, and point it at the `Dockerfile`
in this repo. Auto-deploy on push is done with a GitHub Action that runs
`wrangler deploy` using a `CLOUDFLARE_API_TOKEN` repo secret.

## Recommended: keep it local
LeadScout sends from **your** Gmail and runs long scans. Running it as the Mac
app on your own machine is free, private, and safe. You only need hosting if you
want to reach it from other devices.

## Easiest real auto-deploy (free): Render
This repo includes `render.yaml`, so every `git push` redeploys automatically.

1. Push this repo to GitHub.
2. Create a free account at https://render.com → **New → Blueprint** → pick your repo.
3. Render reads `render.yaml` and builds the `Dockerfile`.
4. In the dashboard, set the environment variables (they're secrets, not in git):
   - **`APP_PASSWORD`** — REQUIRED. A password you choose; the app asks for it.
   - `SELLER_NAME`, `SELLER_COMPANY`, `SELLER_PHONE`, `SELLER_EMAIL`, `USER_AGENT`.
   - Leave `SELLER_EMAIL_APP_PASSWORD` **unset** (SMTP is blocked on most hosts).
5. Deploy. Every future push auto-deploys.

(Alternatives that also auto-deploy a Dockerfile: **Fly.io** `fly deploy`, **Railway**.)

## ⚠️ Always set a password before hosting
LeadScout has **no user login** by design. Set the **`APP_PASSWORD`** environment
variable before any public deploy — otherwise anyone who finds the URL can run
scans and (if SMTP worked) send email in your name. With `APP_PASSWORD` set, the
browser asks for it on every visit. Locally (the Mac app) leave it blank.
