"""
Enhanced error logging system for eBay API operations.
Captures detailed error information including full context, request/response data,
and attempted content for debugging and analysis.
"""

import json
import os
import csv
from datetime import datetime
import traceback
from typing import Any, Dict, Optional
import hashlib

ERROR_LOG_DIR = os.path.join("..", "data", "ebay_errors")
ERROR_LOG_FILE = os.path.join(ERROR_LOG_DIR, "ebay_api_errors.csv")
ERROR_DETAILS_DIR = os.path.join(ERROR_LOG_DIR, "error_details")

# CSV field names for the main error log
ERROR_LOG_FIELDS = [
    "Timestamp",
    "ItemID",
    "Operation",
    "ErrorCode",
    "ErrorMessage",
    "ShortDescription",
    "Severity",
    "DetailFileID",
    "TitleAttempted",
    "DescriptionLength",
    "DescriptionHash",
    "ItemSpecificsCount",
    "HTTPStatus",
    "APICallName",
    "Traceback"
]

def ensure_directories():
    """Ensure error logging directories exist"""
    os.makedirs(ERROR_LOG_DIR, exist_ok=True)
    os.makedirs(ERROR_DETAILS_DIR, exist_ok=True)

def generate_detail_id(item_id: str, timestamp: str) -> str:
    """Generate unique ID for detail file"""
    return f"{item_id}_{timestamp.replace(':', '').replace('-', '').replace('.', '')}"

def log_ebay_error(
    item_id: str,
    operation: str,
    error: Any,
    attempted_title: Optional[str] = None,
    attempted_description: Optional[str] = None,
    attempted_specifics: Optional[Dict] = None,
    api_response: Optional[Any] = None,
    additional_context: Optional[Dict] = None
) -> str:
    """
    Log detailed eBay API error information.
    
    Args:
        item_id: eBay item ID
        operation: Operation being performed (e.g., 'update_description', 'update_title')
        error: The error/exception object
        attempted_title: Title that was attempted to be set
        attempted_description: Description HTML that was attempted
        attempted_specifics: Item specifics dictionary that was attempted
        api_response: Raw API response if available
        additional_context: Any additional context information
    
    Returns:
        Detail file ID for reference
    """
    ensure_directories()
    
    timestamp = datetime.now().isoformat()
    detail_id = generate_detail_id(item_id, timestamp)
    
    # Extract error information
    error_code = ""
    error_message = str(error)
    short_description = ""
    severity = ""
    http_status = ""
    api_call_name = operation
    full_traceback = traceback.format_exc()
    
    # Try to extract more specific error details if available
    if hasattr(error, 'response'):
        if hasattr(error.response, 'dict'):
            response_dict = error.response.dict()
            if 'Errors' in response_dict:
                errors = response_dict['Errors']
                if isinstance(errors, list) and len(errors) > 0:
                    first_error = errors[0]
                    error_code = first_error.get('ErrorCode', '')
                    error_message = first_error.get('LongMessage', error_message)
                    short_description = first_error.get('ShortMessage', '')
                    severity = first_error.get('SeverityCode', '')
            
            # Get HTTP status if available
            if 'Ack' in response_dict:
                http_status = response_dict.get('Ack', '')
    
    # Calculate description metrics
    desc_length = len(attempted_description) if attempted_description else 0
    desc_hash = hashlib.md5(attempted_description.encode()).hexdigest() if attempted_description else ""
    specifics_count = len(attempted_specifics) if attempted_specifics else 0
    
    # Write to main CSV log
    write_header = not os.path.exists(ERROR_LOG_FILE)
    with open(ERROR_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=ERROR_LOG_FIELDS)
        if write_header:
            writer.writeheader()
        
        writer.writerow({
            "Timestamp": timestamp,
            "ItemID": item_id,
            "Operation": operation,
            "ErrorCode": error_code,
            "ErrorMessage": error_message[:500],  # Truncate for CSV
            "ShortDescription": short_description,
            "Severity": severity,
            "DetailFileID": detail_id,
            "TitleAttempted": attempted_title or "",
            "DescriptionLength": desc_length,
            "DescriptionHash": desc_hash,
            "ItemSpecificsCount": specifics_count,
            "HTTPStatus": http_status,
            "APICallName": api_call_name,
            "Traceback": full_traceback[:1000]  # Truncate for CSV
        })
    
    # Write detailed information to separate JSON file
    detail_file = os.path.join(ERROR_DETAILS_DIR, f"{detail_id}.json")
    detail_data = {
        "timestamp": timestamp,
        "item_id": item_id,
        "operation": operation,
        "error": {
            "code": error_code,
            "message": error_message,
            "short_description": short_description,
            "severity": severity,
            "type": type(error).__name__,
            "full_traceback": full_traceback
        },
        "attempted_data": {
            "title": attempted_title,
            "description": attempted_description,
            "description_metrics": {
                "length": desc_length,
                "hash": desc_hash,
                "num_paragraphs": attempted_description.count('<p>') if attempted_description else 0,
                "num_lists": attempted_description.count('<ul>') + attempted_description.count('<ol>') if attempted_description else 0,
                "has_images": '<img' in attempted_description if attempted_description else False
            },
            "specifics": attempted_specifics,
            "specifics_count": specifics_count
        },
        "api_response": str(api_response) if api_response else None,
        "additional_context": additional_context or {}
    }
    
    with open(detail_file, 'w', encoding='utf-8') as f:
        json.dump(detail_data, f, indent=2, ensure_ascii=False)
    
    print(f"[ERROR LOGGED] {operation} failed for item {item_id}")
    print(f"  Error: {short_description or error_message[:100]}")
    print(f"  Details saved to: {detail_id}")
    
    return detail_id

def analyze_error_patterns():
    """Analyze error patterns from the log file"""
    if not os.path.exists(ERROR_LOG_FILE):
        print("No error log file found")
        return
    
    import pandas as pd
    
    df = pd.read_csv(ERROR_LOG_FILE)
    print(f"\n{'='*60}")
    print("EBAY ERROR ANALYSIS")
    print(f"{'='*60}")
    print(f"Total errors logged: {len(df)}")
    
    # Group by error code
    print("\nMost common error codes:")
    error_counts = df['ErrorCode'].value_counts()
    for code, count in error_counts.head(10).items():
        print(f"  {code}: {count}")
    
    # Group by operation
    print("\nErrors by operation:")
    op_counts = df['Operation'].value_counts()
    for op, count in op_counts.items():
        print(f"  {op}: {count}")
    
    # Recent errors
    print("\nMost recent 5 errors:")
    recent = df.nlargest(5, 'Timestamp')[['Timestamp', 'ItemID', 'ErrorCode', 'ShortDescription']]
    for _, row in recent.iterrows():
        print(f"  {row['Timestamp'][:19]} - Item {row['ItemID']}: {row['ErrorCode']} - {row['ShortDescription'][:50]}")
    
    # Description length analysis
    if 'DescriptionLength' in df.columns:
        desc_errors = df[df['DescriptionLength'] > 0]
        if not desc_errors.empty:
            print(f"\nDescription length statistics for errors:")
            print(f"  Average: {desc_errors['DescriptionLength'].mean():.0f} characters")
            print(f"  Max: {desc_errors['DescriptionLength'].max()} characters")
            print(f"  Min: {desc_errors['DescriptionLength'].min()} characters")
    
    print(f"\nDetailed error files saved in: {ERROR_DETAILS_DIR}")
    print(f"{'='*60}\n")

def get_error_details(item_id: str, latest: bool = True) -> Optional[Dict]:
    """
    Retrieve detailed error information for a specific item.
    
    Args:
        item_id: eBay item ID
        latest: If True, return only the latest error for this item
    
    Returns:
        Dictionary with error details or None if not found
    """
    if not os.path.exists(ERROR_LOG_FILE):
        return None
    
    import pandas as pd
    
    df = pd.read_csv(ERROR_LOG_FILE)
    item_errors = df[df['ItemID'] == str(item_id)]
    
    if item_errors.empty:
        return None
    
    if latest:
        item_errors = item_errors.nlargest(1, 'Timestamp')
    
    errors = []
    for _, row in item_errors.iterrows():
        detail_file = os.path.join(ERROR_DETAILS_DIR, f"{row['DetailFileID']}.json")
        if os.path.exists(detail_file):
            with open(detail_file, 'r', encoding='utf-8') as f:
                detail_data = json.load(f)
                errors.append(detail_data)
        else:
            errors.append(row.to_dict())
    
    return errors[0] if latest and errors else errors

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "analyze":
            analyze_error_patterns()
        else:
            # Look up specific item
            item_id = sys.argv[1]
            details = get_error_details(item_id)
            if details:
                print(f"\nError details for item {item_id}:")
                print(json.dumps(details, indent=2))
            else:
                print(f"No errors found for item {item_id}")
    else:
        # Run analysis by default
        analyze_error_patterns()