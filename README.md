# Portfolio Tracker

A self-hosted crypto portfolio tracker that monitors Solana and EVM wallet balances, takes screenshots of wallet pages, and emails you a monthly report.

## Features

- **Multi-chain balance tracking** — Solana + Ethereum, Polygon, BSC, Arbitrum, Optimism, Base, Avalanche
- **Automatic screenshots** — Captures wallet dashboard pages using Playwright
- **Monthly email reports** — Sends balance summaries + screenshots on the 29th of each month
- **Web UI** — Manage wallets, view balances, capture screenshots, and configure settings
- **CLI** — Run captures and emails from the command line
- **Dual email support** — Resend API (recommended) or Gmail SMTP

## What You Need to Sign Up For

### 1. Resend (for email reports)
- Sign up at [resend.com](https://resend.com)
- Get your API key from the [Resend dashboard](https://resend.com/api-keys)
- **Optional:** Add and verify a custom domain in Resend for branded emails. Without a domain, you can only send to the email address on your Resend account.

### 2. Railway (for hosting)
- Sign up at [railway.app](https://railway.app)
- This is where the app runs 24/7 so it can send monthly reports on schedule
- You'll deploy directly from your GitHub repo

### 3. GitHub (to store the code)
- Fork or clone this repo to your own GitHub account
- Railway connects to your GitHub repo for automatic deploys

## Deployment (Railway)

### Step 1: Push to GitHub
Fork this repo or push it to your own GitHub account.

### Step 2: Create a Railway Project
1. Go to [railway.app](https://railway.app) and create a new project
2. Select **Deploy from GitHub repo**
3. Pick your forked repository

### Step 3: Set Environment Variables
In Railway, go to your service → **Variables** and add:

| Variable | Required | Description |
|---|---|---|
| `RESEND_API_KEY` | Yes | Your Resend API key |
| `RESEND_FROM` | No | Sender address (defaults to `Portfolio Tracker <noreply@yourdomain.com>`) |

### Step 4: Expose the Web UI
1. In your Railway service, go to **Settings** → **Networking**
2. Click **Generate Domain** to get a public URL
3. Visit the URL to access the web dashboard

### Step 5: Add Your Wallets
1. Open the web UI
2. Go to the **URLs** tab
3. Paste wallet addresses (Solana or EVM) or DeBank/Zerion/Solscan URLs
4. Go to **Settings** and enter the email address you want reports sent to

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set your Resend API key
export RESEND_API_KEY=re_your_key_here

# Start the web server
python main.py web
```

Then open [http://localhost:5000](http://localhost:5000).

### CLI Commands

```bash
python main.py web         # Start web server (default)
python main.py capture     # Take screenshots now
python main.py email       # Capture screenshots and email report
python main.py schedule    # Run the monthly scheduler
python main.py list        # List configured wallet URLs
```

## How It Works

- **Balances** are fetched from public APIs (Solscan, Jupiter, CoinGecko, Ankr, Blockscout, etc.) with multiple fallback strategies
- **Screenshots** are taken using Playwright with stealth mode to handle Cloudflare-protected sites
- **Monthly reports** are triggered by a background scheduler on the **29th of each month at 5:00 UTC**
- **Email** is sent via the Resend API (or Gmail SMTP if configured in settings)

## Project Structure

```
app.py              # Flask web server + API endpoints
main.py             # CLI entry point
config.json         # User configuration (wallets, email settings)
Dockerfile          # Container setup (Playwright + Python)
requirements.txt    # Python dependencies
src/
  config.py         # Configuration management
  balances.py       # Multi-chain balance fetching
  screenshots.py    # Playwright screenshot automation
  emailer.py        # Email sending (Resend / SMTP)
  scheduler.py      # Monthly job scheduler
templates/
  index.html        # Web dashboard UI
```

## Notes

- The app has **no authentication** — it's meant to be self-hosted for personal use. Don't share your Railway URL publicly.
- Wallet addresses are public data, but your email settings are stored in `config.json` on the server.
- The free tier of Railway gives you 500 hours/month which is enough to run this 24/7 on a single service.
- Resend's free tier allows 100 emails/day — more than enough for monthly reports.
