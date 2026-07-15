"""
Generate a combined HTML report with both bid optimization and new keyword recommendations.
This integrates with the airotate.bat batch process.
"""

import pandas as pd
import os
from datetime import datetime
import glob
import re

def load_current_campaign_keywords():
    """Load keywords currently in the campaign."""
    keyword_files = []
    for search_dir in [os.path.join(os.getcwd(), 'downloads'), os.path.expanduser('~/Downloads')]:
        keyword_files.extend(glob.glob(os.path.join(search_dir, "Top Converters Test_Keyword_*.csv")))

    if not keyword_files:
        return set(), pd.DataFrame()
    
    latest_file = max(keyword_files, key=os.path.getmtime) 
    df = pd.read_csv(latest_file, skiprows=1)
    
    # Get unique keywords
    current_keywords = set()
    for keyword in df['Seller Keyword'].dropna():
        current_keywords.add(keyword.lower().strip())
    
    return current_keywords, df

def extract_keywords_from_title(title):
    """Extract potential keywords from listing title."""
    if pd.isna(title):
        return []
    
    title = str(title).lower()
    keywords = []
    
    # Car makes and models
    car_patterns = [
        r'honda\s+[\w-]+', r'toyota\s+[\w-]+', r'ford\s+[\w-]+',
        r'gmc\s+[\w-]+', r'chevy\s+[\w-]+', r'chevrolet\s+[\w-]+',
        r'dodge\s+[\w-]+', r'nissan\s+[\w-]+', r'mazda\s+[\w-]+'
    ]
    
    for pattern in car_patterns:
        matches = re.findall(pattern, title)
        keywords.extend(matches)
    
    # Product types
    product_types = ['brake', 'hood', 'deflector', 'camera', 'case', 'waterproof',
                    'trim', 'headliner', 'mirror', 'sensor', 'filter', 'cushion']
    
    for product in product_types:
        if product in title:
            keywords.append(product)
            # Try compound terms
            pattern = rf'{product}\s+\w+'
            matches = re.findall(pattern, title)[:2]  # Limit to 2
            keywords.extend(matches)
    
    # Year patterns
    years = re.findall(r'\b(19|20)\d{2}\b', title)
    keywords.extend(years[:2])  # Limit years
    
    return list(set(keywords))[:10]  # Return max 10 keywords

def find_new_keyword_opportunities(current_keywords):
    """Find keywords from listings not in campaign."""
    # First try to get fresh listings
    import subprocess
    from datetime import datetime, timedelta
    
    # Check for existing files
    listing_files = glob.glob("ALL_LISTINGS_REMOVAL_PRIORITY_*.csv") + \
                   glob.glob("current_listing_ratings*.csv")
    
    # Download fresh data if needed
    if not listing_files:
        print("No listings files found, downloading...")
        subprocess.run(['python', 'ai_download_all_listings.py'], 
                      capture_output=True, text=True, timeout=60)
        # Check again
        listing_files = glob.glob("ALL_LISTINGS_REMOVAL_PRIORITY_*.csv") + \
                       glob.glob("current_listing_ratings*.csv")
    elif listing_files:
        latest_file = max(listing_files, key=os.path.getmtime)
        file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_file))
        if file_age > timedelta(hours=12):
            print(f"Listings file is {file_age.total_seconds()/3600:.1f} hours old, downloading fresh...")
            subprocess.run(['python', 'ai_download_all_listings.py'],
                          capture_output=True, text=True, timeout=60)
            # Update file list
            listing_files = glob.glob("ALL_LISTINGS_REMOVAL_PRIORITY_*.csv") + \
                           glob.glob("current_listing_ratings*.csv")
    
    if not listing_files:
        print("Could not get listings data")
        return pd.DataFrame()
    
    latest_file = max(listing_files, key=os.path.getmtime)
    listings_df = pd.read_csv(latest_file)
    
    if listings_df.empty:
        return pd.DataFrame()
    
    # Extract keywords from titles
    all_new_keywords = []
    keyword_listings = {}
    
    for _, row in listings_df.iterrows():
        title = row.get('Title', row.get('title', ''))
        if pd.isna(title):
            continue
            
        potential_keywords = extract_keywords_from_title(title)
        
        for keyword in potential_keywords:
            if keyword.lower() not in current_keywords:
                all_new_keywords.append(keyword)
                if keyword not in keyword_listings:
                    keyword_listings[keyword] = []
                keyword_listings[keyword].append({
                    'title': title[:80],
                    'views': row.get('Views', 0),
                    'sales': row.get('Sales', 0)
                })
    
    # Count and rank keywords
    from collections import Counter
    keyword_counts = Counter(all_new_keywords)
    
    recommendations = []
    for keyword, count in keyword_counts.most_common(30):
        # Calculate potential score
        listings = keyword_listings[keyword]
        total_views = sum(l['views'] for l in listings)
        total_sales = sum(l['sales'] for l in listings)
        
        rec = {
            'Keyword': keyword,
            'Listings Count': count,
            'Total Views': total_views,
            'Total Sales': total_sales,
            'Match Type': 'BROAD' if len(keyword.split()) > 1 else 'EXACT',
            'Suggested Bid': '$0.50',
            'Priority': 'HIGH' if count > 5 or total_sales > 0 else 'MEDIUM' if count > 2 else 'LOW',
            'Score': count * 10 + total_views * 0.1 + total_sales * 100
        }
        recommendations.append(rec)
    
    df = pd.DataFrame(recommendations)
    if not df.empty:
        df = df.sort_values('Score', ascending=False)
    
    return df

def generate_combined_html_report():
    """Generate HTML report with bid changes and new keywords."""
    
    # Load bid optimization data
    bid_files = glob.glob("bid_changes_detailed_*.csv")
    bid_df = pd.DataFrame()
    if bid_files:
        latest_bid_file = max(bid_files, key=os.path.getmtime)
        bid_df = pd.read_csv(latest_bid_file)
    
    # Load current keywords and find new opportunities
    current_keywords, campaign_df = load_current_campaign_keywords()
    new_keywords_df = find_new_keyword_opportunities(current_keywords)
    
    # Calculate statistics
    total_keywords = len(campaign_df) if not campaign_df.empty else 0
    keywords_to_pause = len(bid_df[bid_df['Recommended Status'] == 'PAUSE']) if not bid_df.empty and 'Recommended Status' in bid_df.columns else 0
    keywords_to_add = len(new_keywords_df) if not new_keywords_df.empty else 0
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>eBay Campaign Optimization Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th {{
            background-color: #f8f9fa;
            padding: 10px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #dee2e6;
        }}
        td {{
            padding: 8px;
            border-bottom: 1px solid #dee2e6;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            display: inline-block;
        }}
        .high {{ background: #dc3545; color: white; }}
        .medium {{ background: #ffc107; color: #333; }}
        .low {{ background: #28a745; color: white; }}
        .pause {{ background: #6c757d; color: white; }}
        .increase {{ background: #ffc107; color: #333; }}
        .decrease {{ background: #f8d7da; color: #721c24; }}
        .maintain {{ background: #d4edda; color: #155724; }}
        .new-keyword {{ background: #cff4fc; color: #055160; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 eBay Campaign Optimization Report</h1>
        <p>Campaign: Top Converters Test | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value">{total_keywords}</div>
            <div class="stat-label">Current Keywords</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{keywords_to_add}</div>
            <div class="stat-label">New Keywords to Add</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{keywords_to_pause}</div>
            <div class="stat-label">Keywords to Pause</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(bid_df) if not bid_df.empty else 0}</div>
            <div class="stat-label">Bid Adjustments</div>
        </div>
    </div>
"""
    
    # Add new keywords section
    if not new_keywords_df.empty:
        html_content += """
    <div class="section">
        <h2>🆕 New Keyword Opportunities</h2>
        <p>Keywords found in your listings but not in your campaign:</p>
        <table>
            <thead>
                <tr>
                    <th>Keyword</th>
                    <th>Found In</th>
                    <th>Total Views</th>
                    <th>Total Sales</th>
                    <th>Match Type</th>
                    <th>Suggested Bid</th>
                    <th>Priority</th>
                </tr>
            </thead>
            <tbody>
"""
        for _, row in new_keywords_df.head(20).iterrows():
            priority_class = row['Priority'].lower()
            html_content += f"""
                <tr>
                    <td><strong>{row['Keyword']}</strong></td>
                    <td>{row['Listings Count']} listings</td>
                    <td>{row['Total Views']}</td>
                    <td>{row['Total Sales']}</td>
                    <td>{row['Match Type']}</td>
                    <td>{row['Suggested Bid']}</td>
                    <td><span class="badge {priority_class}">{row['Priority']}</span></td>
                </tr>
"""
        html_content += """
            </tbody>
        </table>
    </div>
"""
    
    # Add bid optimization section
    if not bid_df.empty:
        html_content += """
    <div class="section">
        <h2>💰 Bid Optimization Recommendations</h2>
        <table>
            <thead>
                <tr>
                    <th>Keyword</th>
                    <th>Current Bid</th>
                    <th>New Bid</th>
                    <th>Action</th>
                    <th>Impressions</th>
                    <th>Clicks</th>
                    <th>CTR</th>
                </tr>
            </thead>
            <tbody>
"""
        for _, row in bid_df.head(30).iterrows():
            action_class = 'maintain'
            if 'PAUSE' in str(row.get('Action', '')):
                action_class = 'pause'
            elif 'INCREASE' in str(row.get('Action', '')):
                action_class = 'increase'
            elif 'DECREASE' in str(row.get('Action', '')):
                action_class = 'decrease'
            
            html_content += f"""
                <tr>
                    <td><strong>{row.get('Keyword', '')}</strong></td>
                    <td>{row.get('Current Bid', '')}</td>
                    <td>{row.get('New Bid', '')}</td>
                    <td><span class="badge {action_class}">{row.get('Action', '')}</span></td>
                    <td>{row.get('Impressions', '')}</td>
                    <td>{row.get('Clicks', '')}</td>
                    <td>{row.get('CTR', '')}</td>
                </tr>
"""
        html_content += """
            </tbody>
        </table>
    </div>
"""
    
    html_content += """
    <div class="section">
        <h2>📋 How to Apply These Changes</h2>
        <ol>
            <li><strong>New Keywords:</strong> Go to Campaign > Keywords > Add Keywords. Copy from the table above.</li>
            <li><strong>Bid Changes:</strong> Go to Campaign > Keywords. Use bulk edit or update individually.</li>
            <li><strong>Pause Keywords:</strong> Select keywords marked for pause and change status to PAUSED.</li>
        </ol>
    </div>
</body>
</html>
"""
    
    # Save HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file = f"campaign_optimization_report_{timestamp}.html"
    
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Combined report generated: {html_file}")
    return html_file

if __name__ == "__main__":
    html_file = generate_combined_html_report()
    os.startfile(html_file)