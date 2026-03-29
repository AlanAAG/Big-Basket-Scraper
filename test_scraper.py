import asyncio
from scraper import scrape_bigbasket, scrape_zepto, GEOLOCATION, USER_AGENT
from playwright.async_api import async_playwright

async def test_single_item():
    url_bb = "https://www.bigbasket.com/pd/30006887/aashirvaad-atta-whole-wheat-1-kg-pouch/"
    url_zepto = "https://www.zepto.com/pn/superior-mp-wheat-atta-0-maida-aashirvaad/pvid/56d997f6-b45a-48bf-823d-c9b5acd6ac8f"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            geolocation=GEOLOCATION,
            permissions=["geolocation"],
            user_agent=USER_AGENT
        )
        page = await context.new_page()
        
        print(f"Testing BigBasket: {url_bb}")
        bb_price, bb_weight, bb_err = await scrape_bigbasket(page, url_bb)
        if bb_err:
            print(f"  BB Error: {bb_err}")
        else:
            print(f"  BB Price: ₹{bb_price} (Scraped Weight: {bb_weight})")
            
        print(f"\nTesting Zepto: {url_zepto}")
        z_price, z_weight, z_err = await scrape_zepto(page, url_zepto) 
        if z_err:
            print(f"  Zepto Error: {z_err}")
        else:
            print(f"  Zepto Price: ₹{z_price} (Scraped Weight: {z_weight})")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_single_item())
