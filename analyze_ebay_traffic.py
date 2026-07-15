#!/usr/bin/env python
"""
eBay Traffic Report Analyzer
Analyzes eBay listing traffic reports to identify top performing listings.
"""

import os
import sys
import argparse
from colorama import init, Fore, Style
from ebay_utils import (
    find_latest_traffic_report,
    parse_traffic_report,
    analyze_top_performers,
    export_top_performers_report
)

# Initialize colorama for colored console output
init(autoreset=True)


def main():
    """Main function to analyze eBay traffic reports."""
    
    # Set up command line arguments
    parser = argparse.ArgumentParser(
        description='Analyze eBay listing traffic reports to identify top performers'
    )
    parser.add_argument(
        '--file', '-f',
        help='Path to specific traffic report CSV file (optional, uses latest if not provided)',
        default=None
    )
    parser.add_argument(
        '--top', '-t',
        type=int,
        default=20,
        help='Number of top performers to show (default: 20)'
    )
    parser.add_argument(
        '--min-views', '-m',
        type=int,
        default=1,
        help='Minimum page views to consider a listing (default: 1)'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output file name for the report (optional)',
        default=None
    )
    parser.add_argument(
        '--downloads-dir', '-d',
        help='Custom downloads directory path (optional)',
        default=None
    )
    
    args = parser.parse_args()
    
    print(Fore.CYAN + "=" * 60)
    print(Fore.CYAN + "EBAY TRAFFIC REPORT ANALYZER")
    print(Fore.CYAN + "=" * 60 + "\n")
    
    # Find or use specified traffic report
    if args.file:
        csv_file = args.file
        if not os.path.exists(csv_file):
            print(Fore.RED + f"Error: File not found: {csv_file}")
            return 1
        print(Fore.GREEN + f"Using specified file: {csv_file}")
    else:
        print(Fore.YELLOW + "Searching for latest traffic report...")
        csv_file = find_latest_traffic_report(args.downloads_dir)
        
        if not csv_file:
            print(Fore.RED + "No traffic report found in downloads directory.")
            print("Please download a traffic report from eBay Seller Hub first.")
            return 1
        
        print(Fore.GREEN + f"Found latest report: {os.path.basename(csv_file)}")
    
    # Parse the CSV file
    print(Fore.YELLOW + "\nParsing traffic report...")
    df = parse_traffic_report(csv_file)
    
    if df is None or df.empty:
        print(Fore.RED + "Failed to parse traffic report or file is empty.")
        return 1
    
    print(Fore.GREEN + f"Successfully loaded {len(df)} listings")
    
    # Analyze top performers
    print(Fore.YELLOW + "\nAnalyzing performance metrics...")
    results = analyze_top_performers(
        df, 
        top_n=args.top,
        min_views=args.min_views
    )
    
    if results is None:
        print(Fore.RED + "Failed to analyze traffic data.")
        return 1
    
    # Display summary to console
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "ANALYSIS SUMMARY")
    print(Fore.CYAN + "=" * 60)
    
    summary = results['summary']
    print(f"\nTotal Listings: {Fore.WHITE}{results['total_listings']}")
    print(f"Analyzed Listings: {Fore.WHITE}{results['analyzed_listings']}")
    print(f"Total Page Views: {Fore.WHITE}{summary['total_views']:,}")
    print(f"Average Views per Listing: {Fore.WHITE}{summary['avg_views']:.1f}")
    print(f"Total Watch Count: {Fore.WHITE}{summary['total_watches']:,}")
    print(f"Average Engagement Rate: {Fore.WHITE}{summary['avg_engagement_rate']:.1f}%")
    
    if 'total_sold' in summary:
        print(f"Total Quantity Sold: {Fore.WHITE}{summary['total_sold']}")
        print(f"Average Conversion Rate: {Fore.WHITE}{summary['avg_conversion_rate']:.2f}%")
    
    # Display top 5 by views
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "TOP 5 LISTINGS BY PAGE VIEWS")
    print(Fore.CYAN + "=" * 60)
    
    for i, item in enumerate(results['top_by_views'][:5], 1):
        print(f"\n{Fore.YELLOW}{i}. Item {item['Item ID']}: {Fore.WHITE}{item['Page views']:,} views")
        title_display = item['Title'][:70] + "..." if len(item['Title']) > 70 else item['Title']
        print(f"   {title_display}")
        print(f"   Watches: {item['Watch count']} | Engagement: {item['Engagement rate']}%")
    
    # Display top 5 by engagement
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "TOP 5 LISTINGS BY ENGAGEMENT RATE")
    print(Fore.CYAN + "=" * 60)
    
    for i, item in enumerate(results['top_by_engagement'][:5], 1):
        print(f"\n{Fore.YELLOW}{i}. Item {item['Item ID']}: {Fore.WHITE}{item['Engagement rate']}% engagement")
        title_display = item['Title'][:70] + "..." if len(item['Title']) > 70 else item['Title']
        print(f"   {title_display}")
        print(f"   Views: {item['Page views']:,} | Watches: {item['Watch count']}")
    
    # Export full report
    print(Fore.YELLOW + "\n" + "=" * 60)
    print(Fore.YELLOW + "Exporting detailed report...")
    
    report_file = export_top_performers_report(results, args.output)
    
    if report_file:
        print(Fore.GREEN + f"\n[SUCCESS] Full report saved to: {report_file}")
        print(Fore.GREEN + f"[SUCCESS] Top performers CSV exported")
    
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "Analysis complete!")
    print(Fore.CYAN + "=" * 60)
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(Fore.RED + "\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(Fore.RED + f"\n\nUnexpected error: {e}")
        sys.exit(1)