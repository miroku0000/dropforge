"""
Generate HTML report for Top Converters bid recommendations.
"""

import pandas as pd
import glob
import os
from datetime import datetime

def generate_html_report():
    """Generate an HTML report from the latest bid changes CSV."""
    
    # Find the latest bid changes CSV
    pattern = 'bid_changes_detailed_*.csv'
    files = glob.glob(pattern)
    
    if not files:
        print("[ERROR] No bid changes CSV files found")
        return None
    
    latest_csv = max(files, key=os.path.getmtime)
    print(f"Using CSV: {latest_csv}")
    
    # Read the CSV
    df = pd.read_csv(latest_csv)
    
    # Generate HTML
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html_filename = f'bid_changes_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Top Converters Bid Optimization Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }}
        .summary {{
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 15px;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: linear-gradient(135deg, #0066cc 0%, #004499 100%);
            color: white;
            padding: 12px;
            text-align: left;
            position: sticky;
            top: 0;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background-color: #f0f8ff;
        }}
        .keyword {{
            font-weight: bold;
            color: #333;
        }}
        .maintain {{
            background-color: #d4edda;
            color: #155724;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .increase {{
            background-color: #fff3cd;
            color: #856404;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .decrease {{
            background-color: #f8d7da;
            color: #721c24;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .pause {{
            background-color: #6c757d;
            color: white;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 12px;
        }}
        .positive {{
            color: green;
            font-weight: bold;
        }}
        .negative {{
            color: red;
            font-weight: bold;
        }}
        .neutral {{
            color: gray;
        }}
        .ctr-excellent {{
            color: #28a745;
            font-weight: bold;
        }}
        .ctr-good {{
            color: #17a2b8;
        }}
        .ctr-poor {{
            color: #dc3545;
        }}
        .clicks {{
            font-weight: bold;
            color: #0066cc;
        }}
        .no-clicks {{
            color: #999;
        }}
        .timestamp {{
            text-align: right;
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <h1>🎯 Top Converters Bid Optimization Report</h1>
    <p class="timestamp">Generated: {timestamp}</p>
    
    <div class="summary">
        <h2>Campaign Summary</h2>
        <div class="summary-grid">
            <div class="stat-box">
                <div class="stat-value">{len(df)}</div>
                <div class="stat-label">Total Keywords</div>
            </div>
            <div class="stat-box" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
                <div class="stat-value">{len(df[df['Clicks'] > 0])}</div>
                <div class="stat-label">Keywords with Clicks</div>
            </div>
            <div class="stat-box" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
                <div class="stat-value">{df['Clicks'].sum()}</div>
                <div class="stat-label">Total Clicks</div>
            </div>
            <div class="stat-box" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
                <div class="stat-value">{df['Impressions'].sum():,}</div>
                <div class="stat-label">Total Impressions</div>
            </div>
        </div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Keyword</th>
                <th>Match Type</th>
                <th>Current Bid</th>
                <th>New Bid</th>
                <th>Change</th>
                <th>Action</th>
                <th>Impressions</th>
                <th>Clicks</th>
                <th>CTR</th>
            </tr>
        </thead>
        <tbody>
"""
    
    # Add rows
    for _, row in df.iterrows():
        # Determine action class
        action_class = 'maintain'
        if 'PAUSE' in str(row.get('Action', '')):
            action_class = 'pause'
        elif 'INCREASE' in str(row.get('Action', '')):
            action_class = 'increase'
        elif 'DECREASE' in str(row.get('Action', '')):
            action_class = 'decrease'
        
        # Determine change class
        change_str = str(row.get('Change', '$0.00'))
        if change_str == 'PAUSE':
            change_class = 'negative'
            change_val = 0
        else:
            change_val = float(change_str.replace('$', '').replace('+', ''))
            if change_val > 0:
                change_class = 'positive'
            elif change_val < 0:
                change_class = 'negative'
            else:
                change_class = 'neutral'
        
        # Determine CTR class
        ctr_str = str(row.get('CTR', 'N/A'))
        if ctr_str != 'N/A':
            ctr_val = float(ctr_str.replace('%', ''))
            if ctr_val >= 10:
                ctr_class = 'ctr-excellent'
            elif ctr_val >= 5:
                ctr_class = 'ctr-good'
            else:
                ctr_class = 'ctr-poor'
        else:
            ctr_class = ''
        
        # Clicks class
        clicks = row.get('Clicks', 0)
        clicks_class = 'clicks' if clicks > 0 else 'no-clicks'
        
        html += f"""
            <tr>
                <td class="keyword">{row.get('Keyword', '')}</td>
                <td>{row.get('Match Type', '')}</td>
                <td>{row.get('Current Bid', '')}</td>
                <td>{row.get('New Bid', '')}</td>
                <td class="{change_class}">{row.get('Change', '')}</td>
                <td><span class="{action_class}">{row.get('Action', '')}</span></td>
                <td>{row.get('Impressions', 0)}</td>
                <td class="{clicks_class}">{clicks}</td>
                <td class="{ctr_class}">{ctr_str}</td>
            </tr>
"""
    
    html += """
        </tbody>
    </table>
    
    <div style="margin-top: 30px; padding: 20px; background: white; border-radius: 8px;">
        <h3>📊 Recommendations Summary</h3>
        <ul>
            <li><strong>Keywords with Clicks:</strong> These are your priority keywords. Monitor their conversion rates.</li>
            <li><strong>High CTR Keywords:</strong> Consider increasing bids if they're not converting yet.</li>
            <li><strong>Low CTR Keywords:</strong> May need better keyword-ad relevance or bid reduction.</li>
            <li><strong>No Impressions:</strong> Consider pausing keywords with high bids but no impressions.</li>
        </ul>
    </div>
</body>
</html>
"""
    
    # Save HTML file
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML report generated: {html_filename}")
    return html_filename

if __name__ == "__main__":
    html_file = generate_html_report()
    if html_file:
        # Open in browser
        os.system(f'start {html_file}')