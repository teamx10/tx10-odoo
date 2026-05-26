# TX10 AI — E2E Tests (Playwright)

End-to-end browser tests for `tx10_ai` module.

## Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

## Run

```bash
# Docker must be running: ./docker-start.sh
npm test

# With browser visible
npm run test:headed

# With debug inspector
npm run test:debug

# Single test by title
npx playwright test -g "T-SYS"
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_URL` | `http://localhost:8069` | Odoo base URL |
| `ODOO_LOGIN` | `admin` | Admin username |
| `ODOO_PASSWORD` | `admin` | Admin password |

## Test IDs

| ID | What it tests |
|----|---------------|
| T-NAV | No Solar AI in navbar/systray |
| T-SYS | Systray click opens floating DM chat |
| T-DISC | Discuss sidebar shows TeamX10 AI DM |
| T-SET | Settings > Project has "TeamX10 AI Assistant" block, no "Solar AI" |
| T-ERR | Empty API key → bot replies with Ukrainian error (no silence) |
| T-ADM | Admin sees `— код: no_api_key` suffix in error reply |
