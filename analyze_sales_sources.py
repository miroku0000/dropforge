#!/usr/bin/env python
"""
Analyze the sources of your eBay sales (organic vs promoted)
and calculate probabilities of sales through each channel.
"""

from colorama import init, Fore, Style
from ebay_utils import (
    find_latest_traffic_report,
    find_latest_automagical_report,
    parse_traffic_report,
    parse_automagical_report,
    merge_traffic_and_campaign_data,
    analyze_campaign_performance,
    recommend_campaign_settings
)

init(autoreset=True)

print(Fore.CYAN + "=" * 70)
print(Fore.CYAN + "EBAY SALES SOURCE ANALYSIS")
print(Fore.CYAN + "=" * 70 + "\n")

# Load and parse reports
print(Fore.YELLOW + "Loading reports...")
traffic_csv = find_latest_traffic_report()
campaign_csv = find_latest_automagical_report()

if not traffic_csv or not campaign_csv:
    print(Fore.RED + "Could not find required reports")
    exit(1)

traffic_df = parse_traffic_report(traffic_csv)
campaign_df = parse_automagical_report(campaign_csv)
merged_df = merge_traffic_and_campaign_data(traffic_df, campaign_df)
analysis = analyze_campaign_performance(merged_df)

if not analysis:
    print(Fore.RED + "Failed to analyze data")
    exit(1)

metrics = analysis['metrics']
recommendations = recommend_campaign_settings(analysis)

# Display traffic breakdown
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "TRAFFIC SOURCE BREAKDOWN")
print(Fore.CYAN + "=" * 70)

total_clicks = metrics['total_promoted_clicks'] + metrics['total_organic_clicks']
total_impressions = metrics['total_promoted_impressions'] + metrics['total_organic_impressions']

print(f"\n{Fore.YELLOW}Impressions (How often your listings appeared):")
print(f"  Total: {Fore.WHITE}{total_impressions:,.0f}")
print(f"  • Promoted: {metrics['total_promoted_impressions']:,.0f} ({metrics['promoted_impressions_percent']:.1f}%)")
print(f"  • Organic: {metrics['total_organic_impressions']:,.0f} ({metrics['organic_impressions_percent']:.1f}%)")

print(f"\n{Fore.YELLOW}Clicks (Actual visits to your listings):")
print(f"  Total: {Fore.WHITE}{total_clicks:,.0f}")
print(f"  • Promoted: {metrics['total_promoted_clicks']:,.0f} ({metrics['promoted_clicks_percent']:.1f}%)")
print(f"  • Organic: {metrics['total_organic_clicks']:,.0f} ({metrics['organic_clicks_percent']:.1f}%)")

# Click-through rates
if total_impressions > 0:
    overall_ctr = (total_clicks / total_impressions) * 100
    promoted_ctr = (metrics['total_promoted_clicks'] / max(metrics['total_promoted_impressions'], 1)) * 100
    organic_ctr = (metrics['total_organic_clicks'] / max(metrics['total_organic_impressions'], 1)) * 100
    
    print(f"\n{Fore.YELLOW}Click-Through Rates:")
    print(f"  • Promoted CTR: {promoted_ctr:.2f}%")
    print(f"  • Organic CTR: {organic_ctr:.2f}%")
    print(f"  • Overall CTR: {overall_ctr:.2f}%")

# Display sales breakdown
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "SALES SOURCE BREAKDOWN")
print(Fore.CYAN + "=" * 70)

total_sales = metrics['total_promoted_sold'] + metrics['total_organic_sold']
print(f"\nTotal Sales in Period: {Fore.WHITE}{total_sales:.0f} items")
print(f"  • Promoted Sales: {Fore.YELLOW}{metrics['total_promoted_sold']:.0f} items ({metrics['promoted_sales_percent']:.1f}%)")
print(f"  • Organic Sales: {Fore.GREEN}{metrics['total_organic_sold']:.0f} items ({metrics['organic_sales_percent']:.1f}%)")

# Display probabilities
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "SALE PROBABILITY ANALYSIS")
print(Fore.CYAN + "=" * 70)

print(f"\n{Fore.YELLOW}Organic Sale Probability:")
print(f"  {metrics['organic_sale_probability']:.3f}% chance per listing")
print(f"  (Based on {metrics['total_organic_sold']:.0f} sales from {analysis['total_items']} total listings)")

items_with_clicks = len([1 for _, row in campaign_df.iterrows() 
                        if row.get('Total Promoted Listings Clicks', 0) > 0])
print(f"\n{Fore.YELLOW}Promoted Sale Probability (after click):")
print(f"  {metrics['promoted_sale_probability']:.2f}% chance after ad click")
print(f"  (Based on {metrics['total_promoted_sold']:.0f} sales from {items_with_clicks} items with clicks)")

# Cost analysis
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "COST-BENEFIT ANALYSIS")
print(Fore.CYAN + "=" * 70)

print(f"\n{Fore.YELLOW}Current Ad Performance:")
print(f"  Total Ad Fees Paid: ${metrics['total_ad_fees']:.2f}")
print(f"  Total Promoted Sales: ${metrics['total_promoted_sales']:.2f}")
print(f"  Effective Ad Rate: {metrics['avg_effective_ad_rate']:.2f}%")
print(f"  ROAS (Return on Ad Spend): {metrics['total_promoted_sales']/max(metrics['total_ad_fees'], 0.01):.1f}x")

# Calculate hypothetical organic scenario
organic_rate = metrics['organic_sale_probability'] / 100
hypothetical_organic_sales = analysis['total_items'] * organic_rate
hypothetical_lost_sales = metrics['total_promoted_sold'] - hypothetical_organic_sales

print(f"\n{Fore.YELLOW}Hypothetical No-Ads Scenario:")
print(f"  Expected organic sales: {hypothetical_organic_sales:.1f} items")
print(f"  Potential lost sales: {max(0, hypothetical_lost_sales):.1f} items")
print(f"  Ad fees saved: ${metrics['total_ad_fees']:.2f}")

# Strategic insights
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "STRATEGIC INSIGHTS")
print(Fore.CYAN + "=" * 70 + "\n")

if metrics['organic_sales_percent'] > 50:
    print(Fore.GREEN + "• STRONG ORGANIC PRESENCE")
    print("  Your listings perform well organically. Consider reducing ad spend on")
    print("  items that already rank well in search results.")
elif metrics['organic_sales_percent'] < 10:
    print(Fore.YELLOW + "• AD-DEPENDENT SALES")
    print("  Most sales come from ads. Focus on improving organic ranking through:")
    print("  - Better titles and keywords")
    print("  - Competitive pricing")
    print("  - High-quality photos")
else:
    print(Fore.YELLOW + "• BALANCED SALES MIX")
    print("  You have a healthy mix of organic and promoted sales.")

# Attribution window impact
clicks_per_sale = metrics['total_promoted_clicks'] / max(metrics['total_promoted_sold'], 1)
if clicks_per_sale > 50:
    print(f"\n{Fore.YELLOW}• HIGH CLICK-TO-SALE RATIO ({clicks_per_sale:.0f}:1)")
    print("  With eBay's 30-day attribution, many of these clicks may still convert.")
    print("  Monitor performance over the next month before reducing ad spend.")

# Underperformers impact
underperformer_pct = len(analysis['underperformers']) / analysis['campaign_items'] * 100
if underperformer_pct > 10:
    print(f"\n{Fore.YELLOW}• {len(analysis['underperformers'])} UNDERPERFORMING ADS ({underperformer_pct:.1f}%)")
    print("  These items get clicks but no sales. They may still cost you if")
    print("  buyers purchase within 30 days. Consider:")
    print("  - Reviewing pricing competitiveness")
    print("  - Improving product descriptions")
    print("  - Checking if these items are out of stock")

# Final recommendations
print(Fore.CYAN + "\n" + "=" * 70)
print(Fore.CYAN + "OPTIMIZED SETTINGS RECOMMENDATION")
print(Fore.CYAN + "=" * 70 + "\n")

print(f"Based on your {metrics['organic_sales_percent']:.1f}% organic sales rate:\n")
print(f"{Fore.GREEN}Recommended Ad Cap: {recommendations['recommended_cap']:.1f}%")
print(f"{Fore.GREEN}Recommended Modifier: {recommendations['recommended_modifier']:.1f}%")

print(f"\n{Fore.YELLOW}Rationale:")
for reason in recommendations['reasoning'][:3]:  # Show top 3 reasons
    print(f"  • {reason}")

print(f"\n{Fore.CYAN}This strategy balances maximizing sales while minimizing")
print(f"{Fore.CYAN}unnecessary ad spend on items that sell organically.")

print(f"\n{Fore.WHITE}=" * 70)