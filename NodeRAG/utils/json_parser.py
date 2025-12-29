"""
Safe JSON parsing utility for handling LLM responses that may contain markdown or malformed JSON.
"""
import json
import pandas as pd
from typing import Any, Optional


def safe_json_parse(json_str: Any) -> Optional[dict | list]:
    """
    Safely parse JSON strings with error handling - handles markdown formatting and unicode issues.
    
    Designed to parse JSON from LLM responses that may include:
    - Markdown code blocks (```json ... ```)
    - Invisible unicode characters
    - Extra whitespace
    - Missing or None values
    
    Args:
        json_str: JSON string to parse (can be string, None, or pandas NA)
    
    Returns:
        Parsed JSON object (dict or list) or None if parsing fails
    
    Examples:
        >>> safe_json_parse('{"key": "value"}')
        {'key': 'value'}
        
        >>> safe_json_parse('```json\\n{"key": "value"}\\n```')
        {'key': 'value'}
        
        >>> safe_json_parse(None)
        None
    """
    try:
        # Handle None and pandas NA values
        if json_str is None or pd.isna(json_str):
            return None
        
        # Convert to string if not already
        cleaned = str(json_str)
        
        # Remove invisible unicode characters and strip whitespace
        cleaned = cleaned.replace('\u202f', '').replace('\xa0', '').strip()
        
        # Handle empty or whitespace-only strings
        if not cleaned:
            return None
        
        # Clean JSON response - remove markdown formatting if present
        if cleaned.startswith('```json'):
            cleaned = cleaned.replace('```json', '', 1).strip()
            if cleaned.endswith('```'):
                cleaned = cleaned.rsplit('```', 1)[0].strip()
        elif cleaned.startswith('```'):
            cleaned = cleaned.replace('```', '', 1).strip()
            if cleaned.endswith('```'):
                cleaned = cleaned.rsplit('```', 1)[0].strip()
        
        # Parse the JSON
        return json.loads(cleaned)
        
    except (json.JSONDecodeError, ValueError, AttributeError, TypeError) as e:
        # Return None on any parsing error - let the caller handle it
        return None

