# 🚀 Quick Commerce CPI Tracker & Scraper

A robust, anti-bot grocery price tracking system designed to calculate a daily **Consumer Price Index (CPI)** across major Indian quick-commerce platforms (**BigBasket** and **Zepto**). This project ensures mathematical integrity against shrinkflation, stockouts, and algorithmic pricing.

---

## 🌟 Key Features

### 1. **Anti-Bot & Stealth Scraping**
*   **Playwright Stealth**: Bypasses Cloudflare/WAF defenses using `playwright-stealth`.
*   **Dynamic Fingerprinting**: Injects realistic user agents, viewports, and localized headers (`en-IN`, `Asia/Kolkata`).
*   **Graceful Timeouts**: Implements strict 60-second navigation limits to prevent hangs during high-latency periods.

### 2. **Shrinkflation-Proof Normalization**
*   **Verified Weights**: Uses a verified `target_weight_grams` from `basket.json` as the source of truth.
*   **Pre-Averaging Engine**: Automatically parses active pack sizes (e.g., "5x125g", "6 pcs", "1kg") from the DOM and normalizes prices to a base unit (Price per 100g or Price per 1 unit) *before* index calculation.

### 3. **Mathematical CPI Integrity**
*   **Laspeyres-Logic**: Calculates daily price relatives against a fixed Day 1 base price.
*   **Dynamic Weight Re-balancing**: Automatically adjusts category weights (Staples, Dairy, Produce, etc.) if data is missing, ensuring the baseline index remains a perfect **100.0**.
*   **Carry-Forward Imputation**: If an item is out of stock on both platforms, the system automatically carries forward the last known price to maintain index continuity.

---

## 📂 Project Architecture

### Core Engine
*   `scraper.py`: The live scraping orchestrator. Handles platform navigations, price extraction, and data persistence to the local tracker.
*   `calculate_cpi.py`: Periodically processes the tracking data to derive the daily overall and categorical CPI indices.
*   `basket.json`: The central configuration database. Contains item IDs, category weights, target units, and platform-specific URLs.

### University Assignment Module
*   `generate_assignment_report.py`: A standalone utility that ingests a 7-day mock dataset (`mock_7_day_data.csv`) and generates a professional **3-sheet Excel deliverable** (`Assignment_Deliverable.xlsx`).
*   **Live Excel Formulas**: Unlike typical exports, the generated Excel file contains **native Excel formulas** (`VLOOKUP`, `AVERAGEIFS`, `IFERROR`) so the methodology can be audited directly by instructors.

---

## 🛠️ Installation & Setup

### Prerequisites
*   Python 3.9+
*   Node.js (for Playwright binaries)

### Installation
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/AlanAAG/Big-Basket-Scraper.git
    cd Big-Basket-Scraper
    ```
2.  **Create and Activate Virtual Environment**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Mac/Linux
    # venv\Scripts\activate   # Windows
    ```
3.  **Install Dependencies**:
    ```bash
    pip install playwright playwright-stealth pandas openpyxl
    ```
4.  **Install Playwright Browsers**:
    ```bash
    playwright install chromium
    ```

---

## 📈 Usage

### 1. Run Live Tracker
Executes the scraper to fetch current market prices and update the daily tracking CSV.
```bash
python scraper.py
```

### 2. View Daily Index
Calculates and displays the current CPI based on all scraped data.
```bash
python calculate_cpi.py
```

### 3. Generate Assignment Deliverable
Processes the 7-day mock dataset into a formatted Excel workbook for submission.
```bash
python generate_assignment_report.py
```

---

## 📊 Data Schema: `daily_cpi_tracker.csv`
The tracking database stores every price point with the following structure:
| Date | Category | Item_ID | Target_Weight | Daily_Market_Normalized_Price | Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| YYYY-MM-DD | Staples | Staples_Atta_5kg | 5000 | 6.12 | Scraped |

---

## ⚖️ Methodology
*   **Industry**: Fast-Moving Consumer Goods (FMCG) via Quick Commerce.
*   **Justification**: Quick-commerce offers highly standardized SKUs with high-frequency algorithmic pricing, making it a superior "market-clearing" proxy for real-world inflation.
*   **Weights**:
    *   Staples: 25% | Dairy: 20% | Produce: 20% | Oils: 15% | Household: 10% | Snacks: 10%
