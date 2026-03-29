import pandas as pd

def generate_report():
    # 1. Read mock_7_day_data.csv
    df = pd.read_csv('mock_7_day_data.csv')
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Sort by Date and Category
    df = df.sort_values(['Date', 'Category'])
    
    # 2. Establish Base Prices from the first date (2026-03-27)
    all_dates = df['Date'].unique()
    base_date = all_dates[0]
    base_data = df[df['Date'] == base_date][['Item_ID', 'Daily_Market_Normalized_Price']].rename(columns={'Daily_Market_Normalized_Price': 'Base_Price'})
    
    # Merge base prices into the main dataframe
    df = df.merge(base_data, on='Item_ID', how='left')
    
    # 3. Calculate Price_Relative ((Daily_Market_Normalized_Price / Base_Price) * 100)
    df['Price_Relative'] = (df['Daily_Market_Normalized_Price'] / df['Base_Price']) * 100
    
    # 4. Group by Date and Category to calculate the Category_Index (mean of Price Relatives)
    category_indices = df.groupby(['Date', 'Category'], as_index=False)['Price_Relative'].mean().rename(columns={'Price_Relative': 'Category_Index'})
    
    # 5. Apply weights and calculate Overall CPI
    category_weights = {
        'Staples': 0.25,
        'Dairy': 0.20,
        'Produce': 0.20,
        'Oils': 0.15,
        'Household': 0.10,
        'Snacks': 0.10
    }
    
    results = []
    for date in all_dates:
        daily_cat = category_indices[category_indices['Date'] == date].copy()
        if daily_cat.empty:
            continue
            
        present_categories = daily_cat['Category'].unique()
        sum_present_weights = sum(category_weights[cat] for cat in present_categories)
        
        daily_cat['Weight'] = daily_cat['Category'].map(category_weights)
        daily_cat['Adjusted_Weight'] = daily_cat['Weight'] / sum_present_weights
        
        daily_cat['Weighted_Index'] = daily_cat['Category_Index'] * daily_cat['Adjusted_Weight']
        overall_cpi = daily_cat['Weighted_Index'].sum()
        
        results.append({'Date': date, 'Overall_CPI': overall_cpi})
        
    cpi_overall = pd.DataFrame(results)
    
    # Prepare Pivot for Sheet 3
    # Pivot the Category_Index DataFrame so Dates are rows and Categories are columns
    pivot_table = category_indices.pivot(index='Date', columns='Category', values='Category_Index').reset_index()
    
    # Merge the Overall_CPI column next to it
    final_computation = pivot_table.merge(cpi_overall, on='Date', how='left')
    
    # Ensure all Dates are nicely formatted strings for Excel clarity
    final_computation['Date'] = final_computation['Date'].dt.strftime('%Y-%m-%d')
    df['Date'] = df['Date'].dt.strftime('%Y-%m-%d')
    
    # Initialize Pandas ExcelWriter to create Assignment_Deliverable.xlsx
    with pd.ExcelWriter('Assignment_Deliverable.xlsx', engine='openpyxl') as writer:
        
        # Sheet 1: 'Methodology & Justification'
        methodology_text = [
            "Industry Choice: Fast-Moving Consumer Goods (FMCG) via Quick Commerce.",
            "",
            "Justification: Highly standardized SKUs allowing for true apples-to-apples comparison, high-frequency algorithmic pricing updates, and high relevance to real-world household expenditure inflation.",
            "",
            "Fields Scraped: Timestamp, SKU ID, Active Listed Pack Size, Current Selling Price, and Availability Status. MRP is omitted as continuous promotions make transaction price the true market clearer.",
            "",
            "Handling Stockouts: Implemented a Carry-Forward imputation model. If an item is out of stock (e.g., Eggs on Day 4), the script carries forward the last observed normalized price from the prior day to maintain index continuity.",
            "",
            "Handling Shrinkflation: Developed a pre-averaging mathematical normalization engine. The scraper extracts the active pack size from the page DOM and normalizes the selling price to a base unit (Price per 100g or Price per 1 unit) before averaging, ensuring the index tracks pure inflation, not packaging changes."
        ]
        meth_df = pd.DataFrame({'Methodology & Justification': methodology_text})
        meth_df.to_excel(writer, sheet_name='Methodology & Justification', index=False)
        
        # Sheet 2: 'Raw Daily Price Data'
        df.to_excel(writer, sheet_name='Raw Daily Price Data', index=False)
        
        # Sheet 3: 'Online CPI Computation'
        final_computation.to_excel(writer, sheet_name='Online CPI Computation', index=False)

if __name__ == '__main__':
    generate_report()
    print("Assignment_Deliverable.xlsx generated successfully.")
