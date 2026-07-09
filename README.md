# Bright Data stock screener

This project fetches a stock list page from finanzen.net, uses a Bright Data proxy when configured, and prints the names of stocks whose one-week change is at least 10% up or down.

## Setup

1. Create a virtual environment and activate it.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set the environment variables in your shell or in a .env file:
   ```env
   BRIGHTDATA_API_TOKEN=your-token
   BRIGHTDATA_PROXY_URL=http://your-proxy-host:port
   ```
   If you use Bright Data Web Unlocker, the proxy URL usually looks like:
   ```text
   http://brd-customer-<customer>-zone-unblocker:<token>@zproxy.lum-superproxy.io:22225
   ```

## Run

Use the included demo fixture:
```bash
python app.py --demo
```

Run against the live site:
```bash
python app.py --url https://www.finanzen.net/aktien/
```
