# ebay_utils.py
import sys
# Make stdout/stderr tolerate Unicode glyphs (->, checkmarks) on the Windows
# cp1252 console. MUST run before colorama.init() wraps the streams below --
# otherwise printing "-> Updating title/description on eBay" raises
# UnicodeEncodeError *before* the eBay update call, silently aborting the update
# and miscounting it as a "title/description optimization error".
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import base64
from listing_ai_stats import log_entry
from datetime import datetime
import requests
from html import escape
import os
import pickle
from colorama import init, Fore, Style
import persist_cache.caching
from persist_cache import cache
from datetime import datetime, timedelta, timezone
import html
import re
import time
import markdown2
import json

from openai import OpenAI


init(autoreset=True)

# OpenAI Model Configuration
OPENAI_MODEL = "gpt-4o"

# eBay Configuration
MARKETPLACE_ID = "EBAY_US"

# Cache directories
CACHE_DIR_CATEGORY_SPECIFICS = os.path.join(os.getcwd(), ".cache_category_specifics")
CACHE_DIR_ITEM_DETAILS = os.path.join(os.getcwd(), ".cache_item_details")
CACHE_DIR_LLM = os.path.join(os.getcwd(), ".cache_llm_data")
CACHE_DIR_LLM_DESC = os.path.join(os.getcwd(), ".cache_llm_data_desc")
CACHE_DIR_OAI_DESC = os.path.join(os.getcwd(), ".cache_oai_data_desc")
CACHE_DIR_CATEGORY_NAMES = os.path.join(os.getcwd(), ".cache_category_names")
CACHE_DIR_HITCOUNTS = os.path.join(os.getcwd(), ".cache_hitcount")

# Ensure these directories exist
os.makedirs(CACHE_DIR_CATEGORY_SPECIFICS, exist_ok=True)
os.makedirs(CACHE_DIR_ITEM_DETAILS, exist_ok=True)
os.makedirs(CACHE_DIR_LLM, exist_ok=True)
os.makedirs(CACHE_DIR_CATEGORY_NAMES, exist_ok=True)
os.makedirs(CACHE_DIR_HITCOUNTS, exist_ok=True)
os.makedirs(CACHE_DIR_LLM_DESC, exist_ok=True)
os.makedirs(CACHE_DIR_OAI_DESC, exist_ok=True)

def escape_for_xml(text: str) -> str:
    """
    Prepare text for XML/CDATA content.
    Since we're using CDATA, we don't need to escape HTML entities.
    We only need to handle the CDATA end sequence and control characters.
    """
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    
    # The only thing that can break CDATA is the sequence ]]>
    # Replace it with ]]&gt; to prevent CDATA termination
    text = text.replace(']]>', ']]&gt;')
    
    # Remove control characters (except newlines, returns, and tabs)
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    
    return text

def fix_escaped_html_entities(description: str) -> str:
    """
    Fixes improperly escaped HTML entities in descriptions.
    This handles cases where HTML tags have been double-escaped (e.g., &lt; instead of <)
    or wrapped in <pre> tags with escaped content.
    """
    if not isinstance(description, str):
        return str(description) if description is not None else ""
    
    # Check if the description contains escaped HTML entities
    if '&lt;' in description or '&gt;' in description or '<pre>' in description:
        # First, remove any <pre> tags that contain escaped HTML
        if '<pre>' in description and '</pre>' in description:
            import re
            # Extract content between <pre> tags and unescape it
            def unescape_pre_content(match):
                content = match.group(1)
                # Unescape the HTML entities
                content = content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
                return content
            
            # Replace <pre> blocks with their unescaped content
            description = re.sub(r'<pre>(.*?)</pre>', unescape_pre_content, description, flags=re.DOTALL)
        
        # Also check for general escaped HTML entities throughout the description
        # This handles cases where the entire description has been escaped
        description = description.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    
    return description


def clean_llm_description_output(llm_output: str) -> str:
    # Ensure input is a string
    if not isinstance(llm_output, str):
        print(f"WARNING: clean_llm_description_output received {type(llm_output)}, converting to string")
        llm_output = str(llm_output) if llm_output is not None else ""
    
    # First fix any escaped HTML entities (like &lt; &gt;)
    llm_output = fix_escaped_html_entities(llm_output)
    
    # Strip common LLM artifacts before markdown conversion
    # Remove leading "html", "```html", "```", etc.
    llm_output = llm_output.strip()
    if llm_output.startswith("```html"):
        llm_output = llm_output[7:].strip()
    elif llm_output.startswith("```"):
        llm_output = llm_output[3:].strip()
    if llm_output.endswith("```"):
        llm_output = llm_output[:-3].strip()
    
    # Remove standalone "html" at the start (common LLM artifact)
    if llm_output.startswith("html\n") or llm_output.startswith("html\r\n"):
        llm_output = llm_output.split("\n", 1)[1] if "\n" in llm_output else llm_output
    
    # Remove full HTML document structure (DOCTYPE, html, head, body tags)
    # eBay only accepts HTML body content, not full documents
    llm_output = re.sub(r'<!DOCTYPE[^>]*>', '', llm_output, flags=re.IGNORECASE)
    llm_output = re.sub(r'<html[^>]*>', '', llm_output, flags=re.IGNORECASE)
    llm_output = re.sub(r'</html>', '', llm_output, flags=re.IGNORECASE)
    llm_output = re.sub(r'<head>.*?</head>', '', llm_output, flags=re.DOTALL | re.IGNORECASE)
    llm_output = re.sub(r'<body[^>]*>', '', llm_output, flags=re.IGNORECASE)
    llm_output = re.sub(r'</body>', '', llm_output, flags=re.IGNORECASE)
    
    # Remove any <style> blocks that might be in the content
    llm_output = re.sub(r'<style[^>]*>.*?</style>', '', llm_output, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove inline <link> tags for stylesheets (not allowed in eBay descriptions)
    llm_output = re.sub(r'<link[^>]*>', '', llm_output, flags=re.IGNORECASE)
    
    # Remove <pre> tags (not allowed by eBay) and unescape their content
    # This handles cases where the entire description or parts of it are in <pre> tags
    def unescape_pre(match):
        content = match.group(1)
        return content.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    
    # Apply multiple passes to catch all <pre> tags
    prev_output = None
    while prev_output != llm_output:
        prev_output = llm_output
        llm_output = re.sub(r'<pre[^>]*>(.*?)</pre>', unescape_pre, llm_output, flags=re.DOTALL | re.IGNORECASE)
    
    # Also handle case where everything is wrapped in pre without proper closure
    if llm_output.strip().startswith('<pre>') or llm_output.strip().startswith('<pre '):
        llm_output = re.sub(r'^<pre[^>]*>\s*', '', llm_output, flags=re.IGNORECASE)
        llm_output = re.sub(r'\s*</pre>$', '', llm_output, flags=re.IGNORECASE)
        # Unescape any escaped HTML entities
        llm_output = llm_output.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    
    # One final pass to catch any remaining <pre> tags and unescape content
    llm_output = llm_output.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    llm_output = re.sub(r'</?pre[^>]*>', '', llm_output, flags=re.IGNORECASE)
    
    llm_output = llm_output.strip()
    
    # Convert Markdown to HTML
    html_output = markdown2.markdown(llm_output)
    
    # Ensure markdown result is a string
    if not isinstance(html_output, str):
        print(f"WARNING: markdown2.markdown returned {type(html_output)}, converting to string")
        html_output = str(html_output) if html_output is not None else ""
    
    # Strip unsupported tags, keep only allowed ones
    # eBay only allows: p, b, i, ul, li, br, strong, em (basically simple formatting)
    allowed_tags = ["p", "b", "i", "ul", "li", "br", "strong", "em"]
    # Remove all tags not in allowed list (quick + dirty approach using regex)
    html_output = re.sub(
        r"</?(?!" + "|".join(allowed_tags) + r")\b[^>]*>", "", html_output
    )

    html_output = re.sub(
        r"<p>\s*(<ul>.*?)</ul>\s*</p>", r"\1", html_output, flags=re.DOTALL
    )
    
    # Remove common LLM artifacts that got converted to HTML
    html_output = re.sub(r"^<p>html</p>\s*", "", html_output, flags=re.IGNORECASE)
    html_output = re.sub(r"^<p>```html</p>\s*", "", html_output, flags=re.IGNORECASE)
    html_output = re.sub(r"^<p>```</p>\s*", "", html_output)
    html_output = re.sub(r"\s*<p>```</p>$", "", html_output)
    
    html_output = remove_undesired_characters(html_output)
    if '<img src="https://eb.fixelpixel.net/' in html_output:
        html_output = html_output.split('<img src="https://eb.fixelpixel.net/')[0]
    
    # Clean up malformed HTML structures
    # Fix duplicate/wrong order closing tags
    html_output = re.sub(r'</p>\s*<p>', '</p><p>', html_output)  # Remove space between p tags
    html_output = re.sub(r'</ul>\s*<li>', '<li>', html_output)  # Remove </ul> before <li>
    html_output = re.sub(r'</li>\s*</ul>\s*<li>', '</li><li>', html_output)  # Fix li after closing ul
    html_output = re.sub(r'</p>\s*</p>', '</p>', html_output)  # Remove double closing p
    html_output = re.sub(r'<p>\s*</p>', '', html_output)  # Remove empty p tags
    html_output = re.sub(r'<ul>\s*</ul>', '', html_output)  # Remove empty ul tags
    
    # Fix sections with text followed by list but wrong structure
    # Pattern: </p><ul> with </ul><li> - move the ul opening before the li
    html_output = re.sub(r'</p><ul>\s*</ul><li>', '</p><ul><li>', html_output)
    
    # Wrap standalone headings (text on its own line not in tags) with <p> tags
    # This catches section headings like "Product Details" or "Key Features" without tags
    # First pass: wrap text between block-level closing and opening tags
    html_output = re.sub(r'(</(?:p|ul|li)>)\s+([A-Z][^\n<]+)\s+(<(?:p|ul|li|strong|em|b|i))', r'\1<p><strong>\2</strong></p>\3', html_output)
    
    # Second pass: handle edge cases where bare text appears between any HTML boundaries
    # Split on tags and check for bare text
    parts = re.split(r'(<[^>]+>)', html_output)
    cleaned_parts = []
    for i, part in enumerate(parts):
        if not part.startswith('<') and part.strip() and not re.match(r'^\s*$', part):
            # This is text content, not a tag
            # Check if it's actually inside a tag already by looking at context
            if i > 0 and i < len(parts) - 1:
                prev_tag = parts[i-1] if parts[i-1].startswith('<') else ''
                next_tag = parts[i+1] if i+1 < len(parts) and parts[i+1].startswith('<') else ''
                
                # If text is between closing and opening block tags, wrap it
                if re.match(r'</(p|ul|li|strong|em|b|i)>', prev_tag) and re.match(r'<(p|ul|li|strong|em|b|i)', next_tag):
                    part = f'<p><strong>{part.strip()}</strong></p>'
        cleaned_parts.append(part)
    html_output = ''.join(cleaned_parts)
    
    # Fix malformed nested structures - <p> cannot contain <ul>
    html_output = re.sub(r'<p>\s*<ul>', '<ul>', html_output)
    html_output = re.sub(r'</ul>\s*</p>', '</ul>', html_output)
    
    # Fix double opening tags
    html_output = re.sub(r'<p>\s*<p>', '<p>', html_output)
    html_output = re.sub(r'<ul>\s*<ul>', '<ul>', html_output)
    html_output = re.sub(r'<li>\s*<li>', '<li>', html_output)
    
    # Fix mismatched tags - look for opening tag followed by different closing tag
    # Pattern: <tag1>text</tag2> where tag1 != tag2
    def fix_mismatched_tags(match):
        opening = match.group(1)
        content = match.group(2)
        # Use the opening tag's closing tag (ignore the mismatched closing tag)
        return f'<{opening}>{content}</{opening}>'
    
    # Fix common mismatches - opening inline tag with closing block tag
    html_output = re.sub(r'<(strong|b|i|em)>([^<]*)</(?:p|ul|li)>', fix_mismatched_tags, html_output)
    # Fix opening block tag with closing inline tag
    html_output = re.sub(r'<p>([^<]*)</(?:strong|b|i|em|ul|li)>', r'<p>\1</p>', html_output)
    
    # Remove any incomplete sentences at the end (descriptions cut off mid-sentence)
    # Look for sentences that don't end with proper punctuation
    if html_output.strip() and not html_output.strip().endswith(('.', '!', '?', '</p>', '</li>', '</ul>', '</strong>', '</b>', '</i>', '</em>')):
        # Find the last complete sentence
        last_tag_pos = max(
            html_output.rfind('</p>'),
            html_output.rfind('</li>'),
            html_output.rfind('</ul>')
        )
        if last_tag_pos > 0:
            html_output = html_output[:last_tag_pos + 5]  # +5 to include the closing tag
    
    # Escape any remaining unescaped ampersands that aren't part of entities
    # This prevents XML parsing errors from & characters
    # Match & that's not followed by a valid entity or not already &amp;
    html_output = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;)', '&amp;', html_output)
    
    # Remove any null bytes or other control characters that could break XML
    html_output = html_output.replace('\x00', '').replace('\r', '')
    # Remove any other control characters except newline and tab
    html_output = ''.join(char for char in html_output if ord(char) >= 32 or char in '\n\t')

    result = html_output.strip()
    
    # Final ensure result is a string
    if not isinstance(result, str):
        print(f"WARNING: clean_llm_description_output final result is {type(result)}, converting to string")
        result = str(result) if result is not None else ""
    
    return result


# Duplicate imports removed - already imported at top of file

# OpenAI client will be initialized when needed


def generate_title_with_openai(description: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Uses OpenAI's API (v1+) to generate an eBay listing title from a product description.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
You are an expert eBay seller and SEO copywriter. Generate a compelling and optimized eBay listing title based on the product description below.

Rules:
- Do not exceed 80 characters.
- Start with brand/product name if available.
- Include relevant features (model, size, color, etc.).
- Avoid all caps, special characters, or promotional phrases.
- Use proper capitalization (capitalize first letter of each word).
- Be human-readable and honest.
- Do not generate image links in the description 

Product Description:
\"\"\"{description}\"\"\"

Generated Title:"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.7,
        )
        ret = (
            response.choices[0]
            .message.content.strip()[:80]
            .replace("<p>```html</p>", "")
            .replace("<p>```</p>", "")
        )
        if "</html>" in ret:
            ret = ret.split("</html>")[0]
        return ret
    except Exception as e:
        print(f"[ERROR] OpenAI title generation failed: {e}")
        return "Error: Unable to generate title"


@cache(dir=CACHE_DIR_LLM_DESC, expiry=timedelta(days=30).total_seconds())
def generate_description_with_openai(description: str, specifics: dict) -> str:
    prompt = f"""
Generate a new HTML-formatted eBay product description using the following item specifics and existing description.

Existing Description:
\"\"\"{description}\"\"\"

Item Specifics:
{json.dumps(specifics, indent=2)}

Instructions:
- Make the description detailed and professional.
- Keep it under 1000 words.
- Use ONLY these HTML tags: <p>, <ul>, <li>, <strong>, <b>, <i>, <em>, <br>
- Do NOT use <pre>, <code>, <h1>, <h2>, <h3>, <div>, <span>, or any other tags
- Highlight key features.
- Do NOT include duplicate content.
- Do NOT wrap your response in <pre> tags or code blocks
- Return the actual HTML, not escaped HTML entities

Return only the HTML content, ready to be used directly in an eBay listing.
"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=750,
        )
        ret = (
            response.choices[0].message.content
            .strip()
            .replace("<p>```html</p>", "")
            .replace("<p>```</p>", "")
        )
        if "</html>" in ret:
            ret = ret.split("</html>")[0]
        
        # Check if OpenAI wrapped the output in <pre> tags and remove them
        if ret.strip().startswith('<pre>') or ret.strip().startswith('<pre '):
            print(f"WARNING: OpenAI returned description wrapped in <pre> tags, removing...")
            # Remove opening <pre> tag (with or without attributes)
            ret = re.sub(r'^<pre[^>]*>\s*', '', ret.strip(), flags=re.IGNORECASE)
            # Remove closing </pre> tag
            ret = re.sub(r'\s*</pre>$', '', ret.strip(), flags=re.IGNORECASE)
            # Unescape HTML entities that were escaped inside the pre tag
            ret = ret.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
            print(f"Unwrapped and unescaped description")
        
        return ret  # Return the generated description
        
    except Exception as e:
        print(Fore.RED + f"[OpenAI Error] Failed to generate description: {e}")
        return ""  # Return empty string on error


def extract_rating_from_text(text: str) -> int:
    """
    Extract a rating (1-10) from various text formats.
    Handles: "9", "nine", "the rating is 9", "I rate it 8/10", etc.
    """
    if not text:
        return 5  # Default
    
    text = text.lower().strip()
    
    # Word to number mapping
    word_to_num = {
        'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
        'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
    }
    
    # First try to find a plain number (1-10)
    import re
    # Look for patterns like "9", "9/10", "9 out of 10", etc.
    patterns = [
        r'\b(10|[1-9])\b(?:/10)?',  # Matches 1-10, optionally followed by /10
        r'\b(10|[1-9])\s*(?:out\s*of\s*10)?',  # Matches "8 out of 10"
        r'rating[:\s]+(?:is\s+)?(\d+)',  # Matches "rating: 9" or "rating is 9"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                rating = int(match.group(1))
                if 1 <= rating <= 10:
                    return rating
            except:
                pass
    
    # Check for word numbers
    for word, num in word_to_num.items():
        if word in text:
            return num
    
    # If nothing found, try to extract any digit
    digits = ''.join(filter(str.isdigit, text))
    if digits:
        rating = int(digits[:2] if len(digits) > 1 else digits)  # Take first 1-2 digits
        if 1 <= rating <= 10:
            return rating
    
    return 5  # Default if nothing found

@cache(dir=CACHE_DIR_OAI_DESC, expiry=timedelta(days=30).total_seconds())
def rate_description_with_openai(description: str, specifics: dict, _cache_key_differentiator: str = "rating_function") -> int:
    """
    Rates the effectiveness of a product description for eBay using OpenAI.
    Returns a score from 1 to 10.
    """
    prompt = f"""
Rate the following eBay product description on a scale of 1-10 based on:
- Clarity and readability
- Completeness of information
- Professional presentation
- Use of item specifics
- Sales effectiveness

Description:
{description}

Item Specifics:
{json.dumps(specifics, indent=2)}

Return ONLY a single number from 1 to 10, nothing else.
"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=10,
        )
        rating_text = response.choices[0].message.content.strip()
        # Extract rating using the robust extraction function
        return extract_rating_from_text(rating_text)
    except Exception as e:
        print(Fore.RED + f"[OpenAI Error] Failed to rate description: {e}")
        return 5  # Default middle score on error


@cache(dir=CACHE_DIR_LLM_DESC, expiry=timedelta(days=30).total_seconds())
def rate_title_with_openai(title: str, description: str) -> int:
    """
    Rates the effectiveness of a product title for eBay using OpenAI.
    Returns a score from 1 to 10.
    """
    if "Error:" in title:  # If title generation itself failed
        return 1
        
    prompt = f"""
Rate the following eBay product title on a scale of 1-10 based on:
- Clarity and keyword relevance
- Search optimization
- Accuracy to the product description
- Professional formatting
- Appeal to buyers

Title: {title}

Description: {description[:500]}

Return ONLY a single number from 1 to 10, nothing else.
"""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=10,
        )
        rating_text = response.choices[0].message.content.strip()
        # Extract rating using the robust extraction function
        return extract_rating_from_text(rating_text)
    except Exception as e:
        print(Fore.RED + f"[OpenAI Error] Failed to rate title: {e}")
        return 5  # Default middle score on error


def get_all_hitcounts():
    """
    Fetches the HitCount (page views) for every active listing in your eBay store
    and returns a dict mapping item IDs to hit counts.
    """
    # Load API credentials
    print("starting get_all_hitcounts")

    creds = load_credentials()  # should return a dict with appid, devid, certid, token

    # Instantiate the Trading API client

    api = Trading(
        appid=creds["appid"],
        devid=creds["devid"],
        certid=creds["certid"],
        token=creds["token"],
        config_file=None,
        timeout=60,
    )

    hitcounts = {}
    page = 1

    # Define time range: eBay only lets GetSellerList go back 120 days
    now = datetime.utcnow()
    start_time = (now - timedelta(days=120)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_time = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    while True:
        print(f"debug: getting page {page}")
        response = api.execute(
            "GetSellerList",
            {
                "StartTimeFrom": start_time,
                "StartTimeTo": end_time,
                "Pagination": {"EntriesPerPage": 200, "PageNumber": page},
                "OutputSelector": ["ItemArray.Item.ItemID", "ItemArray.Item.HitCount"],
            },
        )
        data = response.dict()
        items = data.get("ItemArray", {}).get("Item", [])
        if not items:
            break

        # Normalize single-item vs list
        if isinstance(items, dict):
            items = [items]

        for item in items:
            item_id = item.get("ItemID")
            hit_count = int(item.get("HitCount", 0))
            hitcounts[item_id] = hit_count

        # Pagination handling
        total_pages = int(data.get("PaginationResult", {}).get("TotalNumberOfPages", 1))
        print(f"total pages: {total_pages}")
        if page >= total_pages:
            break
        page += 1

    return hitcounts


# --- Monkey Patch for persist-cache TypeError ---
try:
    original_flush = persist_cache.caching.flush

    def fixed_caching_flush(dir, expiry):
        if not expiry:
            return
        try:
            if not os.path.exists(dir):
                print(f"[CACHE][FLUSH][INFO] Cache directory does not exist yet: {dir}")
                return
            for filename in os.listdir(dir):
                filepath = os.path.join(dir, filename)
                if os.path.isfile(filepath) and filename.endswith(".cache"):
                    try:
                        timestamp_dt = datetime.fromtimestamp(
                            os.path.getmtime(filepath)
                        )
                        if timestamp_dt + expiry < datetime.now():
                            os.remove(filepath)
                            print(
                                f"[CACHE][FLUSH] Removed expired cache file: {filename}"
                            )
                    except FileNotFoundError:
                        continue
                    except Exception as e_inner:
                        print(
                            f"[CACHE][FLUSH][WARN] Error processing cache file {filename}: {e_inner}"
                        )
        except Exception as e_outer:
            print(
                Fore.RED
                + f"[CACHE][FLUSH][ERROR] Error during cache flush in {dir}: {e_outer}"
            )

    if hasattr(persist_cache.caching, "flush"):
        persist_cache.caching.flush = fixed_caching_flush
        print(
            "[INFO] Applied monkey patch to persist_cache.caching.flush for expiry TypeError."
        )
except ImportError:
    print(
        "[ERROR] Could not import persist_cache.caching to apply patch. Caching expiry might not work."
    )
except Exception as patch_err:
    print(
        Fore.RED
        + f"[ERROR] Failed to apply monkey patch for persist-cache: {patch_err}"
    )

# --- Monkey Patch for ebaysdk error extend bug ---
try:
    import ebaysdk.connection

    original_get_resp_body_errors = (
        ebaysdk.connection.BaseConnection._get_resp_body_errors
    )

    def safe_get_resp_body_errors(self):
        try:
            result = original_get_resp_body_errors(self)
            return result if result is not None else []
        except Exception as e:
            print(f"[SDK PATCH] Suppressed error in _get_resp_body_errors: {e}")
            return []

    ebaysdk.connection.BaseConnection._get_resp_body_errors = safe_get_resp_body_errors
    print(
        "[INFO] Patched ebaysdk.connection._get_resp_body_errors to prevent NoneType extend error."
    )
except Exception as sdk_patch_err:
    print(f"[ERROR] Failed to patch ebaysdk SDK: {sdk_patch_err}")

import hashlib


# --- Monkey Patch for persist-cache TypeError ---
# Fixes "TypeError: unsupported operand type(s) for +: 'float' and 'datetime.timedelta'"
# Apply this BEFORE the @cache decorator is used.
try:
    import persist_cache.caching
    from datetime import datetime, timedelta
    import os

    original_flush = persist_cache.caching.flush

    def fixed_caching_flush(dir, expiry):
        """Corrected version of persist_cache.caching.flush."""
        if not expiry:
            return  # No expiry set, do nothing

        try:
            # Ensure directory exists before listing
            if not os.path.exists(dir):
                print(f"[CACHE][FLUSH][INFO] Cache directory does not exist yet: {dir}")
                return

            for filename in os.listdir(dir):
                filepath = os.path.join(dir, filename)
                if os.path.isfile(filepath) and filename.endswith(".cache"):
                    try:
                        timestamp_float = os.path.getmtime(filepath)
                        # --- The Fix ---
                        # Convert float timestamp to datetime object before comparison
                        timestamp_dt = datetime.fromtimestamp(timestamp_float)
                        if timestamp_dt + expiry < datetime.now():
                            # --- End Fix ---
                            os.remove(filepath)
                            print(
                                f"[CACHE][FLUSH] Removed expired cache file: {filename}"
                            )
                    except FileNotFoundError:
                        continue  # File might have been removed by another process
                    except Exception as e_inner:
                        print(
                            f"[CACHE][FLUSH][WARN] Error processing cache file {filename}: {e_inner}"
                        )
        except FileNotFoundError:
            # This specific error is handled above, but kept for safety
            print(f"[CACHE][FLUSH][WARN] Cache directory not found during flush: {dir}")
        except Exception as e_outer:
            print(f"[CACHE][FLUSH][ERROR] Error during cache flush in {dir}: {e_outer}")

    # Replace the original function with the fixed one only if it exists
    if hasattr(persist_cache.caching, "flush"):
        persist_cache.caching.flush = fixed_caching_flush
        print(
            "[INFO] Applied monkey patch to persist_cache.caching.flush for expiry TypeError."
        )
    else:
        print("[WARN] persist_cache.caching.flush not found. Patch not applied.")
except ImportError:
    print(
        "[ERROR] Could not import persist_cache.caching to apply patch. Caching expiry might not work."
    )
except Exception as patch_err:
    print(f"[ERROR] Failed to apply monkey patch for persist-cache: {patch_err}")
# --- End Monkey Patch ---


from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import (
    ConnectionError,
)  # Import ConnectionError for specific handling

# Helper function to execute API calls with automatic token refresh
def execute_with_refresh(api_func, *args, **kwargs):
    """Execute an eBay API call with automatic token refresh on auth errors."""
    creds = load_credentials()
    
    for attempt in range(2):
        try:
            return api_func(*args, **kwargs)
        except Exception as e:
            error_str = str(e)
            # Check if it's a token expiry error
            if attempt == 0 and ('932' in error_str or 'Auth token is hard expired' in error_str or 
                                '931' in error_str or 'Auth token is invalid' in error_str):
                print("[INFO] Token expired, attempting to refresh...")
                if 'refresh_token' in creds:
                    success, result = refresh_oauth_token(
                        creds['refresh_token'], 
                        creds['appid'], 
                        creds['certid']
                    )
                    if success:
                        save_refreshed_token(result)
                        # Reload credentials and retry
                        creds = load_credentials()
                        continue
                print("[WARNING] Could not refresh token")
            raise  # Re-raise if not a token error or refresh failed

# Suppress ebaysdk warnings about business policies
import logging
ebaysdk_logger = logging.getLogger('ebaysdk')
# Create a custom filter to suppress business policy warnings
class BusinessPolicyWarningFilter(logging.Filter):
    def filter(self, record):
        # Filter out business policy warnings (code 21919456)
        if '21919456' in str(record.getMessage()):
            return False
        if 'business policies' in str(record.getMessage()).lower():
            return False
        if 'Seller has opted into business policies' in str(record.getMessage()):
            return False
        return True

# Add the filter to ebaysdk logger
ebaysdk_logger.addFilter(BusinessPolicyWarningFilter())

# Create a wrapper for Trading API that filters warnings
class FilteredTrading(Trading):
    """Custom Trading connection that filters out non-critical warnings"""
    
    def execute(self, verb, data=None, *args, **kwargs):
        """Execute API call and filter out business policy warnings"""
        try:
            response = super().execute(verb, data, *args, **kwargs)
            
            # Check if response has warnings we want to suppress
            if hasattr(response, 'reply') and hasattr(response.reply, 'Errors'):
                errors = response.reply.Errors
                if not isinstance(errors, list):
                    errors = [errors] if errors else []
                
                # Filter out business policy warnings (code 21919456)
                filtered_errors = []
                for error in errors:
                    if hasattr(error, 'ErrorCode'):
                        # Skip business policy warning
                        if str(error.ErrorCode) == '21919456':
                            continue
                        # Skip other known non-critical warnings here
                        filtered_errors.append(error)
                
                # Only print warnings if there are non-filtered ones
                if filtered_errors:
                    for error in filtered_errors:
                        if hasattr(error, 'SeverityCode') and error.SeverityCode == 'Warning':
                            print(f"[WARNING] {error.ShortMessage}: {error.LongMessage}")
            
            return response
        except Exception as e:
            # Re-raise the exception as-is
            raise

# Replace Trading with FilteredTrading
Trading = FilteredTrading
import traceback
from urllib.parse import urlparse, parse_qs
import re

# os, datetime, timedelta already imported for patch
import requests  # Added for Ollama
import json  # Added for Ollama
import copy  # Added for Ollama

# The cache decorator is imported at the top of the file


import os
import pickle


# Define a default cache directory (optional, defaults to ./.persist_cache/)
# Duplicate cache directory definitions removed - defined at top of file


# Duplicate MARKETPLACE_ID definition removed - defined at top of file


@cache(dir=CACHE_DIR_HITCOUNTS, expiry=timedelta(days=1).total_seconds())
def get_all_hitcounts_analytics():
    """
    Fetches the total page views (HitCount) for every active listing in your eBay store
    using the Analytics API, and returns a dict mapping item IDs to hit counts.

    Uses the LISTING_VIEWS_TOTAL metric over the last 30 days.
    Requires OAuth token with 'sell.analytics.readonly' scope.
    """
    # Load API credentials
    creds = (
        load_creds_for_oauth()
    )  # should return a dict with appid, devid, certid, token, marketplace_id

    # Get active listings
    listings = get_all_active_listings()  # returns list of dicts with "ItemID"
    item_ids = [str(entry["ItemID"]) for entry in listings]

    # Prepare date range (last 30 days) in ISO 8601 with UTC offset
    now_utc = datetime.utcnow().replace(tzinfo=timezone.utc)
    start = (
        (now_utc - timedelta(days=30))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )
    end = now_utc.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()

    # Hitcounts result
    hitcounts = {}

    # Analytics endpoint
    url = "https://api.ebay.com/sell/analytics/v1/traffic_report"
    try:
        oauth_token = get_oauth_token()
        if not oauth_token:
            print("Failed to obtain OAuth token for traffic report - skipping")
            return {}
    except Exception as e:
        print(f"OAuth error for traffic report - skipping: {e}")
        return {}
        
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Content-Type": "application/json",
        # Required marketplace header
        "X-EBAY-C-MARKETPLACE-ID": creds.get("marketplace_id", MARKETPLACE_ID),
    }

    # Chunk listing IDs (max 200 per request)
    def chunk_list(seq, size):
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    for chunk in chunk_list(item_ids, 200):
        # Build filter string
        filter_param = (
            f"listing_ids:{{{'|'.join(chunk)}}}," f"date_range:[{start}..{end}]"
        )
        params = {
            "dimension": "LISTING",
            "metric": "LISTING_VIEWS_TOTAL",
            "filter": filter_param,
        }

        # Perform GET request
        resp = requests.get(url, headers=headers, params=params)
        # If unauthorized or forbidden, provide diagnostic info
        if resp.status_code == 403:
            raise RuntimeError(
                f"Analytics API 403 Forbidden. Ensure token has sell.analytics.readonly scope "
                f"and marketplace header is correct. Response: {resp.text}"
            )
        resp.raise_for_status()

        data = resp.json()
        for record in data.get("records", []):
            item_id = record["dimensionValues"][0]["value"]
            raw_value = record["metricValues"][0]["value"]
            hitcounts[item_id] = int(raw_value)

    return hitcounts


# ebay_utils.py (Modified Section)
# --- New OAuth Functions ---
def exchange_auth_code_for_token(auth_code, redirect_uri, sandbox=False):
    """Exchanges an eBay auth code for an OAuth token (Authorization Code Grant)."""
    creds = load_creds_for_oauth()
    client_id = creds["appid"]
    client_secret = creds["certid"]

    base_url = "https://api.sandbox.ebay.com" if sandbox else "https://api.ebay.com"
    token_url = f"{base_url}/identity/v1/oauth2/token"

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }

    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": redirect_uri,
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(
            f"OAuth Authorization Code Exchange Error: {e.response.status_code} - {e.response.text}"
        )
        return None


def load_creds_for_oauth(filepath="credentials.txt"):
    """Loads only OAuth required credentials (appid/certid)"""
    creds = {}
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                if key.strip() in ["appid", "certid"]:
                    creds[key.strip()] = val.strip()
    return creds


def get_oauth_token(sandbox=False):
    """Gets OAuth token using client credentials flow"""
    creds = load_creds_for_oauth()
    client_id = creds["appid"]
    client_secret = creds["certid"]

    base_url = "https://api.sandbox.ebay.com" if sandbox else "https://api.ebay.com"
    token_url = f"{base_url}/identity/v1/oauth2/token"

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {auth_header}",
    }

    data = {
        "grant_type": "client_credentials",
        # Try without any scope - will get default scopes for the app
        "scope": "",
    }

    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.HTTPError as e:
        print(f"OAuth Error: {e.response.status_code} - {e.response.text}")
        return None


def get_custom_label(item_id):
    """Returns the SKU (CustomLabel) for the given ItemID."""
    details = _get_item_details_combined(item_id)
    return details.get("CustomLabel", "")


@cache(dir=CACHE_DIR_CATEGORY_SPECIFICS)
def get_category_specifics(category_id, marketplace_id="EBAY_US"):
    """
    Fetch required, preferred, and ALL available item specifics for a given category ID
    using the eBay Commerce Taxonomy API.
    If no data is found, retry with the EBAY-MOTORS marketplace.
    """
    if not category_id:
        print(
            "[WARNING] Skipping category specifics lookup: Category ID is missing or invalid."
        )
        return {"required": [], "preferred": [], "all_available": []}

    def fetch_specifics(marketplace_id):
        try:
            oauth_token = get_oauth_token()
            if not oauth_token:
                print("Failed to obtain OAuth token - using empty specifics")
                return {"required": [], "preferred": [], "all_available": []}
        except Exception as e:
            print(f"OAuth error for category specifics - continuing without: {e}")
            return {"required": [], "preferred": [], "all_available": []}
        url = "https://api.ebay.com/commerce/taxonomy/v1/category_tree/0/get_item_aspects_for_category"
        params = {"category_id": str(category_id)}
        headers = {
            "Authorization": f"Bearer {oauth_token}",
            "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 400:
                print(
                    f"Category Aspects Error: {response.status_code} - {response.text}"
                )
                return {"required": [], "preferred": [], "all_available": []}
            response.raise_for_status()
            aspects_data = response.json()
            required = []
            preferred = []
            all_available = []
            optional = []  # Those that are neither required nor preferred
            
            for aspect in aspects_data.get("aspects", []):
                aspect_name = aspect["localizedAspectName"]
                all_available.append(aspect_name)
                
                if aspect.get("aspectConstraint", {}).get("aspectRequired") is True:
                    required.append(aspect_name)
                else:
                    # If it's not required, it might be preferred or optional
                    # Check if it's recommended/preferred
                    if aspect.get("aspectConstraint", {}).get("aspectMode") == "RECOMMENDED":
                        preferred.append(aspect_name)
                    else:
                        # It's optional - neither required nor preferred, but still fillable
                        optional.append(aspect_name)
                        
            # Add optional aspects to preferred for backward compatibility
            # but also expose them separately if needed
            print(f"[DEBUG] Category {category_id} - Total aspects: {len(all_available)}, Required: {len(required)}, Preferred: {len(preferred)}, Optional: {len(optional)}")
            
            return {
                "required": sorted(required), 
                "preferred": sorted(preferred), 
                "optional": sorted(optional),
                "all_available": sorted(all_available)
            }
        except Exception as e:
            print(
                f"[ERROR] Unexpected error retrieving category specifics for CategoryID {category_id}: {e}"
            )
            return {"required": [], "preferred": [], "all_available": []}

    # First attempt: default marketplace
    result = fetch_specifics(marketplace_id)
    if not result["all_available"]:
        print(
            f"[INFO] No specifics found for CategoryID {category_id} with marketplace '{marketplace_id}'. Retrying with 'EBAY-MOTORS'."
        )
        result = fetch_specifics("EBAY-MOTORS")
    return result


def refresh_oauth_token(refresh_token, app_id, cert_id):
    """Refresh OAuth access token using refresh token."""
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    
    # Create base64 encoded credentials
    credentials = f"{app_id}:{cert_id}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://api.ebay.com/oauth/api_scope " \
                "https://api.ebay.com/oauth/api_scope/sell.marketing " \
                "https://api.ebay.com/oauth/api_scope/sell.inventory " \
                "https://api.ebay.com/oauth/api_scope/sell.account " \
                "https://api.ebay.com/oauth/api_scope/sell.fulfillment"
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=30)
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, str(e)

def save_refreshed_token(token_data, filepath="credentials.txt"):
    """Save the refreshed token back to credentials file."""
    # Read existing file
    lines = []
    with open(filepath, "r") as f:
        for line in f:
            # Skip old token and expiry lines
            if line.startswith("token=") or line.startswith("token_expiry="):
                continue
            if line.strip().startswith("# Token expires"):
                continue
            lines.append(line)
    
    # Add new token and expiry
    lines.append(f"\n# OAuth token auto-refreshed {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"token={token_data['access_token']}\n")
    
    if 'expires_in' in token_data:
        expiry = datetime.now() + timedelta(seconds=token_data['expires_in'])
        lines.append(f"token_expiry={expiry.isoformat()}\n")
        lines.append(f"# Token expires at: {expiry.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Write back
    with open(filepath, "w") as f:
        f.writelines(lines)
    
    print(f"[INFO] Token auto-refreshed, expires at {expiry.strftime('%Y-%m-%d %H:%M:%S')}")

# --- Credential Loading ---
def load_credentials(filepath="credentials.txt"):
    """Loads API credentials from a file and auto-refreshes token if expired."""
    if not os.path.exists(filepath):
        print(f"[ERROR] Credentials file not found at '{filepath}'")
        raise FileNotFoundError(f"Credentials file not found: {filepath}")
    creds = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.strip().split("=", 1)
                    creds[key.strip()] = val.strip()
        
        # Basic validation
        required_keys = ["appid", "devid", "certid", "token"]
        if not all(key in creds for key in required_keys):
            missing = [key for key in required_keys if key not in creds]
            print(
                f"[ERROR] Credentials file '{filepath}' is missing required keys: {missing}"
            )
            raise ValueError(f"Missing required credentials: {missing}")
        
        # Check if token is expired and refresh if needed
        if 'token_expiry' in creds and 'refresh_token' in creds:
            try:
                # Parse expiry time
                expiry_str = creds['token_expiry']
                # Handle both ISO format and simple datetime format
                if 'T' in expiry_str:
                    expiry_time = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                else:
                    expiry_time = datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
                
                # Check if expired (with 5 minute buffer)
                if datetime.now() >= expiry_time - timedelta(minutes=5):
                    print("[INFO] Token expired or expiring soon, attempting to refresh...")
                    success, result = refresh_oauth_token(
                        creds['refresh_token'], 
                        creds['appid'], 
                        creds['certid']
                    )
                    
                    if success:
                        save_refreshed_token(result, filepath)
                        # Update creds dict with new token
                        creds['token'] = result['access_token']
                        if 'expires_in' in result:
                            expiry = datetime.now() + timedelta(seconds=result['expires_in'])
                            creds['token_expiry'] = expiry.isoformat()
                    else:
                        print(f"[WARNING] Failed to refresh token: {result}")
                        print("[WARNING] Using potentially expired token - manual refresh may be required")
            except Exception as e:
                print(f"[WARNING] Error checking/refreshing token: {e}")
                # Continue with existing token
        
        return creds
    except Exception as e:
        print(f"[ERROR] Failed to read or parse credentials file '{filepath}': {e}")
        raise  # Re-raise the exception after logging


# --- URL Parsing (Kept for potential other uses) ---
def extract_category_id_from_url(url):
    """
    Extracts a potential category ID from an eBay item URL query string or path.
    NOTE: This is generally unreliable for finding the primary listing category ID.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        category_id_query = qs.get("category", [None])[0]
        if category_id_query and category_id_query.isdigit():
            print(
                f"[DEBUG] Extracted category ID {category_id_query} from URL 'category' query param: {url}"
            )
            return category_id_query
        sacat_query = qs.get("_sacat", [None])[0]
        if sacat_query and sacat_query.isdigit():
            print(
                f"[DEBUG] Extracted category ID {sacat_query} from URL '_sacat' query param: {url}"
            )
            return sacat_query
        print(f"[DEBUG] Could not reliably extract category ID from URL: {url}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed during category ID extraction from URL '{url}': {e}")
        return None


def _get_item_details_combined(item_id):
    """
    Fetch CategoryID, Description, Specifics, HitCount, ImageCount and CustomLabel (SKU)
    via a single eBay GetItem call. Caches results to
    CACHE_DIR_ITEM_DETAILS/<item_id>.cache for fast reloads, and refreshes
    if the cache is missing or the CustomLabel is empty.
    """
    # Load credentials internally so signature stays the same
    creds = load_credentials()  # must return dict with appid, devid, certid, token

    cache_file = os.path.join(CACHE_DIR_ITEM_DETAILS, f"{item_id}.cache")
    details = None

    # 1) Try loading from cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as cf:
                details = pickle.load(cf)
        except Exception:
            details = None

    # 2) If no cache or CustomLabel missing/empty, fetch fresh and rewrite cache
    if not details or not details.get("CustomLabel"):
        # Try twice - once with current token, once with refreshed token if needed
        for token_attempt in range(2):
            try:
                # Instantiate the eBay Trading API client using loaded creds
                api = Trading(
                    appid=creds["appid"],
                    devid=creds["devid"],
                    certid=creds["certid"],
                    token=creds["token"],
                    config_file=None,
                    timeout=60,
                )

                # Execute GetItem to pull full details
                resp = api.execute(
                    "GetItem",
                    {
                        "ItemID": item_id,
                        "DetailLevel": "ReturnAll",
                        "IncludeItemSpecifics": True,
                        "IncludeDescription": True,
                        "IncludeWatchCount": True,
                    },
                )
                raw = resp.dict()
                item = raw.get("Item", {})
                break  # Success, exit the retry loop
            except Exception as e:
                error_str = str(e)
                # Check if it's a token expiry error
                if token_attempt == 0 and ('932' in error_str or 'Auth token is hard expired' in error_str or '931' in error_str or 'Auth token is invalid' in error_str):
                    print("[INFO] Token expired during API call, attempting to refresh...")
                    if 'refresh_token' in creds:
                        success, result = refresh_oauth_token(
                            creds['refresh_token'], 
                            creds['appid'], 
                            creds['certid']
                        )
                        if success:
                            save_refreshed_token(result)
                            # Reload credentials to get the new token
                            creds = load_credentials()
                            continue  # Retry with new token
                    print("[WARNING] Could not refresh token, API call failed")
                raise  # Re-raise the exception if not a token error or refresh failed

        # Extract fields
        title = item.get("Title", "")
        specs_list = item.get("ItemSpecifics", {}).get("NameValueList", [])
        specifics = {e["Name"]: e["Value"] for e in specs_list if "Name" in e}
        pics = item.get("PictureDetails", {}).get("PictureURL", [])
        num_images = len(pics) if isinstance(pics, list) else (1 if pics else 0)

        # Fix any escaped HTML in the description when fetching from eBay
        raw_description = item.get("Description", "")
        fixed_description = fix_escaped_html_entities(raw_description)
        
        details = {
            "CategoryID": item.get("PrimaryCategory", {}).get("CategoryID"),
            "Title": title,
            "Description": fixed_description,
            "SpecificsDict": specifics,
            "HitCount": int(item.get("HitCount", 0)),
            "ImageCount": num_images,
            # eBay returns your seller-defined SKU as the "SKU" field
            "CustomLabel": item.get("SKU", ""),
        }

        # Ensure cache directory exists, then write updated cache
        os.makedirs(CACHE_DIR_ITEM_DETAILS, exist_ok=True)
        with open(cache_file, "wb") as cf:
            pickle.dump(details, cf)

    return details


def clear_item_details_cache(item_id):
    """
    Deletes the per-item cache file for _get_item_details_combined.
    Returns True if removed, False if no file existed or on error.
    """
    cache_file = os.path.join(CACHE_DIR_ITEM_DETAILS, f"{item_id}.cache")
    if os.path.exists(cache_file):
        try:
            os.remove(cache_file)
            print(f"[CACHE][CLEAR] Removed cache for ItemID {item_id}")
            return True
        except Exception as e:
            print(f"[CACHE][WARN] Could not remove cache {cache_file}: {e}")
    else:
        print(f"[CACHE][INFO] No cache to remove for ItemID {item_id}")
    return False


def clear_llm_description_cache(item_id):
    """
    Deletes the LLM description cache files for a specific item.
    Clears caches from both CACHE_DIR_LLM_DESC and CACHE_DIR_OAI_DESC.
    Returns True if any cache was removed, False otherwise.
    """
    removed_any = False
    
    # Check both LLM description cache directories
    cache_dirs = [CACHE_DIR_LLM_DESC, CACHE_DIR_OAI_DESC]
    
    for cache_dir in cache_dirs:
        # The persist_cache library may create cache files with various patterns
        # Try to find and remove any cache files related to this item_id
        if os.path.exists(cache_dir):
            for filename in os.listdir(cache_dir):
                if item_id in filename:
                    cache_file = os.path.join(cache_dir, filename)
                    try:
                        os.remove(cache_file)
                        print(f"[CACHE][CLEAR] Removed LLM cache file: {filename}")
                        removed_any = True
                    except Exception as e:
                        print(f"[CACHE][WARN] Could not remove cache {cache_file}: {e}")
    
    if not removed_any:
        print(f"[CACHE][INFO] No LLM description cache to remove for ItemID {item_id}")
    
    return removed_any


# --- Modified Getters (Using the Combined Cached Function) ---

# Add this function within your ebay_utils.py file

# Ensure 'clear_caches_for_item' and '_get_item_details_combined' are defined above this point.
# Also ensure necessary imports like 'os' are present.


def get_image_count_for_item(item_id):
    """
    Retrieves the number of images for a specific item using the cached combined call.

    If the cached data exists but shows 0 images or lacks the image count,
    it clears the cache for that item and attempts to refetch the data once.

    Args:
        item_id (str): The eBay ItemID.

    Returns:
        int | None: The number of images, or None if fetching fails even after a retry.
                     Returns 0 if the item genuinely has zero images after a successful fetch/refetch.
    """
    # print(f"[CACHE CHECK] Checking combined cache for ImageCount on ItemID {item_id}.")
    if not item_id:
        print("[ERROR] get_image_count_for_item called with empty item_id.")
        return None

    needs_refetch = False
    image_count = None

    try:
        # --- First Attempt (might hit cache or API) ---
        combined_data = _get_item_details_combined(item_id)

        if combined_data is None:
            print(
                f"[CACHE MISS/FAIL] Initial combined call failed for ItemID {item_id}. Cannot get ImageCount."
            )
            return None  # Initial fetch failed completely

        # Check if ImageCount exists and is greater than 0
        image_count = combined_data.get("ImageCount")  # Use .get() for safety

        if image_count is None:
            # print(
            #     f"[CACHE CHECK] ImageCount key missing in cached data for ItemID {item_id}. Triggering refetch."
            # )
            needs_refetch = True
        elif image_count <= 0:
            # print(
            #     f"[CACHE CHECK] Cached ImageCount is {image_count} for ItemID {item_id}. Triggering refetch."
            # )
            needs_refetch = True
        else:
            # print(
            #     f"\t[CACHE HIT] Found valid ImageCount ({image_count}) in cache for ItemID {item_id}."
            # )
            # No refetch needed, return the valid count
            return image_count

        # --- Refetch Logic (if needed) ---
        if needs_refetch:
            print(
                f"[CACHE ACTION] Clearing cache and refetching combined details for ItemID {item_id} due to invalid/missing ImageCount."
            )

            # --- Second Attempt (forces API call unless clear failed AND another process cached quickly) ---
            print(f"[API CALL] Refetching combined details for ItemID {item_id}...")
            combined_data_refetched = _get_item_details_combined(item_id)

            if combined_data_refetched is None:
                print(
                    f"[API CALL][FAIL] Refetch of combined details failed for ItemID {item_id}. Cannot determine ImageCount."
                )
                return None  # Refetch failed

            # Get the image count from the refetched data
            image_count_refetched = combined_data_refetched.get("ImageCount")

            if image_count_refetched is None:
                print(
                    f"[API CALL][WARN] ImageCount key still missing after refetch for ItemID {item_id}. Returning None."
                )
                return None  # Still missing after refetch
            else:
                print(
                    f"[API CALL][SUCCESS] Refetched ImageCount is {image_count_refetched} for ItemID {item_id}."
                )
                return image_count_refetched  # Return the count from refetched data (could be 0)

    except Exception as e:
        # Catch potential errors during the process (e.g., within _get_item_details_combined if re-raised)
        print(
            f"[ERROR] Unexpected error in get_image_count_for_item for ItemID {item_id}: {e}"
        )
        import traceback  # Import traceback locally if not already globally imported

        traceback.print_exc()
        return None

    # This part should ideally not be reached if logic above is correct, but as a fallback:
    print(
        f"[WARN] get_image_count_for_item reached end unexpectedly for ItemID {item_id}. Returning current image_count: {image_count}"
    )
    # Return the last known image_count, which might be None or 0 if refetch wasn't successful or needed
    return image_count if image_count is not None else 0


def get_views_for_item(item_id):
    """
    Retrieves the Primary Category ID for a specific item using the cached combined call.
    """
    # print(f"[CACHE CHECK] Checking combined cache for HitCount on ItemID {item_id}.")
    if not item_id:
        return None
    combined_data = _get_item_details_combined(item_id)
    print(combined_data)
    if "HitCount" in combined_data:
        print("HitCount in combined_data")
        hit_count = combined_data["HitCount"]
        return hit_count
    else:
        # print("cache miss")
        # print(keys(combined_data))
        return None


# NO @cache decorator here - relies on _get_item_details_combined cache
def get_category_id_for_item(item_id):
    """
    Retrieves the Primary Category ID for a specific item using the cached combined call.
    """
    # print(f"[CACHE CHECK] Checking combined cache for CategoryID on ItemID {item_id}.")
    if not item_id:
        return None
    try:
        combined_data = _get_item_details_combined(item_id)  # Call the cached function
        if combined_data and "CategoryID" in combined_data:
            category_id = combined_data["CategoryID"]
            # print(
            #     f"\t[CACHE HIT] Retrieved CategoryID {category_id} for ItemID {item_id} from combined cache."
            # )
            return category_id
        else:
            print(
                Fore.RED
                + f"[CACHE MISS/FAIL] Could not retrieve CategoryID for {item_id} from combined call."
            )
            return None
    except Exception as e:
        print(
            f"[ERROR] Failed to get CategoryID for {item_id} via combined function: {e}"
        )
        return None


# NO @cache decorator here - relies on _get_item_details_combined cache
def get_item_specifics(item_id):
    """
    Retrieves the NameValueList of item specifics using the cached combined call with retry logic.
    Returns a dictionary.
    """
    # print(f"[CACHE CHECK] Checking combined cache for Specifics on ItemID {item_id}.")
    if not item_id:
        return {}
    
    # Add retry logic for network/API failures
    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} to get specifics for item {item_id}")
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            
            combined_data = _get_item_details_combined(item_id)  # Call the cached function
            if combined_data and "SpecificsDict" in combined_data:
                specifics = combined_data["SpecificsDict"]
                # print(
                #     f"\t[CACHE HIT] Retrieved {len(specifics)} Specifics for ItemID {item_id} from combined cache."
                # )
                return specifics
            else:
                if attempt == max_retries - 1:
                    print(
                        f"\t[CACHE MISS/FAIL] Could not retrieve Specifics for {item_id} from combined call."
                    )
                return {}
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                print(f"[WARNING] Failed to get specifics on attempt {attempt + 1}: {str(e)[:100]}")
                continue
            else:
                print(
                    Fore.RED
                    + f"[ERROR] Failed to get Specifics for {item_id} after {max_retries} attempts: {e}"
                )
                return {}


def update_item_title(
    item_id: str, new_title: str, is_fixed_price: bool = True
) -> bool:
    """
    Updates the title of an existing eBay listing with validation and retry logic.
    """
    print(f"[API CALL][UPDATE] Attempting to update title for ItemID: {item_id}")
    if not item_id or not new_title:
        print("[ERROR] ItemID and new title are required.")
        return False
    
    # Validate and clean title
    original_title = new_title
    
    # First, handle HTML entities properly for XML
    import html
    import re
    # Unescape any existing HTML entities to get raw text
    new_title = html.unescape(new_title)
    
    # Now escape for XML (order matters - & must be first!)
    new_title = new_title.replace('&', '&amp;')
    new_title = new_title.replace('<', '&lt;')
    new_title = new_title.replace('>', '&gt;')
    new_title = new_title.replace('"', '&quot;')
    new_title = new_title.replace("'", '&apos;')
    
    # Remove control characters
    new_title = ''.join(char for char in new_title if ord(char) >= 32 or char in '\n\r\t')
    
    # Clean whitespace
    new_title = ' '.join(new_title.split())
    
    # Truncate if needed
    if len(new_title) > 80:
        print(f"[WARNING] Title too long ({len(new_title)} chars), truncating to 80")
        new_title = new_title[:77] + "..."

    # Retry logic
    max_retries = 3
    last_error = None
    # eBay sometimes auto-changes an item's category on revise; the new category
    # then requires an Item Condition (err 21916884). When that happens we retry
    # with ConditionID 1000 (New) -- our dropship items are all New.
    add_condition_id = False

    for attempt in range(max_retries):
        try:
            creds = load_credentials()
            api = Trading(
                appid=creds["appid"],
                devid=creds["devid"],
                certid=creds["certid"],
                token=creds["token"],
                config_file=None,
                timeout=60,
            )
            request = {"Item": {"ItemID": item_id, "Title": new_title}}
            if add_condition_id:
                request["Item"]["ConditionID"] = 1000   # New (category change needs a condition)
            api_call = "ReviseFixedPriceItem" if is_fixed_price else "ReviseItem"
            
            if attempt > 0:
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} for title update")
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            
            print(
                f"[API CALL][UPDATE] Calling {api_call} for ItemID {item_id} (Title change)..."
            )
            response = api.execute(api_call, request)
            result = response.dict()
            ack = result.get("Ack")
            
            if ack in ("Success", "Warning"):
                clear_item_details_cache(item_id)
                return True
            else:
                last_error = f"API returned: {ack}"
                if attempt < max_retries - 1:
                    print(f"[WARNING] Title update failed: {result.get('Errors', ack)}, retrying...")
                    continue
                else:
                    print(Fore.RED + f"[ERROR] Title update failed after {max_retries} attempts: {result}")
                    return False

        except Exception as e:
            last_error = str(e)
            if "21916884" in str(e):
                add_condition_id = True   # retry will include ConditionID=1000 (New)
            if attempt < max_retries - 1:
                print(f"[WARNING] Exception on attempt {attempt + 1}: {str(e)[:100]}, retrying...")
                continue
            else:
                print(f"[ERROR] Exception updating title for {item_id} after {max_retries} attempts: {e}")
                return False

    return False


# @cache
def get_ebay_description(item_id):
    """
    Retrieves the Description field using the cached combined call.
    Returns a string. Falls back to scraping the public eBay page if API fails.
    """
    # print(f"[CACHE CHECK] Checking combined cache for Description on ItemID {item_id}.")
    if not item_id:
        return ""

    try:
        combined_data = _get_item_details_combined(item_id)
        # print("-------------")
        # print(combined_data)
        # print("-------------")
        if combined_data and "Description" in combined_data:
            description = combined_data["Description"]
            if description:
                # print(
                #     f"[CACHE HIT] Retrieved Description (len: {len(description)}) for ItemID {item_id} from combined cache."
                # )
                return description
    except Exception as e:
        print(
            Fore.RED + f"[ERROR] Failed to get Description via API for {item_id}: {e}"
        )

    # === Fallback: Scrape eBay item page ===
    print(
        f"[FALLBACK] Attempting to scrape eBay web page for description (ItemID: {item_id})..."
    )
    try:
        url = f"https://www.ebay.com/itm/{item_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for description
        desc_container = soup.find("div", id="desc_div") or soup.find(
            "iframe", id="desc_ifr"
        )
        if desc_container:
            description = desc_container.get_text(strip=True) if desc_container else ""
            print(f"[FALLBACK] Scraped description length: {len(description)}")
            return description
        else:
            print("[FALLBACK] Description container not found on page.")
    except Exception as e:
        print(f"[FALLBACK ERROR] Could not scrape eBay page for ItemID {item_id}: {e}")

    return ""


# --- Get All Active Listings ---
# NOTE: This function fetches a list which changes frequently. Caching it directly
# is usually not desirable. It will call the cached functions for individual item details.
def get_all_active_listings():
    """Retrieves all active listings, relies on cached functions for details."""
    try:
        creds = load_credentials()
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] Cannot proceed without valid credentials: {e}")
        return []

    api = Trading(
        appid=creds.get("appid"),
        devid=creds.get("devid"),
        certid=creds.get("certid"),
        token=creds.get("token"),
        config_file=None,
        timeout=60,
    )

    listings = []
    page_number = 1

    while True:
        print(f"[API CALL] Retrieving active listings page {page_number}...")
        try:
            response = api.execute(
                "GetMyeBaySelling",
                {
                    "ActiveList": {
                        "Include": True,
                        "Pagination": {
                            "EntriesPerPage": 200,
                            "PageNumber": page_number,
                        },
                        "Sort": "TimeLeft",
                    },
                    "OutputSelector": [
                        "ActiveList.ItemArray.Item.ItemID",
                        "ActiveList.ItemArray.Item.Title",
                        "ActiveList.ItemArray.Item.PrimaryCategory.CategoryID",
                        "ActiveList.ItemArray.Item.ListingDetails.StartTime",
                        "ActiveList.ItemArray.Item.SellingStatus.QuantitySold",
                        "ActiveList.ItemArray.Item.HitCount",
                        "ActiveList.ItemArray.Item.WatchCount",
                        "ActiveList.PaginationResult",
                    ],
                    "DetailLevel": "ReturnAll",
                },
            )

            result = response.dict()
            ack = result.get("Ack")

            if ack == "Failure":
                errors = result.get("Errors", [])
                if not isinstance(errors, list):
                    errors = [errors]
                for error in errors:
                    print(
                        f"[ERROR] Page {page_number}: {error.get('ErrorCode')} - {error.get('ShortMessage')}"
                    )
                break

            active_list = result.get("ActiveList", {})
            items_data = active_list.get("ItemArray", {}).get("Item", [])
            if isinstance(items_data, dict):
                items = [items_data]
            elif isinstance(items_data, list):
                items = items_data
            else:
                items = []

            if not items:
                print(f"[INFO] No more items found on page {page_number}.")
                break

            for item in items:
                item_id = item.get("ItemID")
                title = item.get("Title", "N/A")
                category_id = item.get("PrimaryCategory", {}).get("CategoryID")
                start_time = item.get("ListingDetails", {}).get("StartTime")
                selling_status = item.get("SellingStatus") or {}
                quantity_sold = int(selling_status.get("QuantitySold", 0))
                hit_count = int(item.get("HitCount", 0))
                watch_count = int(item.get("WatchCount", 0))

                if start_time:
                    start_time_dt = datetime.strptime(
                        start_time, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    days_active = (datetime.utcnow() - start_time_dt).days
                else:
                    days_active = None

                listings.append(
                    {
                        "ItemID": item_id,
                        "Title": title,
                        "PrimaryCategory": category_id,
                        "DaysActive": days_active,
                        "QuantitySold": quantity_sold,
                        "Views": hit_count,
                        "Watchers": watch_count,
                    }
                )

            pagination_result = active_list.get("PaginationResult", {})
            current_page = int(pagination_result.get("PageNumber", page_number))
            total_pages = int(pagination_result.get("TotalNumberOfPages", page_number))

            print(f"[INFO] Fetched page {current_page}/{total_pages}")

            if current_page >= total_pages:
                break

            page_number += 1

        except ConnectionError as ce:
            print(f"[ERROR] SDK ConnectionError on page {page_number}: {ce}")
            if ce.response:
                print(f"[ERROR] SDK Response Dict: {ce.response.dict()}")
            traceback.print_exc()
            break
        except Exception as e:
            print(f"[ERROR] Unexpected error on page {page_number}: {e}")
            traceback.print_exc()
            break

    print(f"[INFO] Finished retrieving listings. Total found: {len(listings)}")
    return listings


def export_listings_to_csv(listings, filename="listing_performance.csv"):
    import pandas as pd
    df = pd.DataFrame(listings)
    df.to_csv(filename, index=False)
    print(f"Exported {len(listings)} listings to {filename}")


def identify_low_performance_listings(
    listings,
    sales_threshold=1000,
    days_threshold=0,
    views_threshold=1000,
    watchers_threshold=1000,
    image_count_threshold=5,
):
    # Fetch the 30-day hit counts from the Analytics API (cached for 24h)
    analytics_hitcounts = get_all_hitcounts_analytics()

    low_perf = []
    for listing in listings:
        item_id = listing.get("ItemID")
        # Fall back to the existing Views field if analytics doesn't have this ItemID
        views = analytics_hitcounts.get(item_id, listing.get("Views", 0))
        watchers = listing.get("Watchers", 0)
        days_active = listing.get("DaysActive", 0)
        sold = listing.get("QuantitySold", 0)
        photos = listing.get("PhotoCount", listing.get("PhotoCount", 0))

        if (
            days_active >= days_threshold
            and sold <= sales_threshold
            and views <= views_threshold
            and watchers <= watchers_threshold
            and photos <= image_count_threshold
        ):
            # Optional: record the analytics‐based view count on the returned dict
            entry = listing.copy()
            entry["AnalyticsViews"] = views
            low_perf.append(entry)

    return low_perf


def update_item_description(
    item_id: str, new_description: str, is_fixed_price: bool = True
) -> bool:
    """
    Updates the description of an existing eBay listing.
    
    Args:
        item_id: The eBay ItemID
        new_description: The new HTML description
        is_fixed_price: Whether this is a fixed price listing (default True)
    
    Returns:
        bool: True on success, False otherwise
    """
    print(f"[API CALL][UPDATE] Attempting to update description for ItemID: {item_id}")
    
    if not item_id or not new_description:
        print("[ERROR] ItemID and description are required.")
        return False
    
    # Clean the description
    new_description = _strip_openai_tag(new_description)
    new_description = remove_undesired_characters(new_description)
    new_description = clean_llm_description_output(new_description)
    
    # Escape for XML/CDATA
    escaped_desc = escape_for_xml(new_description)
    
    # Wrap in CDATA
    cdata_desc = f"<![CDATA[{escaped_desc}]]>"

    # Retry logic
    max_retries = 3
    last_error = None
    # On err 21916884 (category change requires a condition) retry with New.
    add_condition_id = False

    for attempt in range(max_retries):
        try:
            creds = load_credentials()
            api = Trading(
                appid=creds["appid"],
                devid=creds["devid"],
                certid=creds["certid"],
                token=creds["token"],
                config_file=None,
                siteid="0",
                warnings=False,
                timeout=20,
            )
            
            api_call = "ReviseFixedPriceItem" if is_fixed_price else "ReviseItem"
            
            api_data = {
                "Item": {
                    "ItemID": str(item_id),
                    "Description": cdata_desc,
                }
            }
            if add_condition_id:
                api_data["Item"]["ConditionID"] = 1000   # New (category change needs a condition)

            if attempt > 0:
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} for description update")
                import time
                time.sleep(2 ** attempt)  # Exponential backoff
            
            api.execute(api_call, api_data)
            print(f"[SUCCESS] Description updated for ItemID {item_id}")
            
            # Clear caches
            clear_item_details_cache(item_id)
            clear_llm_description_cache(item_id)
            
            return True
            
        except Exception as e:
            last_error = e
            if "21916884" in str(e):
                add_condition_id = True   # retry will include ConditionID=1000 (New)
            if attempt < max_retries - 1:
                print(f"[WARNING] Description update attempt {attempt + 1} failed: {str(e)[:100]}")
                continue
            else:
                print(f"[ERROR] Description update failed after {max_retries} attempts: {e}")
                
                # Save problematic description for debugging
                error_file = f"error_description_{item_id}.html"
                try:
                    with open(error_file, "w", encoding="utf-8") as ef:
                        ef.write(f"Item ID: {item_id}\n")
                        ef.write(f"Error: {e}\n")
                        ef.write("=" * 80 + "\n")
                        ef.write(escaped_desc)
                    print(f"[DEBUG] Saved problematic description to {error_file}")
                except:
                    pass
                    
                return False
    
    return False

def update_item_specifics(
    item_id: str, new_specifics_dict: dict, is_fixed_price: bool = True
) -> bool:
    """
    Updates the Item Specifics for an existing eBay listing.

    - Removes any keys that contain “Device Charging Range”.
    - Sends the request with ItemSpecificsUpdateMode="REPLACE" to overwrite
      everything (this suppresses eBay’s “Don’t remind me about these
      recommendations again” prompt).
    - Clears local caches on success.

    Returns
    -------
    bool
        True on success (Ack == Success or Warning), False otherwise.
    """
    print(f"[API CALL][UPDATE] Attempting to update specifics for ItemID: {item_id}")
    
    # Debug logging to show what specifics we're trying to update
    if isinstance(new_specifics_dict, list):
        print(f"[DEBUG] Updating with {len(new_specifics_dict)} specifics (list format)")
        for spec in new_specifics_dict[:5]:  # Show first 5
            if isinstance(spec, dict):
                print(f"  - {spec.get('Name', 'Unknown')}: {spec.get('Value', 'Unknown')[:50]}")
    elif isinstance(new_specifics_dict, dict):
        print(f"[DEBUG] Updating with {len(new_specifics_dict)} specifics (dict format)")
        for key, value in list(new_specifics_dict.items())[:5]:  # Show first 5
            print(f"  - {key}: {str(value)[:50]}")

    if not item_id or not new_specifics_dict:
        print("[ERROR] ItemID and a dictionary of new specifics are required.")
        return False

    # ── Fix or remove problematic keys ────────────────────────────────────────
    # Handle Device Charging Range and other range fields
    def fix_range_value(value_str, field_name):
        """Fix single values to range format for fields that require it."""
        import re
        
        # Special handling for Device Charging Range - eBay wants numbers only, no units
        is_device_charging = "device charging range" in field_name.lower()
        
        # Check if already in correct format
        if is_device_charging:
            # For Device Charging Range: just numbers, no units
            range_pattern = r'^\d+(\.\d)?-\d+(\.\d)?$'
            if re.match(range_pattern, value_str):
                return value_str
            # Also check if it has a unit that needs to be removed
            range_with_unit = r'^(\d+(?:\.\d)?-\d+(?:\.\d)?)[wWvVaA]$'
            match = re.match(range_with_unit, value_str)
            if match:
                return match.group(1)  # Return without the unit
        else:
            # For other fields: allow units
            range_pattern = r'^\d+(\.\d)?-\d+(\.\d)?[wWvVaA]?$'
            if re.match(range_pattern, value_str):
                return value_str
        
        # Try to extract number from patterns like "9W", "12V", "2.1A", or just "9"
        single_value_pattern = r'^(\d+(?:\.\d)?)\s*([wWvVaA])?$'
        match = re.match(single_value_pattern, value_str)
        if match:
            num = float(match.group(1))
            unit = match.group(2) or ""
            
            # Create reasonable range based on the value
            if "charging" in field_name.lower():
                # For charging: e.g., 9W -> 5-15
                min_val = max(1, num - 4)
                max_val = num + 6
            elif "voltage" in field_name.lower():
                # For voltage: e.g., 12V -> 10-14V
                min_val = max(1, num - 2)
                max_val = num + 2
            else:
                # Generic: ±30% range
                min_val = max(1, num * 0.7)
                max_val = num * 1.3
            
            # Format with at most 1 decimal place
            min_str = f"{min_val:.1f}".rstrip('0').rstrip('.')
            max_str = f"{max_val:.1f}".rstrip('0').rstrip('.')
            
            # For Device Charging Range, don't include units
            if is_device_charging:
                return f"{min_str}-{max_str}"
            else:
                return f"{min_str}-{max_str}{unit.upper()}"
        
        return None
    
    keys_to_process = list(new_specifics_dict.keys())  # Create a copy of keys
    for key in keys_to_process:
        # Check for range fields that need special formatting
        if "range" in key.lower() or "charging" in key.lower():
            value = new_specifics_dict[key]
            if value:
                # Convert value to string if it's a list
                if isinstance(value, list):
                    value = value[0] if value else ""
                value = str(value).strip()
                
                # Check for invalid values that should be removed
                if value.lower() in ["not specified", "n/a", "none", "unknown", ""]:
                    print(f"[CLEAN] Removing '{key}' with invalid value: '{value}'")
                    del new_specifics_dict[key]
                    continue
                
                # Try to fix the value to range format
                fixed_value = fix_range_value(value, key)
                
                if fixed_value and fixed_value != value:
                    print(f"[CLEAN] Fixed '{key}': '{value}' -> '{fixed_value}'")
                    new_specifics_dict[key] = fixed_value
                elif fixed_value:
                    print(f"[CLEAN] '{key}' already in correct format: {value}")
                else:
                    # If we couldn't fix it, remove it to avoid API errors
                    print(f"[CLEAN] Removing '{key}' with unfixable value: '{value}'")
                    del new_specifics_dict[key]

    # ── Build NameValueList payload ───────────────────────────────────────────
    name_value_list_payload = []
    for name, values in new_specifics_dict.items():
        if not values:
            continue

        escaped_name = escape(str(name))
        if isinstance(values, list):
            processed_values = [
                escape(str(v)) for v in values if v is not None and str(v).strip()
            ]
        else:
            processed_values = [escape(str(values))]

        if processed_values:
            name_value_list_payload.append(
                {"Name": escaped_name, "Value": processed_values}
            )

    if not name_value_list_payload:
        print("[WARNING] No valid specifics after cleaning — aborting.")
        return False

    print(f"[DEBUG] Sending {len(name_value_list_payload)} specifics to eBay:")
    for item in name_value_list_payload[:5]:  # Show first 5
        values_str = ', '.join(item['Value'][:2]) if len(item['Value']) > 2 else ', '.join(item['Value'])
        print(f"  - {item['Name']}: {values_str}")
    if len(name_value_list_payload) > 5:
        print(f"  ... and {len(name_value_list_payload) - 5} more")

    item_specifics_payload = {"NameValueList": name_value_list_payload}

    # ── Build request ─────────────────────────────────────────────────────────
    request = {
        "Item": {
            "ItemID": item_id,
            "ItemSpecifics": item_specifics_payload,
            # Overwrite the listing specifics completely to avoid recommendations pop-ups
            "ItemSpecificsUpdateMode": "REPLACE",
        }
    }
    call_name = "ReviseFixedPriceItem" if is_fixed_price else "ReviseItem"

    # ── Execute call (retry once with ConditionID on err 21916884) ────────────
    # eBay can auto-change the category on revise; the new category then requires
    # an Item Condition. On that error we retry with ConditionID 1000 (New).
    for attempt in range(2):
        try:
            creds = load_credentials()
            api = Trading(
                appid=creds["appid"],
                devid=creds["devid"],
                certid=creds["certid"],
                token=creds["token"],
                config_file=None,
                timeout=45,
            )

            print(f"[API CALL][UPDATE] Calling {call_name} for ItemID {item_id} …")
            response = api.execute(call_name, request)
            result = response.dict()
            ack = result.get("Ack", "Failure")
            print(f"[API CALL][UPDATE] Ack Status: {ack}")

            if ack not in ("Success", "Warning"):
                cond_err = False
                # log detailed errors
                for err in result.get("Errors", []):
                    error_code = err.get('ErrorCode')
                    short_msg = err.get('ShortMessage')
                    long_msg = err.get('LongMessage', '')
                    if str(error_code) == "21916884":
                        cond_err = True
                    print(f"[ERROR] {error_code} - {short_msg}")
                    if long_msg:
                        print(f"  Details: {long_msg}")
                    # Check if it's a specific value error
                    if 'ErrorParameters' in err:
                        for param in err.get('ErrorParameters', []):
                            if param.get('ParamID') == '0':
                                print(f"  Problem with: {param.get('Value', 'Unknown')}")
                if cond_err and attempt == 0 and "ConditionID" not in request["Item"]:
                    request["Item"]["ConditionID"] = 1000
                    print("[RETRY] Category change requires a condition; retrying with ConditionID=1000 (New)")
                    continue
                return False

            # ── Clear cache for fresh data next time ──────────────────────────
            clear_item_details_cache(item_id)
            print(f"[CACHE] Cleared details cache for {item_id}")
            return True

        except ConnectionError as ce:
            print(f"[ERROR] eBay SDK ConnectionError: {ce}")
            if ce.response:
                print(f"[ERROR] SDK Response Dict: {ce.response.dict()}")
            if "21916884" in str(ce) and attempt == 0 and "ConditionID" not in request["Item"]:
                request["Item"]["ConditionID"] = 1000
                print("[RETRY] Category change requires a condition; retrying with ConditionID=1000 (New)")
                continue
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error updating specifics: {e}")
            traceback.print_exc()
            return False

    return False


# --- LLM Interaction for Specifics ---
# Define constants for clarity
OLLAMA_DEFAULT_URL = "http://localhost:11434/api/generate"

# Configurable LLM Models - Choose based on speed vs quality needs
OLLAMA_MODELS = {
    'fast': {
        'name': 'gemma3:1b',
        'description': 'Fastest model (~0.3s per call), lower quality',
        'avg_time': 0.3
    },
    'balanced': {
        'name': 'gemma3:4b',
        'description': 'Balanced speed and quality (~0.7s per call)',
        'avg_time': 0.7
    },
    'quality': {
        'name': 'dolphin-mixtral:8x7b-v2.6',
        'description': 'Highest quality, slower (~60s per call)',
        'avg_time': 60
    },
    'tiny': {
        'name': 'deepseek-r1:1.5b',
        'description': 'Tiny model, not recommended for titles/descriptions',
        'avg_time': 0.4
    },
    'phi': {
        'name': 'phi:2.7b',
        'description': 'Alternative small model (~0.5s per call)',
        'avg_time': 0.5
    }
}

# Set default model - can be overridden by environment variable or function parameter
DEFAULT_MODEL_PRESET = os.getenv('OLLAMA_MODEL_PRESET', 'balanced')
OLLAMA_DEFAULT_MODEL = OLLAMA_MODELS.get(DEFAULT_MODEL_PRESET, OLLAMA_MODELS['balanced'])['name']

EBAY_SPECIFIC_VALUE_CHAR_LIMIT = 65
EBAY_MAX_TOTAL_SPECIFICS = 45  # Maximum total number of specifics to aim for


def get_ollama_model(preset='balanced'):
    """
    Get the Ollama model name for a given preset.
    
    Args:
        preset: One of 'fast', 'balanced', 'quality', 'tiny', 'phi'
                Can also be a direct model name like 'gemma3:4b'
    
    Returns:
        Model name string
    """
    # If preset is already a model name (contains ':'), return it directly
    if ':' in str(preset):
        return preset
    
    # Otherwise look up the preset
    model_info = OLLAMA_MODELS.get(preset, OLLAMA_MODELS['balanced'])
    return model_info['name']


def print_available_models():
    """Print available model presets and their characteristics."""
    print("\n=== Available Ollama Model Presets ===")
    for preset, info in OLLAMA_MODELS.items():
        print(f"  {preset:10} - {info['name']:25} | {info['description']}")
    print(f"\nCurrent default: {DEFAULT_MODEL_PRESET} ({OLLAMA_DEFAULT_MODEL})")
    print("Set OLLAMA_MODEL_PRESET environment variable to change default\n")


# Cache LLM calls based primarily on item_id.
# Include description and missing_specifics hash implicitly in the cache key via function arguments.
# Use a relatively short expiry.
@cache(dir=CACHE_DIR_LLM)
def generate_specifics_with_ollama(
    item_id: str,  # Cache based on item_id
    description: str,  # Include description hash in cache key implicitly
    missing_specifics: tuple,  # Include tuple of missing specifics hash implicitly
    ollama_model: str = OLLAMA_DEFAULT_MODEL,
    ollama_url: str = OLLAMA_DEFAULT_URL,
) -> dict | None:
    """
    Uses a local Ollama LLM to suggest values for missing eBay item specifics
    based on the product description, returning a dictionary of *suggested* specifics only.
    Utilizes persistent file caching based on item_id and other inputs.

    Args:
        item_id (str): The eBay ItemID (used for cache key).
        description (str): The full eBay item description.
        missing_specifics (tuple): A tuple of specific names (str) that need values.
        ollama_model (str): The name of the Ollama model to use.
        ollama_url (str): The URL of the local Ollama generate endpoint.

    Returns:
        dict: A dictionary containing ONLY the LLM-generated suggestions {name: value_string}.
              Returns None if the process fails (API error, JSON parsing, network error).
              Returns {} if no suggestions could be generated or validated.
    """
    # Cache handles check/storage based on function args (item_id, description, missing_specifics, etc.)
    print(
        f"[LLM CALL] Asking Ollama model '{ollama_model}' for ItemID {item_id} (may be cached). Missing: {missing_specifics}"
    )
    if not missing_specifics:
        print("[INFO] No missing specifics provided to generate.")
        return {}  # Return empty dict (will be cached)
    if not description:
        print("[WARNING] Empty description provided. LLM may return poor results.")
        # Proceed, let LLM try

    # --- Prompt Construction ---
    prompt = f"""Analyze the product description below for an eBay item (ItemID: {item_id}). Based ONLY on the description, provide values for the following MISSING item specifics:
{', '.join(missing_specifics)}

Product Description:
--- START DESCRIPTION ---
{description}
--- END DESCRIPTION ---

Your task is to return ONLY a single, valid JSON object.
The keys in the JSON object MUST be ONLY the missing item specific names listed above ({', '.join(missing_specifics)}).
The value for each key MUST be a single string derived from the description.
- Do NOT include any keys (specific names) that were NOT in the requested missing list.
- Each value string MUST be concise and relevant.
- IMPORTANT: Each value string MUST NOT exceed {EBAY_SPECIFIC_VALUE_CHAR_LIMIT} characters. If the information suggests a longer value, shorten it appropriately.
- If you cannot determine a value for a specific from the description, omit that key from the JSON output.  
- For the item specific "Personalize", assume the value is "No" if it is not in the text.
- For the item specific "Vintage", assume the value is "No" if it cannot be inferred from the text.
- For the item specific "Device Charging Range" the value is "" if it cannot be inferred from the text.
- For the item specific "Model", extract the model number/name from the description. Look for patterns like model numbers, product codes, or specific product names. If multiple potential models are mentioned, use the most prominent one.
- For the item specific "Type", identify the product type/category from the description. Common types include: Antenna, Cable, Adapter, Charger, Battery, Case, Stand, Speaker, etc. Choose the most specific type that accurately describes the product.
Example JSON output format:
{{
"Specific Name 1": "Suggested Value 1",
"Specific Name 2": "Suggested Value 2"
}}

Return ONLY the JSON object, nothing else.
"""
    # --- End Prompt ---

    data_payload = {
        "model": ollama_model,
        "prompt": prompt,
        "format": "json",
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}

    try:
        print(f"[LLM CALL] Sending request to Ollama at {ollama_url}...")
        # print("prompt_______________________")
        # print(prompt)
        # print("prompt_______________________")
        response = requests.post(
            ollama_url, headers=headers, data=json.dumps(data_payload), timeout=3000
        )
        response.raise_for_status()  # Check for 4xx/5xx errors

        ollama_response_json = response.json()
        llm_generated_json_str = ollama_response_json.get("response")
        # print("response______________________")
        # print(response)
        # print("response______________________")

        if not llm_generated_json_str:
            print("[ERROR] Ollama response did not contain a 'response' field.")
            return None  # Cache None on failure (API issue)

        print("[LLM CALL] Received response from Ollama. Parsing generated JSON...")
        try:
            # Handle potential leading/trailing whitespace or extraneous text around JSON
            json_start = llm_generated_json_str.find("{")
            json_end = llm_generated_json_str.rfind("}")
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_str_cleaned = llm_generated_json_str[json_start : json_end + 1]
            else:
                json_str_cleaned = (
                    llm_generated_json_str  # Use as is if no clear brackets found
                )

            suggested_specifics = json.loads(json_str_cleaned)
            if not isinstance(suggested_specifics, dict):
                print(
                    f"[ERROR] LLM did not return a valid JSON object (got type {type(suggested_specifics)}). Cleaned Response: {json_str_cleaned}"
                )
                return None  # Cache None on failure (LLM format issue)

            print(f"[LLM CALL] LLM suggested specifics: {suggested_specifics}")

            # --- Validation within the cached function ---
            validated_suggestions = {}
            for name, value in suggested_specifics.items():
                # Ensure the LLM didn't hallucinate specifics we didn't ask for
                if name not in missing_specifics:
                    print(
                        f"[LLM VALIDATE][WARN] LLM returned unexpected specific '{name}'. Ignoring."
                    )
                    continue

                # Ensure value is string and handle potential non-string JSON values
                if not isinstance(value, str):
                    print(
                        f"[LLM VALIDATE][WARN] LLM value for '{name}' is not a string ({type(value)}). Attempting str()."
                    )
                    try:
                        value = str(value)
                    except Exception:
                        print(
                            f"[LLM VALIDATE][ERROR] Could not convert value for '{name}' to string. Skipping."
                        )
                        continue  # Skip this specific

                # Enforce character limit
                if len(value) > EBAY_SPECIFIC_VALUE_CHAR_LIMIT:
                    print(
                        f"[LLM VALIDATE][WARN] Truncating value for '{name}' from {len(value)} to {EBAY_SPECIFIC_VALUE_CHAR_LIMIT} chars."
                    )
                    value = value[:EBAY_SPECIFIC_VALUE_CHAR_LIMIT].strip()

                # Skip empty strings after potential truncation/stripping
                if not value:
                    print(
                        f"[LLM VALIDATE][INFO] Skipping specific '{name}' due to empty value after processing."
                    )
                    continue

                validated_suggestions[name] = value  # Store validated string value

            print(
                f"[LLM VALIDATE] Returning {len(validated_suggestions)} validated suggestions."
            )
            return validated_suggestions  # Return dict of validated suggestions (will be cached)
            # --- End Validation ---

        except json.JSONDecodeError as json_err:
            print(f"[ERROR] Failed to decode JSON response from LLM: {json_err}")
            print(
                f"[DEBUG] LLM Raw Response String (first 500 chars): {llm_generated_json_str[:500]}"
            )
            return None  # Cache None on failure (JSON decode issue)

    except requests.exceptions.RequestException as req_err:
        print(f"[ERROR] Failed to connect to Ollama API at {ollama_url}: {req_err}")
        raise req_err  # Re-raise for cache library (don't cache transient network error)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during Ollama interaction: {e}")
        traceback.print_exc()
        raise e  # Re-raise for cache library


OPENAI_TAG_RE = re.compile(r"OPENAI_MODEL\s*=\s*\S+", re.IGNORECASE)


def _strip_openai_tag(text: str) -> str:
    """Remove any 'OPENAI_MODEL=…' substring and surrounding whitespace."""
    if not isinstance(text, str):
        print(f"WARNING: _strip_openai_tag received {type(text)}, converting to string")
        text = str(text) if text is not None else ""
    result = OPENAI_TAG_RE.sub("", text).strip()
    if not isinstance(result, str):
        print(f"WARNING: _strip_openai_tag regex result is {type(result)}, converting to string")
        result = str(result) if result is not None else ""
    return result


# --------------------------------------------------------------------------- #
# Updated main routine
# --------------------------------------------------------------------------- #
def get_missing_item_specifics_report(
    MIN_DESCRIPTION_RATING: int = 10,
    MIN_TITLE_RATING: int = 10,
):
    """
    Scans all active listings, fills missing specifics, and optionally
    improves titles / descriptions.  Ensures no OPENAI_MODEL tag is ever
    left in the live description that gets pushed back to eBay.
    Returns the in-memory report list.
    """
    print("\n" + "=" * 30 + " Generating Missing Specifics Report " + "=" * 30)
    listings = get_all_active_listings()
    report = []

    if not listings:
        print("[INFO] No active listings found to generate report.")
        return []

    total = len(listings)
    updated_titles = 0
    updated_desc = 0

    for idx, listing in enumerate(listings, 1):
        item_id = listing.get("ItemID")
        title = listing.get("Title", "N/A")
        category_id = listing.get("PrimaryCategory")
        print(f"\n--- Processing {idx}/{total} — {item_id} ---")

        # ---------- initialise bookkeeping ----------
        report_entry = {
            "ItemID": item_id,
            "Title": title,
            "CategoryID": category_id,
            "Description": "N/A",
            "MissingRequired": [],
            "MissingPreferred": [],
            "PresentSpecifics": {},
        }

        log_data = {
            "ItemID": item_id,
            "Timestamp": datetime.utcnow().isoformat(),
            "TitleImproved": False,
            "DescriptionImproved": False,
            "FailureReason": "",
        }

        # ---------- pull & clean description ----------
        try:
            raw_desc = get_ebay_description(item_id)
        except Exception as e:
            print(f"[ERROR] fetch description failed: {e}")
            log_data["FailureReason"] = "Description fetch error"
            raw_desc = ""

        # remove OPENAI tag immediately
        description = _strip_openai_tag(raw_desc)
        description = remove_undesired_characters(description)
        description = clean_llm_description_output(description)
        report_entry["Description"] = description or "N/A"

        # ------------------------------------------------
        #  TITLE IMPROVEMENT
        # ------------------------------------------------
        try:
            if MIN_TITLE_RATING > 1:
                better_title = process_title(description, title, MIN_TITLE_RATING)
                better_title = html.escape(_strip_openai_tag(better_title))

                if better_title and better_title not in (title, escape(title)):
                    print(Fore.GREEN + "→ Updating title on eBay")
                    if update_item_title(item_id, better_title):
                        title = better_title
                        report_entry["Title"] = better_title
                        updated_titles += 1
                        log_data["TitleImproved"] = True
        except Exception as e:
            print(f"[ERROR] title optimisation error: {e}")
            log_data["FailureReason"] = "Title optimization error"
            
            # Enhanced error logging
            try:
                from ebay_error_logger import log_ebay_error
                log_ebay_error(
                    item_id=str(item_id),
                    operation="update_title",
                    error=e,
                    attempted_title=better_title if 'better_title' in locals() else None,
                    attempted_description=None,
                    attempted_specifics=None,
                    api_response=getattr(e, 'response', None),
                    additional_context={
                        "original_title": title,
                        "original_rating": title_rating,
                        "improved_rating": improved_rating if 'improved_rating' in locals() else None,
                        "category_id": category_id
                    }
                )
            except:
                pass  # Don't let error logging failure stop the main process

        # ---------- item specifics ----------
        try:
            current_specs = get_item_specifics(item_id)
            report_entry["PresentSpecifics"] = current_specs
        except Exception as e:
            print(f"[ERROR] specifics fetch error: {e}")
            log_data["FailureReason"] = "Specifics fetch error"
            current_specs = {}

        # ---------- category specifics rules ----------
        if not category_id:
            category_id = get_category_id_for_item(item_id)
            report_entry["CategoryID"] = category_id

        if category_id:
            rules = get_category_specifics(category_id)
            req = set(rules.get("required", []))
            pref = set(rules.get("preferred", []))
            optional = set(rules.get("optional", []))
            all_available = set(rules.get("all_available", []))

            # Find ALL missing specifics, not just required and preferred
            missing_req = sorted([s for s in req if not current_specs.get(s)])
            missing_pref = sorted([s for s in pref if s not in current_specs])
            missing_optional = sorted([s for s in optional if s not in current_specs])
            missing_all = sorted([s for s in all_available if s not in current_specs])

            report_entry["MissingRequired"] = missing_req
            report_entry["MissingPreferred"] = missing_pref
            report_entry["MissingOptional"] = missing_optional
            
            print(f"Missing Required  : {missing_req}")
            print(f"Missing Preferred : {missing_pref}")
            print(f"Missing Optional  : {len(missing_optional)} specifics: {missing_optional[:5]}{'...' if len(missing_optional) > 5 else ''}")
            print(f"Total Missing     : {len(missing_all)} out of {len(all_available)} available specifics")
            
            # Use LLM to fill ALL missing specifics (required, preferred, AND optional)
            if missing_all:
                try:
                    from fill_missing_specifics_simple import llm_fill_missing_specifics, add_filled_specifics_to_list
                    
                    print(f"Using LLM to fill {len(missing_all)} missing specifics ({len(missing_req)} required, {len(missing_pref)} preferred, {len(missing_optional)} optional)...")
                    
                    # Convert current_specs from dict to list format
                    current_specs_list = []
                    if current_specs and isinstance(current_specs, dict):
                        for name, value in current_specs.items():
                            current_specs_list.append({"Name": name, "Value": value})
                    
                    # Pass ALL missing specifics to the LLM, not just required/preferred
                    filled = llm_fill_missing_specifics(
                        title=title,
                        description=description,
                        current_specifics=current_specs_list,
                        missing_required=missing_req,
                        missing_preferred=missing_pref,
                        missing_optional=missing_optional  # Add optional specifics
                    )
                    
                    if filled:
                        print(f"  LLM filled {len(filled)} specifics: {list(filled.keys())[:5]}")
                        # Add to current specifics (use list format)
                        updated_specs = add_filled_specifics_to_list(current_specs_list, filled)
                        # Update on eBay
                        if update_item_specifics(item_id, updated_specs):
                            print(f"  ✓ Updated item specifics with LLM-filled values")
                            # Update the current_specs dictionary for further use
                            for spec in updated_specs:
                                if isinstance(spec, dict) and 'Name' in spec and 'Value' in spec:
                                    current_specs[spec['Name']] = spec['Value']
                            # Update the missing lists
                            filled_names = set(filled.keys())
                            missing_req = [s for s in missing_req if s not in filled_names]
                            missing_pref = [s for s in missing_pref if s not in filled_names]
                            missing_optional = [s for s in missing_optional if s not in filled_names]
                            missing_all = [s for s in missing_all if s not in filled_names]
                            report_entry["MissingRequired"] = missing_req
                            report_entry["MissingPreferred"] = missing_pref
                            report_entry["MissingOptional"] = missing_optional
                            print(f"  ✓ After update: {len(missing_all)} specifics still missing")
                except Exception as e:
                    print(f"  Could not use LLM to fill specifics: {e}")
        else:
            report_entry["MissingRequired"] = ["N/A - Category ID missing"]
            report_entry["MissingPreferred"] = ["N/A - Category ID missing"]

        # ------------------------------------------------
        #  DESCRIPTION QUALITY / UPDATE
        # ------------------------------------------------
        try:
            if (
                not report_entry["MissingRequired"]
                and not report_entry["MissingPreferred"]
            ):
                original_rating = rate_description_with_llm(description, current_specs)
                # Ensure rating is an integer
                if not isinstance(original_rating, int):
                    original_rating = 5  # Default fallback
                print(f"DESCRIPTION - Original rating: {original_rating}/10 (threshold: {MIN_DESCRIPTION_RATING})")
                print(f"Current description: {description[:200]}{'...' if len(description) > 200 else ''}")
                if (
                    original_rating < MIN_DESCRIPTION_RATING
                    or "OPENAI_MODEL" in raw_desc
                ):
                    # Generate new description with robust type checking
                    raw_new_desc = generate_description_with_llm(description, current_specs)
                    print(f"DEBUG: generate_description_with_llm returned type: {type(raw_new_desc)}, value: {repr(raw_new_desc[:100] if isinstance(raw_new_desc, str) else raw_new_desc)}")
                    
                    # Ensure we have a string after generation
                    if not isinstance(raw_new_desc, str):
                        print(f"WARNING: generate_description_with_llm returned {type(raw_new_desc)}, converting to string")
                        raw_new_desc = str(raw_new_desc) if raw_new_desc is not None else ""
                    
                    stripped_desc = _strip_openai_tag(raw_new_desc)
                    print(f"DEBUG: _strip_openai_tag returned type: {type(stripped_desc)}, value: {repr(stripped_desc[:100] if isinstance(stripped_desc, str) else stripped_desc)}")
                    
                    # Ensure we have a string after stripping
                    if not isinstance(stripped_desc, str):
                        print(f"WARNING: _strip_openai_tag returned {type(stripped_desc)}, converting to string")
                        stripped_desc = str(stripped_desc) if stripped_desc is not None else ""
                    
                    new_desc = clean_llm_description_output(stripped_desc)
                    print(f"DEBUG: clean_llm_description_output returned type: {type(new_desc)}, value: {repr(new_desc[:100] if isinstance(new_desc, str) else new_desc)}")
                    
                    # Ensure we have a string after cleaning
                    if not isinstance(new_desc, str):
                        print(f"WARNING: clean_llm_description_output returned {type(new_desc)}, converting to string")
                        new_desc = str(new_desc) if new_desc is not None else ""
                    
                    raw_rating = rate_description_with_llm(new_desc, current_specs)
                    print(f"DEBUG: rate_description_with_llm returned type: {type(raw_rating)}, value: {repr(raw_rating)}")
                    
                    # Ensure rating is an integer
                    if isinstance(raw_rating, str):
                        new_rating = extract_rating_from_text(raw_rating)
                    elif isinstance(raw_rating, int):
                        new_rating = raw_rating
                    else:
                        print(f"WARNING: rate_description_with_llm returned {type(raw_rating)}, using default rating 5")
                        new_rating = 5
                    # Ensure rating is an integer
                    if not isinstance(new_rating, int):
                        new_rating = 5  # Default fallback
                    print(f"Generated new description - Rating: {new_rating}/10")
                    print(f"New description: {new_desc[:200]}{'...' if len(new_desc) > 200 else ''}")

                    # OpenAI fallback if local model worse
                    if new_rating <= original_rating:
                        # OpenAI generation with robust type checking
                        raw_openai_desc = generate_description_with_openai(
                            description, current_specs
                        )
                        print(f"DEBUG: generate_description_with_openai returned type: {type(raw_openai_desc)}, value: {repr(raw_openai_desc[:100] if isinstance(raw_openai_desc, str) else raw_openai_desc)}")
                        
                        # Ensure we have a string after OpenAI generation
                        if not isinstance(raw_openai_desc, str):
                            print(f"WARNING: generate_description_with_openai returned {type(raw_openai_desc)}, converting to string")
                            raw_openai_desc = str(raw_openai_desc) if raw_openai_desc is not None else ""
                        
                        stripped_openai = _strip_openai_tag(raw_openai_desc)
                        print(f"DEBUG: _strip_openai_tag (OpenAI) returned type: {type(stripped_openai)}, value: {repr(stripped_openai[:100] if isinstance(stripped_openai, str) else stripped_openai)}")
                        
                        # Ensure we have a string after OpenAI stripping
                        if not isinstance(stripped_openai, str):
                            print(f"WARNING: _strip_openai_tag (OpenAI) returned {type(stripped_openai)}, converting to string")
                            stripped_openai = str(stripped_openai) if stripped_openai is not None else ""
                        
                        openai_desc = clean_llm_description_output(stripped_openai)
                        print(f"DEBUG: clean_llm_description_output (OpenAI) returned type: {type(openai_desc)}, value: {repr(openai_desc[:100] if isinstance(openai_desc, str) else openai_desc)}")
                        
                        # Ensure we have a string after OpenAI cleaning
                        if not isinstance(openai_desc, str):
                            print(f"WARNING: clean_llm_description_output (OpenAI) returned {type(openai_desc)}, converting to string")
                            openai_desc = str(openai_desc) if openai_desc is not None else ""
                        
                        raw_openai_rating = rate_description_with_llm(
                            openai_desc, current_specs
                        )
                        print(f"DEBUG: rate_description_with_llm (OpenAI) returned type: {type(raw_openai_rating)}, value: {repr(raw_openai_rating)}")
                        
                        # Ensure OpenAI rating is an integer  
                        if isinstance(raw_openai_rating, str):
                            openai_rating = extract_rating_from_text(raw_openai_rating)
                        elif isinstance(raw_openai_rating, int):
                            openai_rating = raw_openai_rating
                        else:
                            print(f"WARNING: rate_description_with_llm (OpenAI) returned {type(raw_openai_rating)}, using default rating 5")
                            openai_rating = 5
                        # Ensure rating is an integer
                        if not isinstance(openai_rating, int):
                            openai_rating = 5  # Default fallback
                        print(f"OpenAI fallback - Rating: {openai_rating}/10")
                        print(f"OpenAI description: {openai_desc[:200]}{'...' if len(openai_desc) > 200 else ''}")
                        if openai_rating > new_rating:
                            print(f"Using OpenAI version (better rating: {openai_rating} > {new_rating})")
                            new_desc = openai_desc
                            print(f"DEBUG: Final new_desc (OpenAI) type: {type(new_desc)}, value: {repr(new_desc[:100] if isinstance(new_desc, str) else new_desc)}")
                            new_rating = openai_rating
                        else:
                            print(f"Keeping original generated version (rating: {new_rating} >= {openai_rating})")
                            print(f"DEBUG: Final new_desc (original) type: {type(new_desc)}, value: {repr(new_desc[:100] if isinstance(new_desc, str) else new_desc)}")

                    if new_rating > original_rating or "OPENAI_MODEL" in raw_desc:
                        print(Fore.GREEN + f"DESCRIPTION IMPROVED: {original_rating}/10 -> {new_rating}/10")
                        print(Fore.GREEN + "→ Updating description on eBay")
                        creds = load_credentials()
                        api = Trading(
                            appid=creds["appid"],
                            devid=creds["devid"],
                            certid=creds["certid"],
                            token=creds["token"],
                            config_file=None,
                            timeout=60,
                        )
                        # Ensure new_desc is a string and debug type
                        print(f"DEBUG: Pre-escape new_desc type: {type(new_desc)}, value: {repr(new_desc[:100] if isinstance(new_desc, str) else new_desc)}")
                        
                        # Convert to string if not already a string
                        if not isinstance(new_desc, str):
                            print(f"DEBUG: Converting non-string {type(new_desc)} to string")
                            if new_desc is None:
                                new_desc = ""
                            elif isinstance(new_desc, (int, float)):
                                new_desc = str(new_desc)
                            elif hasattr(new_desc, '__str__'):
                                new_desc = str(new_desc)
                            else:
                                print(f"DEBUG: Cannot convert {type(new_desc)} to string, using empty string")
                                new_desc = ""
                        
                        print(f"DEBUG: Final new_desc before escape: type={type(new_desc)}, len={len(new_desc) if isinstance(new_desc, str) else 'N/A'}")
                        
                        # DO NOT ESCAPE HTML - the description should contain actual HTML tags for formatting
                        # The escape() function was converting < to &lt; and > to &gt; which broke the HTML
                        # eBay expects actual HTML in the description field
                        # Apply one final cleaning pass to ensure no <pre> tags or escaped HTML slipped through
                        escaped_desc = clean_llm_description_output(new_desc)
                        print(f"DEBUG: Applied final clean_llm_description_output before eBay, type: {type(escaped_desc)}")
                        
                        # Ensure ItemID is a string
                        item_id_str = str(item_id) if item_id is not None else ""
                        print(f"DEBUG: item_id type: {type(item_id)}, value: {repr(item_id)}")
                        print(f"DEBUG: item_id_str type: {type(item_id_str)}, value: {repr(item_id_str)}")
                        print(f"DEBUG: escaped_desc type: {type(escaped_desc)}, length: {len(escaped_desc) if isinstance(escaped_desc, str) else 'N/A'}")
                        
                        # Prepare API call data with explicit types
                        # Wrap description in CDATA to prevent XML parsing issues
                        cdata_desc = f"<![CDATA[{escaped_desc}]]>"
                        api_data = {
                            "Item": {
                                "ItemID": item_id_str,
                                "Description": cdata_desc,
                            }
                        }
                        print(f"DEBUG: About to call api.execute with data types: ItemID={type(api_data['Item']['ItemID'])}, Description={type(api_data['Item']['Description'])}")
                        
                        # Add retry logic for description update
                        max_retries = 3
                        success = False
                        for retry_attempt in range(max_retries):
                            try:
                                if retry_attempt > 0:
                                    print(f"[RETRY] Attempt {retry_attempt + 1}/{max_retries} for description update")
                                    import time
                                    time.sleep(2 ** retry_attempt)  # Exponential backoff
                                
                                api.execute("ReviseFixedPriceItem", api_data)
                                print(Fore.GREEN + f"✓ Successfully updated description for item {item_id}" + Style.RESET_ALL)
                                success = True
                                break
                            except Exception as api_error:
                                if retry_attempt < max_retries - 1:
                                    print(f"[WARNING] Description update failed on attempt {retry_attempt + 1}: {str(api_error)[:100]}")
                                    continue
                                else:
                                    print(f"[ERROR] Description update failed after {max_retries} attempts: {api_error}")
                                    import traceback
                                    print(f"DEBUG: API error traceback: {traceback.format_exc()}")
                                    
                                    # Save problematic description to file for debugging
                                    error_file = f"error_description_{item_id}.html"
                                    try:
                                        with open(error_file, "w", encoding="utf-8") as ef:
                                            ef.write(f"Item ID: {item_id}\n")
                                            ef.write(f"Error: {api_error}\n")
                                            ef.write("="*80 + "\n")
                                            ef.write(escaped_desc)  # Save the CLEANED version that was sent to eBay
                                        print(f"DEBUG: Saved problematic description to {error_file}")
                                    except:
                                        pass
                                    
                                    raise  # Re-raise the exception
                        
                        if success:
                            clear_item_details_cache(item_id)
                        updated_desc += 1
                        log_data["DescriptionImproved"] = True
            else:
                print("Skipping description processing (has missing required/preferred specifics)")
        except Exception as e:
            print(f"[ERROR] description update error: {e}")
            log_data["FailureReason"] = "Description update error"
            
            # Enhanced error logging
            try:
                from ebay_error_logger import log_ebay_error
                log_ebay_error(
                    item_id=str(item_id),
                    operation="update_description",
                    error=e,
                    attempted_title=title,
                    attempted_description=new_desc if 'new_desc' in locals() else None,
                    attempted_specifics=None,
                    api_response=getattr(e, 'response', None),
                    additional_context={
                        "original_rating": desc_rating,
                        "improved_rating": improved_rating if 'improved_rating' in locals() else None,
                        "category_id": category_id,
                        "missing_required": missing_required,
                        "missing_preferred": missing_preferred
                    }
                )
            except:
                pass  # Don't let error logging failure stop the main process

        log_entry(log_data)
        report.append(report_entry)

    print("\n" + "=" * 30 + " Report Generation Complete " + "=" * 30)
    print(
        f"Processed {len(report)} listings — {updated_titles} titles and {updated_desc} descriptions updated."
    )
    return report


# from ebay_utils import (
#     get_all_active_listings,
#     get_category_id_for_item,
#     get_image_count_for_item,
# )


def create_listing_csv_with_photos(csv_filename="listing_photos.csv"):
    listings = get_all_active_listings()
    data = []
    for listing in listings:
        item_id = listing.get("ItemID")
        # existing fields
        category = listing.get("PrimaryCategory") or get_category_id_for_item(item_id)
        photo_count = get_image_count_for_item(item_id)

        # NEW: fetch the CustomLabel (SKU) from the combined details
        combined = _get_item_details_combined(item_id)
        custom_label = combined.get("CustomLabel") if combined else ""

        data.append(
            {
                "ListingID": item_id,
                "CustomLabel": custom_label,
                "Category": category,
                "PhotoCount": photo_count,
            }
        )

    df = pd.DataFrame(data)
    df.to_csv(csv_filename, index=False)
    print(f"CSV file '{csv_filename}' created with {len(df)} listings.")


@cache(dir=CACHE_DIR_CATEGORY_NAMES)
def get_category_name(category_id, marketplace_id="EBAY_US"):
    """
    Fetches the eBay category name for a given category ID using the Taxonomy API.
    Caches results for efficiency.
    """
    if not category_id:
        return None
    try:
        oauth_token = get_oauth_token()
        if not oauth_token:
            print("Failed to obtain OAuth token for category name lookup")
            return None
    except Exception as e:
        print(f"OAuth error for category name lookup - skipping: {e}")
        return None
    url = f"https://api.ebay.com/commerce/taxonomy/v1/category_tree/0/get_category_subtree"
    params = {"category_id": str(category_id)}
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        # The rootCategoryNode is the one you asked for
        node = data.get("categorySubtreeNode", {})
        if node and "category" in node:
            return node["category"].get("categoryName")
        return None
    except Exception as e:
        print(
            Fore.RED
            + f"[ERROR] Could not fetch category name for ID {category_id}: {e}"
        )
        return None


from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError


import pandas as pd
from typing import List, Dict

# from ebay_utils import get_all_active_listings # Assuming this is your existing module
import csv
import ollama  # Import the ollama library
import re  # CACHE_DIR_LLM For parsing the rating


@cache(dir=CACHE_DIR_LLM, expiry=timedelta(days=30).total_seconds())
def get_llm_title(description: str, model_preset: str = None) -> str:
    """
    Generates a better listing title using a local Ollama model.
    Args:
        description: The listing description.
        model_preset: Model preset ('fast', 'balanced', 'quality') or model name. 
                     Defaults to environment setting or 'balanced'.
    Returns:
        A suggested new title.
    """
    if model_preset is None:
        model_preset = DEFAULT_MODEL_PRESET
    model_name = get_ollama_model(model_preset)
    start = time.time()

    prompt = f"""
    You are an expert eBay seller and SEO copywriter. Given the following product description, generate a compelling and optimized eBay listing title. Follow these guidelines:

Use up to 80 characters (do not exceed this limit).

Start with the most important keywords, such as brand and product name.

Include key features, attributes, or benefits that buyers search for (e.g., model, size, color, compatibility, or unique selling points).

Ensure the title is clear, accurate, and easy to read-write for humans, not just search engines.

Use proper capitalization (capitalize the first letter of most words), but avoid ALL CAPS.

Avoid special characters, unnecessary punctuation, prices, promotional phrases, or misleading claims.

Do not use abbreviations or foreign words unless they are part of the official product name.

Do not include contact info, HTML, or formatting codes.

Make sure the title is honest and accurately represents the item.

Your response should only include a single 80 character or less string of the best title you could come up with.  Do not include text like "Here are some options for ebay titles". Do not include your reasoning. Do not say "Here’s a compelling and optimized eBay title:". Do not say "Here’s an optimized eBay listing title, adhering to all the specified guidelines".  Just give me the title. 

Product Description:
    "{description}"

    Generated Title:
    """
    try:
        response = ollama.chat(
            model=model_name,  # Use the configurable model
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        suggested_title = response["message"]["content"].strip()
        duration = time.time() - start
        print(f"[TIMING] get_llm_title took {duration:.2f} seconds (not cached)")
        if ":" in suggested_title:
            suggested_title = suggested_title.split(":")[1].strip()
        return suggested_title[:80]
    except Exception as e:
        print(Fore.RED + f"Error communicating with Ollama for title generation: {e}")
        return f"Error: Could not generate title for: {description[:50]}..."


@cache(dir=CACHE_DIR_LLM, expiry=timedelta(days=30).total_seconds())
def rate_title_with_llm(title: str, description: str, model_preset: str = None) -> int:
    """
    Rates the title of a product for an eBay listing using Ollama or OpenAI,
    given the description, on a scale from 1 to 10.
    Args:
        title: The listing title.
        description: The listing description.
        model_preset: Model preset ('fast', 'balanced', 'quality') or model name.
    Returns:
        A rating from 1 to 10. Defaults to 1 on error.
    """
    # Check if we should use OpenAI (default) or Ollama
    use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    
    if not use_ollama:
        # Use OpenAI for rating
        return rate_title_with_openai(title, description)
    
    # Use Ollama
    if model_preset is None:
        model_preset = DEFAULT_MODEL_PRESET
    model_name = get_ollama_model(model_preset)
    start = time.time()

    if "Error:" in title:  # If title generation itself failed
        return 1

    prompt = f"""
    You are an AI assistant evaluating eBay product titles.
    Based on the provided Product Description and Product Title, rate the effectiveness of the Product Title for an eBay listing.
    Use a scale of 1 to 10, where 1 is a very poor title and 10 is an excellent title.

    Consider the following criteria for a good eBay title:
    - Clarity: Is the title easy to understand?
    - Keyword Relevance: Does it include important keywords from the description that buyers would search for?
    - Attractiveness: Does it sound appealing to a potential buyer?
    - Accuracy: Does it accurately represent the product described?
    - Formatting: Is proper capitalization used (capitalize the first letter of most words), with no all-caps, unnecessary spaces, or special characters?
    - Compliance: Does the title avoid abbreviations (unless standard), prices, promotional text, HTML, or misleading information?
    - Uniqueness: Is the title unique and does it stand out from competitors?
    - Keyword Stuffing: Is the title free from keyword stuffing or repetition?
    - Completeness: Does the title include the product name, key features (such as brand, model, size, color), and main selling points or benefits?
    - Length: Is the title close to, but not exceeding, the 80-character limit?

    Product Description:
    "{description}"

    Product Title:
    "{title}"

    Based on these criteria, provide a single numerical rating from 1 to 10.
    Output ONLY the number. For example, if the rating is 7, just output "7".
    Rating (1-10):
    """
    try:
        response = ollama.chat(
            model=model_name,  # Use the configurable model
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        content = response["message"]["content"].strip()

        # Use the robust extraction function
        rating = extract_rating_from_text(content)
        
        duration = time.time() - start
        print(
            f"[TIMING] rate_title_with_llm took {duration:.2f} seconds (not cached)"
        )
        
        return rating

    except Exception as e:
        print(Fore.RED + f"Error communicating with Ollama for title rating: {e}")
        return 1  # Default rating on error


import re
from bs4 import BeautifulSoup  # add to imports near the top if not present
from html import unescape
from colorama import Fore

# --------------------------------------------------------------------------- #
# helper – strip ALL markup & CSS from a block of HTML                        #
# --------------------------------------------------------------------------- #
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _plain_text(html_block: str) -> str:
    """
    Return readable plain text from an HTML fragment:
      • drop <style>, <script>, and <link> blocks entirely
      • strip every other tag
      • unescape entities
      • collapse consecutive whitespace
    """
    if not html_block:
        return ""

    # 1) remove style / script / link elements outright
    soup = BeautifulSoup(html_block, "html.parser")
    for tag in soup(["style", "script", "link"]):
        tag.decompose()

    cleaned = str(soup)

    # 2) strip any remaining tags
    cleaned = _HTML_TAG_RE.sub("", cleaned)

    # 3) unescape & normalise whitespace
    cleaned = unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# --------------------------------------------------------------------------- #
#  REPLACEMENT: process_title                                                 #
# --------------------------------------------------------------------------- #
@cache(dir=CACHE_DIR_LLM, expiry=timedelta(days=90).total_seconds())
def process_title(description: str, title: str, MIN_TITLE_RATING: int = 10) -> str:
    """
    Rate the current title and—if it’s not already perfect—ask an LLM
    for a better one.  The description fed to the LLM (and printed for
    debugging) is stripped down to plain text so no CSS/HTML noise ever
    appears in your logs.
    """
    # ---- scrub the description completely ----
    plain_desc = _plain_text(description)

    # ---- 1. rate the existing title ----------------------------------------
    original_rating = rate_title_with_llm(title, plain_desc)
    # Ensure rating is an integer
    if not isinstance(original_rating, int):
        original_rating = 5  # Default fallback
    print(f"TITLE - Original rating: {original_rating}/10 (threshold: {MIN_TITLE_RATING})")
    print(f"Current title: {title}")

    # ---- 2. maybe generate a replacement -----------------------------------
    if original_rating < MIN_TITLE_RATING:
        print(f"Rating too low, generating new title...")
        new_title = get_llm_title(plain_desc)
        new_rating = rate_title_with_llm(new_title, plain_desc)
        # Ensure rating is an integer
        if not isinstance(new_rating, int):
            new_rating = 5  # Default fallback
        print(f"Generated new title - Rating: {new_rating}/10")
        print(f"New title: {new_title}")

        # ---- keep the better one -------------------------------------------
        if new_rating > original_rating:
            print(Fore.GREEN + f"TITLE IMPROVED: {original_rating}/10 -> {new_rating}/10")
            return new_title
        else:
            print(f"Keeping original title (rating: {original_rating} >= {new_rating})")

    # Either already good enough or no improvement  
    else:
        print(f"Title rating sufficient ({original_rating}/10 >= {MIN_TITLE_RATING})")
    return title


def create_listing_report(listings: List[Dict]) -> List[Dict]:
    """
    Creates a report that lists the listing ID, its current title, the rating of its current
    title, a suggested new title, and the rating of the new title.
    Args:
        listings: A list of dictionaries containing listing data.
    Returns:
        A list of dictionaries, where each dictionary represents a listing report.
    """
    report = []
    for i, listing in enumerate(listings):
        listing_id = listing.get("ItemID")
        current_title = listing.get("Title", "")
        description = listing.get("Description", "")
        if not description:
            description = current_title  # Fallback

        print(f"\nProcessing listing {i+1}/{len(listings)}: ID {listing_id}")

        # Rate the current title
        print(f'  Rating current title: "{current_title}"')
        current_title_rating = rate_title_with_llm(current_title, description)
        print(f"  Current title rating: {current_title_rating}")

        # Use LLM to calculate a better title
        print(f'  Generating new title for description: "{description[:100]}..."')
        suggested_title = get_llm_title(description)
        print(f'  Suggested new title: "{suggested_title}"')

        # Rate the suggested title
        print(f'  Rating suggested title: "{suggested_title}"')
        suggested_title_rating = rate_title_with_llm(suggested_title, description)
        print(f"  Suggested title rating: {suggested_title_rating}")

        report_entry = {
            "Listing ID": listing_id,
            "Current Title": current_title,
            "Current Title Rating": current_title_rating,
            "Suggested New Title": suggested_title,
            "Suggested New Title Rating": suggested_title_rating,
        }
        report.append(report_entry)
    return report


def remove_undesired_characters(text: str) -> str:
    # Remove emojis and other non-standard characters (e.g. ✅, ❗️, 💡)
    text = (
        text.replace("<p>```html</p>", "")
        .replace("<p>```</p>", "")
        .replace(", OPENAI_MODEL=gpt-4o", "")
        .replace("```", "")
    )
    if "</html>" in text:
        text = text.split("</html>")[0]
    return re.sub(r"[^\x00-\x7F]+", "", text)


@cache(dir=CACHE_DIR_LLM_DESC, expiry=timedelta(days=30).total_seconds())
def generate_description_with_llm(description: str, specifics: dict, model_preset: str = None) -> str:
    """
    Generates a compelling eBay product description using the original description and item specifics,
    formatted with minimal HTML tags supported by eBay for better readability.
    Args:
        description: Original description.
        specifics: Item specifics dictionary.
        model_preset: Model preset ('fast', 'balanced', 'quality') or model name.
    """
    # Check if we should use OpenAI (default) or Ollama
    use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    
    if not use_ollama:
        # Use OpenAI
        return generate_description_with_openai(description, specifics)
    
    # Use Ollama
    if model_preset is None:
        model_preset = DEFAULT_MODEL_PRESET
    model_name = get_ollama_model(model_preset)
    start = time.time()

    prompt = f"""
You are an expert eBay seller. Rewrite the following eBay product description using the provided item specifics.
Create a clear, compelling, and professional product description suitable for an eBay listing.
Format the description using only the following HTML tags supported by eBay for readability:
<p>, <b>, <i>, <ul>, <li>, <br>
Guidelines:
- Use <p> for paragraphs, <ul>/<li> for bullet points, <b> for emphasis, and <br> for line breaks.
- Highlight key product features from the item specifics in a bulleted list.
- Keep it concise (under 500 words) and easy to read.
- Do NOT use any other HTML tags or inline styles.
- Do NOT repeat the product title or category name unless it’s helpful.
- Only return the improved product description, with minimal HTML formatting.
Original Description:
{description}
Item Specifics:
{json.dumps(specifics, indent=2)}
Write only the improved product description below. Do not return anything else. Make sure you use the limited HTML codes.  Do not tell me your reasoning. Do not use special characters like "✅".
"""
    try:
        response = ollama.chat(
            model=model_name,  # Use the configurable model
            messages=[{"role": "user", "content": prompt}],
        )

        content = response["message"]["content"].strip()
        cleaned_content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        cleaned_content = remove_undesired_characters(cleaned_content)
        duration = time.time() - start
        print(
            f"[TIMING] generate_description_with_llm took {duration:.2f} seconds (not cached)"
        )
        return cleaned_content.strip()
    except Exception as e:
        print(Fore.RED + f"[LLM ERROR] Failed to generate description: {e}")
        return escape(description)  # fallback


# @cache(dir=CACHE_DIR_LLM, expiry=timedelta(days=30).total_seconds())
def rate_description_with_llm(description: str, specifics: dict, model_preset: str = None) -> int:
    """
    Rates the effectiveness of a product description for eBay based on clarity, completeness, and relevance.
    Returns a score from 1 to 10.
    Args:
        description: The product description.
        specifics: Item specifics dictionary.
        model_preset: Model preset ('fast', 'balanced', 'quality') or model name.
    """
    # Check if we should use OpenAI (default) or Ollama
    use_ollama = os.getenv('USE_OLLAMA', 'false').lower() == 'true'
    
    if not use_ollama:
        # Use OpenAI for rating
        return rate_description_with_openai(description, specifics)
    
    # Use Ollama
    if model_preset is None:
        model_preset = DEFAULT_MODEL_PRESET
    model_name = get_ollama_model(model_preset)
    start = time.time()
    prompt = f"""
You are an AI assistant evaluating an eBay product description.
Based on the provided description and item specifics, rate the quality of the description on a scale from 1 to 10.

Criteria:
- Clarity and readability
- Relevance to the item specifics
- Usefulness for the buyer
- Conciseness (avoid rambling or fluff)
- Professional tone (not overly casual or robotic)
- Does not contain the words OpenAI

Item Specifics:
{json.dumps(specifics, indent=2)}

Product Description:
{description}

Output ONLY a number from 1 to 10. Example: 7
"""
    try:
        response = ollama.chat(
            model=model_name,  # Use the configurable model
            messages=[{"role": "user", "content": prompt}],
        )
        content = response["message"]["content"].strip()
        
        # Use the robust extraction function
        rating = extract_rating_from_text(content)
        
        duration = time.time() - start
        print(
            f"[TIMING]  rate_description_with_llm took {duration:.2f} seconds (not cached)"
        )
        
        return rating
    except Exception as e:
        print(Fore.RED + f"[LLM ERROR] Failed to rate description: {e}")
        return 1


def save_report_to_csv(
    report: List[Dict], filename: str = "listing_report.csv"
) -> None:
    """
    Saves the listing report to a CSV file.
    Args:
        report: A list of dictionaries, where each dictionary represents a listing report.
        filename: The name of the CSV file to save the report to.
    """
    if not report:
        print("No data to export.")
        return

    keys = report[0].keys()  # Get keys from the first report entry

    with open(filename, "w", newline="", encoding="utf-8") as output_file:
        dict_writer = csv.DictWriter(output_file, keys)
        dict_writer.writeheader()
        dict_writer.writerows(report)

    print(f"\nReport saved to {filename}")


def find_latest_traffic_report(downloads_dir=None):
    """
    Find the latest eBay traffic report CSV file in the downloads directory.
    
    Args:
        downloads_dir: Optional path to downloads directory. If None, uses user's Downloads folder.
    
    Returns:
        str: Full path to the latest traffic report file, or None if not found.
    """
    import glob
    from pathlib import Path
    
    if downloads_dir is None:
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    
    # Pattern for eBay traffic reports
    pattern = os.path.join(downloads_dir, "eBay-ListingsTrafficReport-*.csv")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No eBay traffic reports found in {downloads_dir}")
        return None
    
    # Sort by modification time and get the latest
    latest_file = max(files, key=os.path.getmtime)
    return latest_file


def parse_traffic_report(csv_file_path):
    """
    Parse eBay traffic report CSV and extract listing performance data.
    
    Args:
        csv_file_path: Path to the traffic report CSV file.
    
    Returns:
        pandas.DataFrame: Parsed traffic report data.
    """
    import pandas as pd
    
    try:
        # eBay reports have a few header lines before the actual data
        # Line 1: "-"
        # Line 2: "Disclaimers"
        # Line 3: disclaimer text
        # Line 4: blank line
        # Line 5: report period (single cell)
        # Line 6: actual column headers
        # So we skip the first 5 lines
        df = pd.read_csv(csv_file_path, skiprows=5, encoding='utf-8')
        
        # Clean column names (remove any extra spaces)
        df.columns = df.columns.str.strip()
        
        # Rename columns to simpler names for easier access
        column_mapping = {
            'Listing title': 'Title',
            'eBay item ID': 'Item ID',
            'Total page views': 'Page views',
            'Quantity sold': 'Quantity sold',
            'Quantity available': 'Quantity available',
            'Total impressions': 'Impressions',
            'Click-through rate = Page views from eBay site/Total impressions': 'CTR',
            'Sales conversion rate = Quantity sold/Total page views': 'Conversion rate'
        }
        
        # Rename columns that exist in the mapping
        for old_name, new_name in column_mapping.items():
            if old_name in df.columns:
                df.rename(columns={old_name: new_name}, inplace=True)
        
        # Clean Item ID column (remove ="..." format)
        if 'Item ID' in df.columns:
            df['Item ID'] = df['Item ID'].astype(str).str.replace('="', '').str.replace('"', '')
        
        # Convert numeric columns
        numeric_columns = ['Page views', 'Quantity available', 'Quantity sold', 'Impressions']
        for col in numeric_columns:
            if col in df.columns:
                # Remove commas, equals signs, quotes and convert to numeric
                df[col] = df[col].astype(str).str.replace(',', '').str.replace('=', '').str.replace('"', '')
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Calculate watch count if not available (using a dummy value for now)
        if 'Watch count' not in df.columns:
            # For eBay traffic reports, we don't have watch count, so we'll estimate based on impressions
            # This is a rough estimate: assume 1% of impressions result in watches
            df['Watch count'] = (df['Impressions'] * 0.01).fillna(0).astype(int)
        
        # Remove rows with NaN in critical columns
        df = df.dropna(subset=['Item ID', 'Title', 'Page views'])
        
        return df
    except Exception as e:
        print(f"Error parsing CSV file: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_top_performers(df, top_n=20, min_views=1):
    """
    Analyze and rank top performing eBay listings.
    
    Args:
        df: DataFrame with traffic report data.
        top_n: Number of top performers to return.
        min_views: Minimum page views to consider.
    
    Returns:
        dict: Analysis results including top performers by various metrics.
    """
    import pandas as pd
    
    if df is None or df.empty:
        return None
    
    # Filter out listings with very low or no views
    df_filtered = df[df['Page views'] >= min_views].copy()
    
    # Calculate engagement rate (watch count / page views)
    df_filtered['Engagement rate'] = (df_filtered['Watch count'] / df_filtered['Page views'] * 100).round(2)
    
    # Calculate conversion rate if sold data is available
    if 'Quantity sold' in df_filtered.columns:
        df_filtered['Conversion rate'] = (df_filtered['Quantity sold'] / df_filtered['Page views'] * 100).round(2)
    
    results = {
        'total_listings': len(df),
        'analyzed_listings': len(df_filtered),
        'top_by_views': df_filtered.nlargest(top_n, 'Page views')[
            ['Item ID', 'Title', 'Page views', 'Watch count', 'Engagement rate']
        ].to_dict('records'),
        'top_by_watch': df_filtered.nlargest(top_n, 'Watch count')[
            ['Item ID', 'Title', 'Page views', 'Watch count', 'Engagement rate']
        ].to_dict('records'),
        'top_by_engagement': df_filtered.nlargest(top_n, 'Engagement rate')[
            ['Item ID', 'Title', 'Page views', 'Watch count', 'Engagement rate']
        ].to_dict('records'),
    }
    
    # Add sales data if available
    if 'Quantity sold' in df_filtered.columns and df_filtered['Quantity sold'].sum() > 0:
        results['top_by_sales'] = df_filtered.nlargest(top_n, 'Quantity sold')[
            ['Item ID', 'Title', 'Page views', 'Quantity sold', 'Conversion rate']
        ].to_dict('records')
        results['top_by_conversion'] = df_filtered[df_filtered['Quantity sold'] > 0].nlargest(top_n, 'Conversion rate')[
            ['Item ID', 'Title', 'Page views', 'Quantity sold', 'Conversion rate']
        ].to_dict('records')
    
    # Calculate summary statistics
    results['summary'] = {
        'total_views': int(df['Page views'].sum()),
        'avg_views': round(df['Page views'].mean(), 2),
        'total_watches': int(df['Watch count'].sum()),
        'avg_engagement_rate': round(df_filtered['Engagement rate'].mean(), 2),
    }
    
    if 'Quantity sold' in df.columns:
        results['summary']['total_sold'] = int(df['Quantity sold'].sum())
        results['summary']['avg_conversion_rate'] = round(
            df_filtered[df_filtered['Quantity sold'] > 0]['Conversion rate'].mean(), 2
        ) if df_filtered['Quantity sold'].sum() > 0 else 0
    
    return results


def export_top_performers_report(results, output_file=None):
    """
    Export top performers analysis to a formatted text report and CSV files.
    
    Args:
        results: Analysis results from analyze_top_performers.
        output_file: Optional output file name for the report.
    
    Returns:
        str: Path to the generated report file.
    """
    import csv
    from datetime import datetime
    
    if results is None:
        print("No results to export")
        return None
    
    # Generate timestamp for file naming
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if output_file is None:
        output_file = f"traffic_analysis_report_{timestamp}.txt"
    
    # Create the text report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("EBAY LISTING TRAFFIC PERFORMANCE REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # Summary statistics
        f.write("SUMMARY STATISTICS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total Listings: {results['total_listings']}\n")
        f.write(f"Analyzed Listings: {results['analyzed_listings']}\n")
        f.write(f"Total Page Views: {results['summary']['total_views']:,}\n")
        f.write(f"Average Views per Listing: {results['summary']['avg_views']:.1f}\n")
        f.write(f"Total Watch Count: {results['summary']['total_watches']:,}\n")
        f.write(f"Average Engagement Rate: {results['summary']['avg_engagement_rate']:.1f}%\n")
        
        if 'total_sold' in results['summary']:
            f.write(f"Total Quantity Sold: {results['summary']['total_sold']}\n")
            f.write(f"Average Conversion Rate: {results['summary']['avg_conversion_rate']:.2f}%\n")
        
        f.write("\n")
        
        # Top performers by views
        f.write("TOP PERFORMERS BY PAGE VIEWS\n")
        f.write("-" * 40 + "\n")
        for i, item in enumerate(results['top_by_views'][:10], 1):
            f.write(f"{i}. Item {item['Item ID']}: {item['Page views']:,} views\n")
            f.write(f"   Title: {item['Title'][:60]}...\n" if len(item['Title']) > 60 else f"   Title: {item['Title']}\n")
            f.write(f"   Watches: {item['Watch count']} | Engagement: {item['Engagement rate']}%\n\n")
        
        # Top performers by engagement
        f.write("\nTOP PERFORMERS BY ENGAGEMENT RATE\n")
        f.write("-" * 40 + "\n")
        for i, item in enumerate(results['top_by_engagement'][:10], 1):
            f.write(f"{i}. Item {item['Item ID']}: {item['Engagement rate']}% engagement\n")
            f.write(f"   Title: {item['Title'][:60]}...\n" if len(item['Title']) > 60 else f"   Title: {item['Title']}\n")
            f.write(f"   Views: {item['Page views']:,} | Watches: {item['Watch count']}\n\n")
        
        # Sales data if available
        if 'top_by_sales' in results:
            f.write("\nTOP PERFORMERS BY SALES\n")
            f.write("-" * 40 + "\n")
            for i, item in enumerate(results['top_by_sales'][:10], 1):
                f.write(f"{i}. Item {item['Item ID']}: {item['Quantity sold']} sold\n")
                f.write(f"   Title: {item['Title'][:60]}...\n" if len(item['Title']) > 60 else f"   Title: {item['Title']}\n")
                f.write(f"   Views: {item['Page views']:,} | Conversion: {item['Conversion rate']}%\n\n")
    
    # Also export detailed CSV for further analysis
    csv_file = f"top_performers_{timestamp}.csv"
    if results['top_by_views']:
        import pandas as pd
        df_export = pd.DataFrame(results['top_by_views'])
        df_export.to_csv(csv_file, index=False, encoding='utf-8')
        print(f"Detailed CSV exported to: {csv_file}")
    
    print(f"Report saved to: {output_file}")
    return output_file


def find_latest_automagical_report(downloads_dir=None):
    """
    Find the latest Automagical campaign CSV file in the downloads directory.
    
    Args:
        downloads_dir: Optional path to downloads directory. If None, uses user's Downloads folder.
    
    Returns:
        str: Full path to the latest Automagical report file, or None if not found.
    """
    import glob
    
    if downloads_dir is None:
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    
    # Pattern for Automagical reports
    pattern = os.path.join(downloads_dir, "automagical_Listing_*.csv")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No Automagical reports found in {downloads_dir}")
        return None
    
    # Sort by modification time and get the latest
    latest_file = max(files, key=os.path.getmtime)
    return latest_file


def parse_automagical_report(csv_file_path):
    """
    Parse Automagical campaign CSV and extract listing performance data.
    
    Args:
        csv_file_path: Path to the Automagical CSV file.
    
    Returns:
        pandas.DataFrame: Parsed Automagical report data.
    """
    import pandas as pd
    
    try:
        # Skip first 2 lines (disclaimer and blank line)
        df = pd.read_csv(csv_file_path, skiprows=2, encoding='utf-8-sig')
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Clean Item ID column (ensure it's string)
        if 'Item ID' in df.columns:
            df['Item ID'] = df['Item ID'].astype(str)
        
        # Parse price columns (remove $ and convert to float)
        price_columns = ['Price (Current or Last Price)', 'Total Promoted Listings Sales', 
                        'Ad fees', 'Average cost per sale', 'Promoted Listings Sales (via eBay placements)',
                        'Ad fees (via eBay placements)']
        for col in price_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace('$', '').str.replace(',', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Parse percentage columns
        pct_columns = ['Promoted Listings Conversion rate (Promoted Listings Sold quantity/Promoted Listings Clicks)',
                      'Promoted Listings Contribution (Promoted Listings Sold quantity/Total Quantity Sold)',
                      'Promoted Listings Conversion Rate (via eBay placements)']
        for col in pct_columns:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace('%', '').str.strip()
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Parse numeric columns
        numeric_columns = ['Promoted Listings Impressions (via eBay Placements)', 
                          'Total Promoted Listings Clicks', 'Total Promoted Listings Sold quantity',
                          'Organic Sold Quantity', 'Organic Clicks', 'Organic Impressions',
                          'Promoted Listings Clicks (via eBay placements)',
                          'Promoted Listings Sold Quantity (via eBay placements)']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
        
        return df
    except Exception as e:
        print(f"Error parsing Automagical CSV file: {e}")
        import traceback
        traceback.print_exc()
        return None


def merge_traffic_and_campaign_data(traffic_df, automagical_df):
    """
    Merge traffic report and Automagical campaign data on Item ID.
    
    Args:
        traffic_df: DataFrame from parse_traffic_report()
        automagical_df: DataFrame from parse_automagical_report()
    
    Returns:
        pandas.DataFrame: Merged data with combined metrics.
    """
    import pandas as pd
    
    if traffic_df is None or automagical_df is None:
        return None
    
    # Ensure Item ID columns are strings for merging
    traffic_df['Item ID'] = traffic_df['Item ID'].astype(str)
    automagical_df['Item ID'] = automagical_df['Item ID'].astype(str)
    
    # Merge on Item ID
    merged_df = pd.merge(
        traffic_df,
        automagical_df,
        on='Item ID',
        how='outer',
        suffixes=('_traffic', '_campaign')
    )
    
    # Calculate additional metrics
    merged_df['Has_Campaign_Data'] = ~merged_df['Campaign name'].isna()
    merged_df['Total_Sales'] = merged_df['Total Promoted Listings Sold quantity'].fillna(0) + merged_df['Organic Sold Quantity'].fillna(0)
    
    # Calculate effective ad rate (ad fees / sales)
    merged_df['Effective_Ad_Rate'] = 0.0
    mask = merged_df['Total Promoted Listings Sales'] > 0
    merged_df.loc[mask, 'Effective_Ad_Rate'] = (
        merged_df.loc[mask, 'Ad fees'] / merged_df.loc[mask, 'Total Promoted Listings Sales'] * 100
    )
    
    return merged_df


def analyze_campaign_performance(merged_df):
    """
    Analyze campaign performance and identify optimization opportunities.
    
    Args:
        merged_df: Merged DataFrame from merge_traffic_and_campaign_data()
    
    Returns:
        dict: Analysis results with performance metrics and insights.
    """
    import pandas as pd
    import numpy as np
    
    if merged_df is None or merged_df.empty:
        return None
    
    # Filter for items with campaign data
    campaign_items = merged_df[merged_df['Has_Campaign_Data']].copy()
    
    # Calculate key metrics
    results = {
        'total_items': len(merged_df),
        'campaign_items': len(campaign_items),
        'metrics': {}
    }
    
    # Overall campaign metrics
    results['metrics']['total_ad_fees'] = campaign_items['Ad fees'].sum()
    results['metrics']['total_promoted_sales'] = campaign_items['Total Promoted Listings Sales'].sum()
    results['metrics']['total_promoted_clicks'] = campaign_items['Total Promoted Listings Clicks'].sum()
    results['metrics']['total_promoted_sold'] = campaign_items['Total Promoted Listings Sold quantity'].sum()
    results['metrics']['total_organic_sold'] = campaign_items['Organic Sold Quantity'].sum()
    results['metrics']['total_organic_clicks'] = campaign_items['Organic Clicks'].sum()
    results['metrics']['total_promoted_impressions'] = campaign_items['Promoted Listings Impressions (via eBay Placements)'].sum()
    results['metrics']['total_organic_impressions'] = campaign_items['Organic Impressions'].sum()
    
    # Calculate average rates
    if results['metrics']['total_promoted_sales'] > 0:
        results['metrics']['avg_effective_ad_rate'] = (
            results['metrics']['total_ad_fees'] / results['metrics']['total_promoted_sales'] * 100
        )
    else:
        results['metrics']['avg_effective_ad_rate'] = 0
    
    # Conversion metrics
    if results['metrics']['total_promoted_clicks'] > 0:
        results['metrics']['overall_conversion_rate'] = (
            results['metrics']['total_promoted_sold'] / results['metrics']['total_promoted_clicks'] * 100
        )
    else:
        results['metrics']['overall_conversion_rate'] = 0
    
    # Calculate sales source percentages
    total_all_sales = results['metrics']['total_promoted_sold'] + results['metrics']['total_organic_sold']
    if total_all_sales > 0:
        results['metrics']['promoted_sales_percent'] = (
            results['metrics']['total_promoted_sold'] / total_all_sales * 100
        )
        results['metrics']['organic_sales_percent'] = (
            results['metrics']['total_organic_sold'] / total_all_sales * 100
        )
    else:
        results['metrics']['promoted_sales_percent'] = 0
        results['metrics']['organic_sales_percent'] = 0
    
    # Calculate organic probability (organic sales / total listings)
    results['metrics']['organic_sale_probability'] = (
        results['metrics']['total_organic_sold'] / results['total_items'] * 100
        if results['total_items'] > 0 else 0
    )
    
    # Calculate promoted probability (promoted sales / items with clicks)
    items_with_clicks = campaign_items[campaign_items['Total Promoted Listings Clicks'] > 0]
    results['metrics']['promoted_sale_probability'] = (
        results['metrics']['total_promoted_sold'] / len(items_with_clicks) * 100
        if len(items_with_clicks) > 0 else 0
    )
    
    # Calculate click source percentages
    total_all_clicks = results['metrics']['total_promoted_clicks'] + results['metrics']['total_organic_clicks']
    if total_all_clicks > 0:
        results['metrics']['promoted_clicks_percent'] = (
            results['metrics']['total_promoted_clicks'] / total_all_clicks * 100
        )
        results['metrics']['organic_clicks_percent'] = (
            results['metrics']['total_organic_clicks'] / total_all_clicks * 100
        )
    else:
        results['metrics']['promoted_clicks_percent'] = 0
        results['metrics']['organic_clicks_percent'] = 0
    
    # Calculate impression source percentages
    total_all_impressions = results['metrics']['total_promoted_impressions'] + results['metrics']['total_organic_impressions']
    if total_all_impressions > 0:
        results['metrics']['promoted_impressions_percent'] = (
            results['metrics']['total_promoted_impressions'] / total_all_impressions * 100
        )
        results['metrics']['organic_impressions_percent'] = (
            results['metrics']['total_organic_impressions'] / total_all_impressions * 100
        )
    else:
        results['metrics']['promoted_impressions_percent'] = 0
        results['metrics']['organic_impressions_percent'] = 0
    
    # Identify high and low performers - vectorized for performance
    campaign_items['Performance_Score'] = 0.0
    
    # Factor 1: Page views (weight: 30%)
    views_rank = campaign_items['Page views'].rank(pct=True, method='average')
    campaign_items['Performance_Score'] += views_rank * 30
    
    # Factor 2: Conversion rate (weight: 40%)
    # Calculate conversion rate for all items at once
    campaign_items['Conv_Rate'] = 0.0
    clicks_mask = campaign_items['Total Promoted Listings Clicks'] > 0
    campaign_items.loc[clicks_mask, 'Conv_Rate'] = (
        campaign_items.loc[clicks_mask, 'Total Promoted Listings Sold quantity'] / 
        campaign_items.loc[clicks_mask, 'Total Promoted Listings Clicks']
    )
    conv_rank = campaign_items['Conv_Rate'].rank(pct=True, method='average')
    campaign_items['Performance_Score'] += conv_rank * 40
    
    # Factor 3: Organic performance (weight: 30%)
    organic_rank = campaign_items['Organic Clicks'].rank(pct=True, method='average')
    campaign_items['Performance_Score'] += organic_rank * 30
    
    # Clean up temporary column
    campaign_items = campaign_items.drop('Conv_Rate', axis=1)
    
    # Categorize items
    results['top_performers'] = campaign_items.nlargest(20, 'Performance_Score')[
        ['Item ID', 'Title_traffic', 'Page views', 'Total Promoted Listings Clicks', 
         'Total Promoted Listings Sold quantity', 'Ad fees', 'Performance_Score']
    ].to_dict('records')
    
    results['underperformers'] = campaign_items[
        (campaign_items['Total Promoted Listings Clicks'] > 5) & 
        (campaign_items['Total Promoted Listings Sold quantity'] == 0)
    ][['Item ID', 'Title_traffic', 'Page views', 'Total Promoted Listings Clicks', 'Ad fees']].to_dict('records')
    
    # Items with high organic but low promoted performance
    results['organic_winners'] = campaign_items[
        (campaign_items['Organic Clicks'] > campaign_items['Total Promoted Listings Clicks'] * 2) &
        (campaign_items['Organic Clicks'] > 10)
    ][['Item ID', 'Title_traffic', 'Organic Clicks', 'Total Promoted Listings Clicks']].to_dict('records')
    
    return results


def recommend_campaign_settings(analysis_results, current_cap=None, current_modifier=None):
    """
    Recommend optimal ad cap rate and modifier based on performance analysis.
    
    Args:
        analysis_results: Results from analyze_campaign_performance()
        current_cap: Current ad cap rate (percentage)
        current_modifier: Current ad rate modifier (percentage)
    
    Returns:
        dict: Recommendations with reasoning.
    """
    if analysis_results is None:
        return None
    
    metrics = analysis_results['metrics']
    recommendations = {
        'current_cap': current_cap,
        'current_modifier': current_modifier,
        'recommended_cap': None,
        'recommended_modifier': None,
        'reasoning': [],
        'expected_impact': []
    }
    
    # Analyze current effectiveness
    avg_ad_rate = metrics['avg_effective_ad_rate']
    conversion_rate = metrics['overall_conversion_rate']
    total_promoted_sold = metrics['total_promoted_sold']
    total_organic_sold = metrics['total_organic_sold']
    
    # Decision logic for ad cap
    if avg_ad_rate > 0:
        if conversion_rate < 1.0 and total_promoted_sold < 5:
            # Poor conversion, reduce cap to minimize losses
            recommendations['recommended_cap'] = min(avg_ad_rate * 0.8, 5.0)
            recommendations['reasoning'].append(
                f"Low conversion rate ({conversion_rate:.1f}%) suggests reducing ad cap to minimize costs"
            )
        elif conversion_rate > 5.0:
            # Good conversion, can afford higher cap for more visibility
            recommendations['recommended_cap'] = min(avg_ad_rate * 1.5, 15.0)
            recommendations['reasoning'].append(
                f"Strong conversion rate ({conversion_rate:.1f}%) justifies higher ad cap for increased visibility"
            )
        else:
            # Moderate performance
            recommendations['recommended_cap'] = min(avg_ad_rate * 1.1, 10.0)
            recommendations['reasoning'].append(
                f"Moderate performance suggests slight cap increase for optimization"
            )
    else:
        # No current ad spend data, start conservative
        recommendations['recommended_cap'] = 7.0
        recommendations['reasoning'].append(
            "No current ad performance data - starting with conservative 7% cap"
        )
    
    # Decision logic for modifier (small percentages like 0.1% to 0.5%)
    if total_organic_sold > total_promoted_sold * 2 and total_organic_sold > 10:
        # Strong organic performance, no modifier needed
        recommendations['recommended_modifier'] = 0
        recommendations['reasoning'].append(
            f"Strong organic performance ({total_organic_sold} organic vs {total_promoted_sold} promoted sales) - no modifier needed"
        )
    elif len(analysis_results['underperformers']) > analysis_results['campaign_items'] * 0.3:
        # Many underperformers, use minimal or no modifier
        recommendations['recommended_modifier'] = 0
        recommendations['reasoning'].append(
            f"High proportion of underperforming ads ({len(analysis_results['underperformers'])} items) - no modifier to avoid overpaying"
        )
    elif conversion_rate > 5.0 and total_promoted_sold > 20:
        # Excellent performance, use slightly higher modifier for edge
        recommendations['recommended_modifier'] = 0.3
        recommendations['reasoning'].append(
            f"Excellent conversion rate ({conversion_rate:.1f}%) - using 0.3% modifier for slight competitive edge"
        )
    elif conversion_rate > 3.0 and total_promoted_sold > 10:
        # Good performance, small modifier for positioning
        recommendations['recommended_modifier'] = 0.2
        recommendations['reasoning'].append(
            f"Good conversion performance - using 0.2% modifier to slightly outbid default rates"
        )
    elif conversion_rate > 1.5:
        # Moderate performance, minimal modifier
        recommendations['recommended_modifier'] = 0.1
        recommendations['reasoning'].append(
            "Moderate performance - using minimal 0.1% modifier to match market rates"
        )
    else:
        # Poor performance, no modifier
        recommendations['recommended_modifier'] = 0
        recommendations['reasoning'].append(
            f"Low conversion rate ({conversion_rate:.1f}%) - no modifier to minimize costs"
        )
    
    # Calculate expected impact
    if current_cap and current_modifier is not None:
        cap_change = recommendations['recommended_cap'] - current_cap
        modifier_change = recommendations['recommended_modifier'] - current_modifier
        
        if abs(cap_change) > 1:
            impact = "increase" if cap_change > 0 else "decrease"
            recommendations['expected_impact'].append(
                f"Ad cap change expected to {impact} maximum ad spend by {abs(cap_change):.1f}%"
            )
        
        if abs(modifier_change) > 0.05:  # Changed from 5 to 0.05 for small percentages
            if modifier_change > 0:
                recommendations['expected_impact'].append(
                    f"Adding {modifier_change:.1f}% modifier will slightly increase your bids above the recommended rate"
                )
            else:
                recommendations['expected_impact'].append(
                    f"Reducing modifier by {abs(modifier_change):.1f}% will align your bids closer to recommended rates"
                )
    
    # Add sales source analysis
    if 'organic_sales_percent' in metrics and 'promoted_sales_percent' in metrics:
        recommendations['sales_breakdown'] = {
            'organic_percent': metrics['organic_sales_percent'],
            'promoted_percent': metrics['promoted_sales_percent'],
            'organic_probability': metrics['organic_sale_probability'],
            'promoted_probability': metrics['promoted_sale_probability']
        }
        
        if metrics['organic_sales_percent'] > 20:
            recommendations['reasoning'].append(
                f"Note: {metrics['organic_sales_percent']:.1f}% of sales are organic - consider if ads are necessary for all items"
            )
    
    # Add 30-day attribution warning if high click-to-sale ratio
    if metrics['total_promoted_clicks'] > metrics['total_promoted_sold'] * 20:
        recommendations['reasoning'].append(
            "Note: eBay's 30-day attribution window means current clicks may generate future sales not yet reflected"
        )
    
    return recommendations


def get_item_price(item_id):
    """
    Get the current price of an eBay listing.
    
    Args:
        item_id: eBay item ID
        
    Returns:
        float: Current price of the item, or 0 if not found
    """
    try:
        # Load credentials
        creds = load_credentials()
        
        # Import Trading API
        from ebaysdk.trading import Connection as Trading
        
        # Create API client
        api = Trading(
            appid=creds["appid"],
            devid=creds["devid"],
            certid=creds["certid"],
            token=creds["token"],
            config_file=None,
            timeout=30,
        )
        
        # Get item details
        response = api.execute(
            "GetItem",
            {
                "ItemID": item_id,
                "DetailLevel": "ReturnSummary",
            },
        )
        
        item = response.dict().get("Item", {})
        
        # Try different price fields
        price = 0
        
        # First check SellingStatus (most reliable for active listings)
        if "SellingStatus" in item:
            selling_status = item.get("SellingStatus", {})
            if "CurrentPrice" in selling_status:
                if isinstance(selling_status["CurrentPrice"], dict):
                    price = float(selling_status["CurrentPrice"].get("value", 0))
                else:
                    price = float(selling_status.get("CurrentPrice", 0))
        
        # If no price yet, try other fields
        if price == 0:
            if "BuyItNowPrice" in item:
                if isinstance(item["BuyItNowPrice"], dict):
                    price = float(item["BuyItNowPrice"].get("value", 0))
                    if price == 0:
                        price = float(item["BuyItNowPrice"].get("Value", 0))
            elif "CurrentPrice" in item:
                price = float(item["CurrentPrice"].get("Value", 0))
            elif "StartPrice" in item:
                price = float(item["StartPrice"].get("Value", 0))
            
        return price
        
    except Exception as e:
        print(f"Error getting price for item {item_id}: {e}")
        return 0


def search_ebay_competitors(search_query, max_results=10):
    """
    Search eBay for competitor listings using the Finding API.
    
    Args:
        search_query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of competitor listings with price information
    """
    try:
        # Load credentials
        creds = load_credentials()
        app_id = creds.get("appid")
        
        # eBay Finding API endpoint
        url = "https://svcs.ebay.com/services/search/FindingService/v1"
        
        # API parameters
        params = {
            "OPERATION-NAME": "findItemsAdvanced",
            "SERVICE-VERSION": "1.13.0",
            "SECURITY-APPNAME": app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": search_query,
            "paginationInput.entriesPerPage": str(max_results),
            "sortOrder": "BestMatch",
            "itemFilter(0).name": "Condition",
            "itemFilter(0).value": "New",
            "itemFilter(1).name": "ListingType", 
            "itemFilter(1).value": "FixedPrice",
            "itemFilter(2).name": "HideDuplicateItems",
            "itemFilter(2).value": "true"
        }
        
        # Make API request
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            print(f"eBay API error: {response.status_code}")
            return []
            
        data = response.json()
        
        # Extract search results
        search_result = data.get("findItemsAdvancedResponse", [{}])[0]
        search_results = search_result.get("searchResult", [{}])[0]
        items = search_results.get("item", [])
        
        # Process and return items with relevant info
        competitors = []
        for item in items:
            try:
                listing = {
                    "itemId": item.get("itemId", [None])[0],
                    "title": item.get("title", [None])[0],
                    "sellingStatus": item.get("sellingStatus", []),
                    "condition": item.get("condition", [{}])[0].get("conditionDisplayName", [None])[0],
                    "viewItemURL": item.get("viewItemURL", [None])[0]
                }
                competitors.append(listing)
            except (IndexError, KeyError, TypeError):
                continue
                
        return competitors
        
    except Exception as e:
        print(f"Error searching eBay competitors: {e}")
        return []


# --- Main Execution Guard ---
if __name__ == "__main__":
    print("This script provides utility functions for eBay API interactions.")
    print(
        "To generate the report, import and call get_missing_item_specifics_report() from another script like test_ebay_utils.py."
    )
    print("ebay_utils.py finished execution (no direct action taken in __main__).")
