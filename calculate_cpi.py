import pandas as pd
import os

DATA_FILE = 'daily_cpi_tracker.csv'

def calculate_cpi():
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found. Run scraper.py first.")
        return

    df = pd.read_csv(DATA_FILE)
    if df.empty:
        print("Error: CSV is empty.")
        return

    # Ensure Date is sorted
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(['Date', 'Category'])

    # Get unique dates
    all_dates = df['Date'].unique()
    if len(all_dates) == 0:
        return

    # Base Period (Day 1)
    # We take the first date as the base. 
    # To ensure Base = 100, we need the base prices for all items that have data on Day 1.
    base_date = all_dates[0]
    base_data = df[df['Date'] == base_date][['Item_ID', 'Daily_Market_Normalized_Price']]
    base_data.columns = ['Item_ID', 'Base_Price']

    # Merge base prices into the main dataframe
    df = df.merge(base_data, on='Item_ID', how='left')

    # Calculate Price Relatives (P_t / P_0 * 100)
    # Only calculate if both prices are valid
    df = df[df['Daily_Market_Normalized_Price'].notna() & df['Base_Price'].notna()]
    df['Price_Relative'] = (df['Daily_Market_Normalized_Price'] / df['Base_Price']) * 100

    # Group by Date and Category to get Category Index (Arithmetic Mean of item relatives)
    category_indices = df.groupby(['Date', 'Category'])['Price_Relative'].mean().reset_index()
    category_indices.columns = ['Date', 'Category', 'Category_Index']

    # Define Category Weights
    category_weights = {
        'Staples': 0.25,
        'Dairy': 0.20,
        'Produce': 0.20,
        'Oils': 0.15,
        'Household': 0.10,
        'Snacks': 0.10
    }

    # Phase 4: Mathematical Integrity via Dynamic Weight Re-Balancing
    results = []
    for date in all_dates:
        daily_cat = category_indices[category_indices['Date'] == date].copy()
        if daily_cat.empty:
            continue
            
        # 1. Sum the designated weights of the categories that have data
        present_categories = daily_cat['Category'].unique()
        sum_present_weights = sum(category_weights[cat] for cat in present_categories)
        
        # 2. Re-balance weights (Adjusted_Weight = Original_Weight / sum_present_weights)
        daily_cat['Adjusted_Weight'] = daily_cat['Category'].map(category_weights) / sum_present_weights
        
        # 3. Final Computation: Weight * Category_Index
        daily_cat['Weighted_Index'] = daily_cat['Category_Index'] * daily_cat['Adjusted_Weight']
        
        overall_cpi = daily_cat['Weighted_Index'].sum()
        results.append({'Date': date, 'Overall_CPI': overall_cpi})
        
        # Log for debugging
        if date == base_date:
            print(f"Day 1 Re-balancing Check: Sum of weights = {sum_present_weights:.2f}")

    cpi_overall = pd.DataFrame(results)

    print("\nOverall Daily Online CPI (Fixed Architecture):")
    print(cpi_overall.to_string(index=False))
    
    # Category-wise breakdown for the latest date
    if not category_indices.empty:
        latest_date = category_indices['Date'].max()
        print(f"\nCategory Indices for {latest_date.strftime('%Y-%m-%d')}:")
        print(category_indices[category_indices['Date'] == latest_date][['Category', 'Category_Index']].to_string(index=False))

    return cpi_overall

if __name__ == "__main__":
    calculate_cpi()
