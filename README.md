# How to setup

1) Convert your instagram account to a business account

## Cloudflare-first publishing flow

Playwright runs locally. Images and menu JSON are published to Cloudflare R2.

### Required environment variables

- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_R2_ACCESS_KEY_ID`
- `CLOUDFLARE_R2_SECRET_ACCESS_KEY`
- `CLOUDFLARE_R2_BUCKET`
- `CLOUDFLARE_R2_PUBLIC_BASE_URL` (public bucket/custom domain, e.g. `https://pub-xxx.r2.dev`)
- `CLOUDFLARE_R2_PREFIX` (optional, default `queens-menu-bot`)

Instagram token/user identity still comes from `api/users.json`.

### Run the publisher (local machine)

Use:

`python3 -m api.publish_cli --once --mode auto`

This will:

- scrape the menu with Playwright locally
- upload menu JSON to Cloudflare R2 as a public API
- upload post images temporarily to Cloudflare R2 for Instagram fetch
- publish to Instagram using the existing token from `users.json`
- delete temporary image objects after posting

Optional flags:

- `--mode auto|daily|weekly`
- `--interval-minutes 15` (without `--once`, runs continuously)

### Public menu API URLs

Uploaded on every update:

- `.../<prefix>/api/menu/latest.json`
- `.../<prefix>/api/menu/week-YYYY-MM-DD.json`