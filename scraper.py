import asyncio
import json
import os
import re
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

# Configuration
CONFIG_FILE = 'basket.json'
DATA_FILE = 'daily_cpi_tracker.csv'
GEOLOCATION = {"latitude": 28.6139, "longitude": 77.2090} # Central Delhi
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
EXTRA_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}
VIEWPORT = {"width": 1920, "height": 1080}
LOCALE = "en-IN"
TIMEZONE = "Asia/Kolkata"

def parse_weight(weight_str):
    """Parses weight string into grams or pieces."""
    if not weight_str:
        return None
    
    weight_str = weight_str.lower().strip()
    
    # Check for grams/kg/L/ml
    kg_match = re.search(r'(\d+\.?\d*)\s*(kg|l|liter)', weight_str)
    if kg_match:
        return float(kg_match.group(1)) * 1000
    
    g_match = re.search(r'(\d+\.?\d*)\s*(g|gm|ml|milliliter)', weight_str)
    if g_match:
        return float(g_match.group(1))
    
    # Check for pieces/units (e.g., 6 pcs, 6 pk)
    pc_match = re.search(r'(\d+)\s*(pcs?|pk|units?)', weight_str)
    if pc_match:
        return float(pc_match.group(1))
    
    return None

async def scrape_bigbasket(page, url):
    """Scrapes price and weight from BigBasket."""
    try:
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
        except PlaywrightTimeoutError:
            return None, None, "Timeout Error"
        await asyncio.sleep(2)
        
        title = await page.title()
        if "Access Denied" in title:
            return None, None, "Access Denied (Bot Detection)"

        h1_text = await page.inner_text('h1') if await page.query_selector('h1') else None
        
        # Price extraction
        price = None
        price_elements = await page.query_selector_all('span, div, p')
        for el in price_elements:
            try:
                text = await el.inner_text()
                if '₹' in text:
                    match = re.search(r'₹\s*(\d+\.?\d*)', text)
                    if match:
                        price = float(match.group(1))
                        break
            except:
                continue

        if price is None or not h1_text:
            return None, None, "OOS or Element Not Found"
            
        actual_weight = parse_weight(h1_text)
        return price, actual_weight, None
    except Exception as e:
        return None, None, str(e)

async def scrape_zepto(page, url):
    """Scrapes price and weight from Zepto."""
    try:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except PlaywrightTimeoutError:
            return None, None, "Timeout Error"
        await asyncio.sleep(5)
        
        title = await page.title()
        
        # Price from title fallback
        price = None
        title_match = re.search(r'Price\s*@\s*₹\s*(\d+\.?\d*)', title)
        if title_match:
            price = float(title_match.group(1))
            
        price_selector = 'span[data-testid="selling-price"], [class*="SellingPrice"]'
        weight_selector = 'span[data-testid="product-uom"], [class*="ProductUom"], [data-testid="product-net-quantity"]'
        
        if price is None:
            price_text = await page.inner_text(price_selector) if await page.query_selector(price_selector) else None
            if price_text:
                price = float(re.sub(r'[^\d.]', '', price_text))
        
        # Weight extraction
        weight_text = await page.inner_text(weight_selector) if await page.query_selector(weight_selector) else None
        if not weight_text:
            page_content = await page.inner_text('body')
            match = re.search(r'(Net Qty|Net Quantity):\s*(.*)', page_content, re.IGNORECASE)
            if match:
                weight_text = match.group(2)
            else:
                match = re.search(r'(\d+\s*(kg|g|pcs|pk|units|l|ml))', page_content, re.IGNORECASE)
                if match:
                    weight_text = match.group(1)

        if price is None or not weight_text:
            return None, None, "OOS or Element Not Found"
            
        actual_weight = parse_weight(weight_text)
        return price, actual_weight, None
    except Exception as e:
        return None, None, str(e)

async def initialization_mode(page, basket):
    """Discovers missing target weights using BigBasket URLs."""
    updated = False
    for item_id, details in basket.items():
        if details.get('target_weight_grams') is None or details.get('target_weight_grams') == 0:
            print(f"Initializing target weight for {item_id}...")
            # Try BigBasket first (Primary)
            _, weight, err = await scrape_bigbasket(page, details['bigbasket_url'])
            
            # Try Zepto as fallback (Secondary)
            if not weight:
                print(f"  BigBasket discovery failed, trying Zepto for {item_id}...")
                _, weight, err = await scrape_zepto(page, details['zepto_url'])
            
            if weight:
                details['target_weight_grams'] = weight
                updated = True
                print(f"  Discovered: {weight} units/grams")
            else:
                print(f"  Failed to discover weight for {item_id}: {err}")
    
    if updated:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(basket, f, indent=2)
        print(f"Updated {CONFIG_FILE} with discovered weights.")
    return basket

async def run_scraper(headless=True):
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        return

    with open(CONFIG_FILE, 'r') as f:
        basket = json.load(f)

    # Load yesterday's data for imputation
    prev_data = None
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        try:
            prev_data = pd.read_csv(DATA_FILE)
            if not prev_data.empty:
                prev_data['Date'] = pd.to_datetime(prev_data['Date'])
                latest_date = prev_data['Date'].max()
                prev_data = prev_data[prev_data['Date'] == latest_date]
        except:
            pass

    daily_results = []
    current_date = datetime.now().strftime('%Y-%m-%d')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            geolocation=GEOLOCATION,
            permissions=["geolocation"],
            user_agent=USER_AGENT,
            extra_http_headers=EXTRA_HEADERS,
            viewport=VIEWPORT,
            locale=LOCALE,
            timezone_id=TIMEZONE
        )
        page = await context.new_page()
        stealth_applier = Stealth()
        await stealth_applier.apply_stealth_async(page)

        # Step 2: Autonomous Weight Discovery
        # basket = await initialization_mode(page, basket)

        # Step 3: Scraping & Normalization Engine
        for item_id, details in basket.items():
            print(f"Scraping {item_id}...")
            
            # Robust piece-based detection
            if "pcs" in item_id.lower() or "pk" in item_id.lower():
                base_unit = 1
            else:
                base_unit = 100

            # Platform Scrapes
            bb_price, _, _ = await scrape_bigbasket(page, details['bigbasket_url'])
            z_price, _, _ = await scrape_zepto(page, details['zepto_url'])

            # Normalize Platform Prices Individually
            normalized_prices = []
            
            # CRITICAL: Use verified target_weight_grams from JSON for all math
            target_weight = details.get('target_weight_grams')
            
            if target_weight:
                if bb_price:
                    norm_bb = (bb_price / target_weight) * base_unit
                    normalized_prices.append(norm_bb)
                
                if z_price:
                    norm_z = (z_price / target_weight) * base_unit
                    normalized_prices.append(norm_z)

            # Market Averaging
            if normalized_prices:
                daily_market_norm = sum(normalized_prices) / len(normalized_prices)
                method = "Scraped"
            elif prev_data is not None and item_id in prev_data['Item_ID'].values:
                # Imputation
                daily_market_norm = prev_data.loc[prev_data['Item_ID'] == item_id, 'Daily_Market_Normalized_Price'].values[0]
                method = "Imputed (Carry Forward)"
            else:
                daily_market_norm = None
                method = "Failed"

            daily_results.append({
                'Date': current_date,
                'Category': details['category'],
                'Item_ID': item_id,
                'Weight_Percentage': details['weight_percentage'],
                'Target_Weight': target_weight,
                'Daily_Market_Normalized_Price': daily_market_norm,
                'Method': method
            })

        await browser.close()

    # Save to CSV (Anti-duplication logic)
    df = pd.DataFrame(daily_results)
    
    if os.path.exists(DATA_FILE) and os.path.getsize(DATA_FILE) > 0:
        try:
            existing_df = pd.read_csv(DATA_FILE)
            if 'Date' in existing_df.columns:
                existing_df = existing_df[existing_df['Date'] != current_date]
            final_df = pd.concat([existing_df, df], ignore_index=True)
            final_df.to_csv(DATA_FILE, index=False)
        except:
             df.to_csv(DATA_FILE, index=False)
    else:
        df.to_csv(DATA_FILE, index=False)
    
    print(f"Finished scraping. Results saved to {DATA_FILE}")

if __name__ == "__main__":
    asyncio.run(run_scraper())
