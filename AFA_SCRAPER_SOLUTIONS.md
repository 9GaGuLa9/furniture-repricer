# AFA Scraper - 403 Forbidden Solutions

## Problem
Your IP address is blocked by afastores.com (Cloudflare protection). This typically happens when:
- Using datacenter/cloud IPs (AWS, Azure, hosting providers)
- Multiple requests from same IP
- Geographic restrictions

## Solutions

### Option 1: Use a Proxy (Recommended for Production)
The scraper now supports proxy configuration.

1. **Get a proxy service** (recommended providers):
   - [Bright Data](https://brightdata.com) - residential proxies
   - [Oxylabs](https://oxylabs.io) - datacenter and residential
   - [SmartProxy](https://smartproxy.com) - residential
   - [ScraperAPI](https://scraperapi.com) - handles Cloudflare automatically

2. **Configure proxy in your code**:
```python
from app.scrapers.afa import scrape_afa

config = {
    'delay_min': 2.0,
    'delay_max': 4.0,
    'retry_attempts': 3,
    'timeout': 30,
    'proxies': {
        'http': 'http://username:password@proxy.example.com:8080',
        'https': 'http://username:password@proxy.example.com:8080'
    }
}

results = scrape_afa(config)
```

3. **Test the connection**:
```bash
python test_afa_connection.py
```

### Option 2: Use Selenium (Slower but Works)
Real browser bypasses most blocking mechanisms.

1. **Install dependencies**:
```bash
pip install selenium
```

2. **Download ChromeDriver**:
   - Visit https://chromedriver.chromium.org/
   - Download version matching your Chrome browser
   - Add to PATH or place in project folder

3. **Use Selenium scraper**:
```python
from app.scrapers.afa_selenium import scrape_afa_selenium

config = {
    'delay_min': 2.0,
    'delay_max': 4.0,
    'timeout': 30,
    'headless': True  # False to see browser window
}

results = scrape_afa_selenium(config)
```

4. **Test it**:
```bash
python -m app.scrapers.afa_selenium
```

### Option 3: Use VPN
Connect to a VPN and use the original scraper.

1. Connect to VPN (especially US-based)
2. Run the original scraper:
```bash
python -m app.scrapers.afa
```

### Option 4: Run from Different Network
If it works on your home computer, the issue is likely your current IP/network.

Run the scraper from:
- Home internet connection
- Different cloud provider
- Mobile hotspot
- Different VPN location

## Comparison of Solutions

| Solution | Speed | Cost | Setup Difficulty | Reliability |
|----------|-------|------|------------------|-------------|
| Proxy | Fast | $$$ | Easy | High |
| Selenium | Slow | Free | Medium | High |
| VPN | Fast | $-$$ | Easy | Medium |
| Different Network | Fast | Free | Easy | High |

## Testing Your Connection

Run the diagnostic tool to check if your IP is blocked:
```bash
python test_afa_connection.py
```

This will show:
- Homepage accessibility
- Products API accessibility
- Cloudflare detection
- IP block status

## Current Status

Your IP is **currently blocked** (403 Forbidden). You need to use one of the solutions above.

Working from your home computer suggests:
- Home IP is not blocked
- Current IP (datacenter/VPS) is blocked by Cloudflare

## Recommendations

**For Development:**
- Use Selenium (free, easy setup)

**For Production:**
- Use residential proxies (most reliable)
- Rotate IPs to avoid blocks
- Add longer delays between requests

**Quick Fix:**
- Connect to VPN
- Or run from home computer
