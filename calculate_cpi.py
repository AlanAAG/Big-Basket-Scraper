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
    df = df.sort_values(['Date', 'Item_ID'])

    # Get unique dates
    dates = df['Date'].unique()
    if len(dates) == 0:
        return

    # Base Period (Day 1)
    base_date = dates[0]
    base_prices = df[df['Date'] == base_date][['Item_ID', 'Normalized_Unit_Price']]
    base_prices.columns = ['Item_ID', 'Base_Price']

    # Merge base prices into the main dataframe
    df = df.merge(base_prices, on='Item_ID', how='left')

    # Calculate Price Relatives (P_t / P_0 * 100)
    df['Price_Relative'] = (df['Normalized_Unit_Price'] / df['Base_Price']) * 100

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

    # Apply Weights
    category_indices['Weight'] = category_indices['Category'].map(category_weights)
    category_indices['Weighted_Index'] = category_indices['Category_Index'] * category_indices['Weight']

    # Aggregate by Date to get the Final CPI Index
    cpi_overall = category_indices.groupby('Date')['Weighted_Index'].sum().reset_index()
    cpi_overall.columns = ['Date', 'Overall_CPI']

    print("\nCategory-wise Indices:")
    pivot_categories = category_indices.pivot(index='Date', columns='Category', values='Category_Index')
    print(pivot_categories.to_string())

    print("\nOverall Daily Online CPI:")
    print(cpi_overall.to_string(index=False))
    
    return cpi_overall

if __name__ == "__main__":
    calculate_cpi()
