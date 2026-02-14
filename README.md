# How to setup

1) Convert your instagram account to a business account

## Running Playwright locally and pushing to SRCF

Playwright should run on your local machine, not on SRCF.

### 1) Start the SRCF server

The server now accepts POST updates at `/update-queens-menu` and validates:

- `user_id` exists in `api/users.json`
- provided `access_token` matches the stored token
- stored token is unexpired

### 2) Run the local updater (on your machine)

Use:

`python3 -m api.push_menu_remote_cli --once`

This will:

- scrape the menu with Playwright locally
- send `menu_week` + `menu` to SRCF
- let SRCF post using the same token identity rules in `users.json`

Optional flags:

- `--remote-url https://tsg36.soc.srcf.net/update-queens-menu`
- `--mode auto|daily|weekly`
- `--interval-minutes 15` (without `--once`, runs continuously)