import asyncio
import json
import os
import re
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright

# Configuration
CONFIG_FILE = 'basket.json'
DATA_FILE = 'daily_cpi_tracker.csv'
GEOLOCATION = {"latitude": 19.0760, "longitude": 72.8777} # Mumbai
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def parse_weight(weight_str):
    """Parses weight string into grams or pieces."""
    if not weight_str:
        return None
    
    weight_str = weight_str.lower().strip()
    
    # Check for grams/kg
    kg_match = re.search(r'(\d+\.?\d*)\s*kg', weight_str)
    if kg_match:
        return float(kg_match.group(1)) * 1000
    
    g_match = re.search(r'(\d+\.?\d*)\s*g', weight_str)
    if g_match:
        return float(g_match.group(1))
    
    # Check for pieces/units (e.g., 6 pcs, 6 pk)
    pc_match = re.search(r'(\d+)\s*(pcs?|pk|units?)', weight_str)
    if pc_match:
        return float(pc_match.group(1))
    
    return None

async def scrape_bigbasket(page, url, target_weight):
    """Scrapes price and weight from BigBasket."""
    try:
        # Stealth init script
        await page.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
        
        await page.goto(url, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2) # Extra wait for dynamic content
        
        title = await page.title()
        if "Access Denied" in title:
            return None, "Access Denied (Bot Detection)"

        # Weight is usually in the H1 title
        h1_text = await page.inner_text('h1') if await page.query_selector('h1') else None
        
        # Price extraction
        price = None
        
        # Try finding ₹ in the page
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

        if price is None and h1_text:
            # Try to find price in title if text fails? BB usually doesn't have it in title like Zepto
            pass

        if price is None or not h1_text:
            return None, "OOS or Element Not Found"
            
        actual_weight = parse_weight(h1_text)
        if actual_weight != target_weight:
            return None, f"Weight Mismatch: {actual_weight} != {target_weight}"
            
        return price, None
    except Exception as e:
        return None, str(e)

async def scrape_zepto(page, url, target_weight):
    """Scrapes price and weight from Zepto."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5) # Zepto needs time to load prices
        
        title = await page.title()
        
        # Zepto often has price in the title: "... Price @ ₹306 ..."
        price = None
        title_match = re.search(r'Price\s*@\s*₹\s*(\d+\.?\d*)', title)
        if title_match:
            price = float(title_match.group(1))
            
        # Selectors (Verified)
        price_selector = 'span[data-testid="selling-price"], [class*="SellingPrice"]'
        weight_selector = 'span[data-testid="product-uom"], [class*="ProductUom"], [data-testid="product-net-quantity"]'
        
        if price is None:
            price_text = await page.inner_text(price_selector) if await page.query_selector(price_selector) else None
            if price_text:
                price = float(re.sub(r'[^\d.]', '', price_text))
        
        # Weight extraction
        weight_text = await page.inner_text(weight_selector) if await page.query_selector(weight_selector) else None
        if not weight_text:
            # Check for "Net Qty" or "1 pack" in title
            # Title example: "Buy Superior MP Wheat Atta... Online - Price @ ₹306"
            # The title doesn't always have weight. Let's check body.
            page_content = await page.inner_text('body')
            match = re.search(r'(Net Qty|Net Quantity):\s*(.*)', page_content, re.IGNORECASE)
            if match:
                weight_text = match.group(2)
            else:
                # Last resort: search for "5 kg" or similar in body
                # This is risky, but better than nothing
                match = re.search(r'(\d+\s*(kg|g|pcs|pk|units))', page_content, re.IGNORECASE)
                if match:
                    weight_text = match.group(1)

        if price is None or not weight_text:
            return None, "OOS or Element Not Found"
            
        actual_weight = parse_weight(weight_text)
        if actual_weight != target_weight:
            return None, f"Weight Mismatch: {actual_weight} != {target_weight}"
            
        return price, None
    except Exception as e:
        return None, str(e)

async def main():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        return

    with open(CONFIG_FILE, 'r') as f:
        basket = json.load(f)

    # Load yesterday's data for imputation
    prev_data = None
    is_day_1 = not os.path.exists(DATA_FILE)
    if not is_day_1:
        prev_data = pd.read_csv(DATA_FILE)
        if not prev_data.empty:
            prev_data['Date'] = pd.to_datetime(prev_data['Date'])
            latest_date = prev_data['Date'].max()
            prev_data = prev_data[prev_data['Date'] == latest_date]

    daily_results = []
    current_date = datetime.now().strftime('%Y-%m-%d')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            geolocation=GEOLOCATION,
            permissions=["geolocation"],
            user_agent=USER_AGENT
        )
        page = await context.new_page()

        for item_id, details in basket.items():
            print(f"Scraping {item_id}...")
            
            # Scrape BigBasket
            bb_price, bb_err = await scrape_bigbasket(page, details['bigbasket_url'], details['target_weight_grams'])
            if bb_err:
                print(f"  BigBasket Error for {item_id}: {bb_err}")
            
            # Scrape Zepto
            z_price, z_err = await scrape_zepto(page, details['zepto_url'], details['target_weight_grams'])
            if z_err:
                print(f"  Zepto Error for {item_id}: {z_err}")
                
            # Logic for Daily Price
            valid_prices = [p for p in [bb_price, z_price] if p is not None]
            
            avg_price = None
            method = "Failed"
            
            if valid_prices:
                avg_price = sum(valid_prices) / len(valid_prices)
                method = "Scraped"
            elif prev_data is not None and item_id in prev_data['Item_ID'].values:
                # Imputation (Carry Forward)
                avg_price = prev_data.loc[prev_data['Item_ID'] == item_id, 'Avg_Selling_Price'].values[0]
                method = "Imputed (Carry Forward)"
            elif is_day_1:
                print(f"  CRITICAL ERROR: Item {item_id} unavailable on Day 1. No historical data to carry forward.")
                print(f"  ACTION REQUIRED: Check URL or manually replace item in {CONFIG_FILE}.")
                method = "Failed (Day 1 OOS)"

            # Normalization (Price per 100g or 1 unit)
            # Basket target: Staples/Produce/Oils usually grams, Eggs/Banana are pieces
            base_unit = 1 if details['target_weight_grams'] == 6 else 100
            
            normalized_price = None
            if avg_price is not None:
                normalized_price = (avg_price / details['target_weight_grams']) * base_unit

            daily_results.append({
                'Date': current_date,
                'Category': details['category'],
                'Item_ID': item_id,
                'Weight_Percentage': details['weight_percentage'],
                'Target_Weight': details['target_weight_grams'],
                'Avg_Selling_Price': avg_price,
                'Normalized_Unit_Price': normalized_price,
                'Method': method
            })

        await browser.close()

    # Save to CSV
    df = pd.DataFrame(daily_results)
    if os.path.exists(DATA_FILE):
        df.to_csv(DATA_FILE, mode='a', header=False, index=False)
    else:
        df.to_csv(DATA_FILE, index=False)
    
    print(f"Finished scraping. Results saved to {DATA_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
