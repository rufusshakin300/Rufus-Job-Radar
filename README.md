# Rufus Job Radar — Python + Telegram

A free-first starter project that checks public job feeds, filters .NET/Dynamics 365 roles, deduplicates listings, and sends a Telegram digest.

## What it does / limitations

- Checks Remotive's public remote software-development API and Arbeitnow's public job-board API.
- Can check official Greenhouse and Lever company career-board APIs when you add company board slugs to the JSON config files.
- Filters for .NET/C#/ASP.NET, Dynamics 365/CRM, Power Platform, and related terms.
- Prioritizes Hyderabad, Bengaluru/Bangalore, India, and remote listings.
- Excludes obvious senior/lead/manager roles and sends up to 15 new matches per run.
- Keeps deduplication state in `state.json`; GitHub Actions cache attempts to carry this between scheduled runs.
- No paid AI API is needed.

Important: public feeds do not cover every Indian job site. Remotive is remote-only and its public API listings can be delayed by 24 hours; the source requires linking back to Remotive and identifying it as the source. Arbeitnow is not India-focused, so results may be sparse. The script cannot guarantee that every remote role accepts applicants located in India. Review the job page before applying. Some source URLs point to a board listing rather than a direct employer application form.

## 1. Create a Telegram bot

1. Open https://t.me/BotFather in Telegram.
2. Send `/newbot`, follow the prompts, and copy the bot token.
3. Open your bot's chat and press **Start**.
4. To find your chat ID, open this URL in a browser after replacing `<BOT_TOKEN>` with your token:
   `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
5. Find `message.chat.id` in the response. Do not share your bot token publicly or commit it to Git.

If `getUpdates` is empty, send another message to your bot and refresh.

## 2. Create a GitHub repository

1. Create a new repository at https://github.com/new. A private repository is fine.
2. Upload all files from this project, preserving the `.github/workflows/job-radar.yml` path.
3. In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.
4. Add:
   - `TELEGRAM_BOT_TOKEN` = the token from BotFather
   - `TELEGRAM_CHAT_ID` = your numeric Telegram chat ID
5. In **Settings → Actions → General**, confirm workflow permissions permit the workflow to read/write repository contents only if you later choose to commit state. This starter uses Actions cache for state and does not need write permission; the permission can be set to read-only.
6. Go to **Actions → Rufus Job Radar → Run workflow** to test immediately.
7. Check the Telegram chat. If successful, scheduled runs are set for 03:30 UTC (09:00 India Standard Time). GitHub scheduled runs can occasionally be delayed.

GitHub Actions has usage limits and policies that may change. Check https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions. A private repository on a free plan typically has included minutes; public repositories have different runner pricing rules. Verify your account's current limits.

## 3. Add official company career boards

Edit `greenhouse_boards.json` and `lever_boards.json`. Replace the example entry or remove it until you have valid company board slugs.

- Greenhouse board slug: often the value after `boards.greenhouse.io/` on a company's hosted job board. The public API used is `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs`.
- Lever site slug: often the value after `jobs.lever.co/`. The public API used is `https://api.lever.co/v0/postings/{slug}?mode=json`.

Only add company board slugs that you have verified. Not every employer uses these platforms. Do not add secrets to these files.

## 4. Run locally (optional)

Python 3.10+ recommended:

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

Set environment variables `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then run `python main.py`.

## Cost

- Python, Telegram bot creation, and the script: free.
- GitHub Actions: free within the current plan's included usage; check account billing and limits.
- Hosting outside GitHub Actions: optional and may cost money.
- AI API: not used by this starter.

## Security

Never commit your Telegram bot token or put it in source code. Use GitHub Actions repository secrets. If the token leaks, revoke it through BotFather and create a new one.
