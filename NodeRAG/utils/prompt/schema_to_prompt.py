"""
Convert Pydantic schema models to prompt instruction strings for Gemma models.

Since Gemma models don't support native JSON mode, we append JSON schema
instructions directly to prompts to guide the model's output format.
"""
from typing import Type
from pydantic import BaseModel


def schema_to_prompt_instruction(schema_name: str) -> str:
    """
    Convert a schema model name to formatted JSON schema instructions for prompts.
    
    Args:
        schema_name: Name of the schema ('text_decomposition', 'relationship_reconstraction', etc.)
    
    Returns:
        Formatted schema instruction string to append to prompts
    """
    schemas = {
        'text_decomposition': TEXT_DECOMPOSITION_SCHEMA,
        'relationship_reconstraction': RELATIONSHIP_RECONSTRUCTION_SCHEMA,
        'high_level_element': HIGH_LEVEL_ELEMENT_SCHEMA,
        'decomposed_text': DECOMPOSED_TEXT_SCHEMA,
    }
    
    return schemas.get(schema_name, '')


# Schema instruction templates
# Note: Braces are doubled {{}} to escape them from Python's .format() method
TEXT_DECOMPOSITION_SCHEMA = """

OUTPUT FORMAT:
You MUST respond with valid JSON matching this exact structure:
{{
  "Output": [
    {{
      "semantic_unit": "string - paraphrased summary of the semantic unit",
      "entities": ["ENTITY1", "ENTITY2", "..." - list of UPPERCASE entity names],
      "relationships": ["ENTITY_A, relation description, ENTITY_B" - list of 3-part relationship strings]
    }}
  ]
}}

CRITICAL: Respond with ONLY the JSON object above, no markdown code blocks (no ```json or ```), no explanations, no additional text. Just pure JSON.
"""

RELATIONSHIP_RECONSTRUCTION_SCHEMA = """

OUTPUT FORMAT:
Respond with valid JSON in this exact structure:
{{
  "source": "ENTITY_A",
  "relationship": "RELATION_TYPE",
  "target": "ENTITY_B"
}}

CRITICAL: Output ONLY the JSON object, no markdown formatting (no ```json or ```), no explanations.
"""

HIGH_LEVEL_ELEMENT_SCHEMA = """

OUTPUT FORMAT:
Respond with valid JSON in this exact structure:
{{
  "high_level_elements": [
    {{
      "title": "string - concise title",
      "description": "string - detailed description"
    }}
  ]
}}

CRITICAL: Output ONLY the JSON object, no markdown formatting (no ```json or ```), no explanations.
"""

DECOMPOSED_TEXT_SCHEMA = """

OUTPUT FORMAT:
Respond with valid JSON in this exact structure:
{{
  "elements": ["element1", "element2", "..."]
}}

CRITICAL: Output ONLY the JSON object, no markdown formatting (no ```json or ```), no explanations.
"""

