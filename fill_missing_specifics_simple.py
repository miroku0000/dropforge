"""
Simple function to fill missing item specifics using LLM.
Can be integrated into existing workflow.
"""

import json
import re
from typing import Dict, List, Optional

def llm_fill_missing_specifics(
    title: str,
    description: str,
    current_specifics: List[Dict],
    missing_required: List[str] = None,
    missing_preferred: List[str] = None,
    missing_optional: List[str] = None,
    llm_function = None
) -> Dict[str, str]:
    """
    Use LLM to intelligently fill missing item specifics.
    
    Args:
        title: Item title
        description: Item description (can be HTML)
        current_specifics: List of current specifics [{"Name": "Brand", "Value": "Nike"}]
        missing_required: List of required specifics that are missing
        missing_preferred: List of preferred specifics that are missing
        missing_optional: List of optional specifics that are missing
        llm_function: Function to call LLM (defaults to generate_description_with_llm)
    
    Returns:
        Dictionary of filled specifics {"Brand": "Nike", "Color": "Black"}
    """
    
    # Import here to avoid circular imports
    if llm_function is None:
        from ebay_utils import generate_description_with_llm
        llm_function = generate_description_with_llm
    
    # Combine missing lists - prioritize required, then preferred, then optional
    all_missing = []
    if missing_required:
        all_missing.extend(missing_required)
    if missing_preferred:
        all_missing.extend(missing_preferred)
    if missing_optional:
        all_missing.extend(missing_optional)
    
    # If no specific missing list provided, use common ones
    if not all_missing:
        common_specs = [
            "Brand", "Model", "Type", "Color", "Size", "Material",
            "MPN", "Compatible Brand", "Compatible Model", "Features"
        ]
        # Filter out ones we already have
        current_names = {spec.get('Name') for spec in current_specifics if spec.get('Name')}
        all_missing = [spec for spec in common_specs if spec not in current_names]
    
    if not all_missing:
        return {}
    
    # Build current specs string for context
    current_str = ""
    if current_specifics:
        specs_list = []
        for spec in current_specifics:
            name = spec.get('Name', '')
            value = spec.get('Value', '')
            if name and value:
                specs_list.append(f"{name}: {value}")
        if specs_list:
            current_str = "\\nCurrent specifications:\\n" + "\\n".join(specs_list)
    
    # Clean HTML from description
    clean_desc = re.sub('<.*?>', ' ', description[:1500])  # Remove HTML tags
    clean_desc = re.sub('\\s+', ' ', clean_desc)  # Clean whitespace
    
    # Build prompt with separate sections for required/preferred/optional
    missing_sections = []
    if missing_required:
        missing_sections.append(f"REQUIRED (must fill if possible): {', '.join(missing_required)}")
    if missing_preferred:
        missing_sections.append(f"PREFERRED (highly recommended): {', '.join(missing_preferred)}")
    if missing_optional:
        # Limit optional to first 30 to avoid overwhelming the LLM
        optional_subset = missing_optional[:30]
        missing_sections.append(f"OPTIONAL (fill what you can): {', '.join(optional_subset)}")
    
    missing_str = "\n".join(missing_sections) if missing_sections else f"SPECIFICS: {', '.join(all_missing[:30])}"
    
    prompt = f"""Based on this product information, provide values for the missing item specifics.
Only include values you can determine with confidence from the given information.

PRODUCT: {title}

DESCRIPTION: {clean_desc}{current_str}

MISSING SPECIFICS TO FILL:
{missing_str}

Provide ONLY a JSON object with the specific names and their values.
Example: {{"Brand": "Nike", "Color": "Black", "Size": "10"}}
If you cannot determine a value with confidence, omit that specific.
Focus on required and preferred specifics first.

JSON Response:"""

    try:
        # Call LLM
        response = llm_function(prompt, title)
        
        # Extract JSON from response
        # Try to find JSON object in response
        json_match = re.search(r'\{[^\{\}]*\}', response, re.DOTALL)
        if json_match:
            filled_specs = json.loads(json_match.group())
            
            # Validate and clean
            cleaned = {}
            for key, value in filled_specs.items():
                if key in all_missing:
                    # Clean and validate value
                    value = str(value).strip()
                    if value and value.lower() not in ['unknown', 'n/a', 'not specified', '']:
                        # Truncate to eBay's 65 char limit
                        cleaned[key] = value[:65]
            
            return cleaned
            
    except Exception as e:
        print(f"Error parsing LLM response for specifics: {e}")
    
    return {}

def add_filled_specifics_to_list(
    current_specifics: List[Dict],
    filled_specifics: Dict[str, str]
) -> List[Dict]:
    """
    Add filled specifics to existing specifics list.
    
    Args:
        current_specifics: Current list of specifics
        filled_specifics: Dictionary of new specifics to add
    
    Returns:
        Combined list of specifics
    """
    # Copy current specifics
    updated = current_specifics.copy() if current_specifics else []
    
    # Get current names to avoid duplicates
    current_names = {spec.get('Name') for spec in updated if spec.get('Name')}
    
    # Add new specifics
    for name, value in filled_specifics.items():
        if name not in current_names:
            updated.append({
                'Name': name,
                'Value': value
            })
    
    return updated

# Example usage
if __name__ == "__main__":
    # Test the function
    test_title = "Nike Air Max 270 Men's Running Shoes Size 10 Black/White"
    test_desc = "Brand new Nike Air Max 270 running shoes. Features Air Max cushioning technology."
    test_current = [{"Name": "Condition", "Value": "New"}]
    test_missing_req = ["Brand", "Model", "Size"]
    test_missing_pref = ["Color", "Style", "Material"]
    
    print("Testing LLM specifics filler...")
    print(f"Title: {test_title}")
    print(f"Missing required: {test_missing_req}")
    print(f"Missing preferred: {test_missing_pref}")
    
    # Mock LLM function for testing
    def mock_llm(prompt, title):
        return '{"Brand": "Nike", "Model": "Air Max 270", "Size": "10", "Color": "Black/White"}'
    
    result = llm_fill_missing_specifics(
        test_title, test_desc, test_current,
        test_missing_req, test_missing_pref,
        llm_function=mock_llm
    )
    
    print(f"\\nFilled specifics: {result}")
    
    # Test combining
    combined = add_filled_specifics_to_list(test_current, result)
    print(f"\\nCombined specifics: {combined}")