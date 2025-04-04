import time
import datetime

import requests
import json
from typing import Optional, Dict, Any
from utils.logging_config import LoggingConfig

log = LoggingConfig.get_logger('_AI_', _default=4)

# Server configuration
LLAMA_SERVER_URL = "http://192.168.7.13:9070/completion"
REQUEST_TIMEOUT = 30  # seconds

# Prompt templates
STYLE_ANALYSIS_TEMPLATE = """
You are a professional Italian editor with expertise in literary fiction. Analyze this text:

### Text:
{text}

### Analysis Guidelines:
1. Language Quality:
   - Grammar/syntax errors
   - Awkward phrasing
   - Register consistency

2. Narrative Flow:
   - Pacing issues
   - Paragraph structure
   - Transition smoothness

3. Style Evaluation:
   - Word repetition
   - Sentence rhythm
   - Show vs. tell balance

4. Specific Suggestions:
   - Provide concrete examples
   - Suggest improvements
   - Note positive aspects

Format your response with clear section headings.
"""

SUMMARY_TEMPLATE = """
Create a concise summary of this literary text in Italian. Include:

1. Key events (3-5 bullet points)
2. Character development aspects
3. Important details
4. Style characteristics

Return as JSON with these keys:
"events", "character_dev", "details", "style"

### Text:
{text}
"""

TRANSLATION_TEMPLATE = """
Translate this Italian literary text to English while:

1. Preserving the original style and voice
2. Maintaining natural dialogue flow
3. Adapting idioms appropriately
4. Keeping cultural references intact

Return only the translation without additional commentary.

### Italian Text:
{text}

### English Translation:
"""


def _make_llama_request(prompt: str, mode: str = "quick") -> Optional[str]:
    """Generic function to handle llama.cpp requests"""
    params = {
        "thorough": {
            "temperature": 0.7,
            "top_k": 50,
            "top_p": 0.9,
            "n_predict": 512
        },
        "quick": {
            "temperature": 0.7,
            "top_k": 30,
            "top_p": 0.8,
            "n_predict": 256
        }
    }

    payload = {
        "prompt": prompt,
        **params[mode]
    }

    try:
        log.debug(f"Sending request to llama.cpp: {payload['prompt'][:100]}...")
        start_time = time.time()
        response = requests.post(LLAMA_SERVER_URL, json=payload)
        elapsed = time.time()-start_time
        log.debug(f'request took {datetime.timedelta(seconds=elapsed)} ({elapsed} seconds)')
        response.raise_for_status()
        return response.json().get("content", "").strip()
    except requests.exceptions.RequestException as e:
        log.error(f"Request failed: {str(e)}")
        return None


def analyze_style(scene_text: str, mode: str = "quick") -> Optional[str]:
    """Get detailed style analysis of the text"""
    prompt = STYLE_ANALYSIS_TEMPLATE.format(text=scene_text)
    return _make_llama_request(prompt, mode)


def generate_summary(text: str) -> Optional[Dict[str, Any]]:
    """Generate structured summary of the text"""
    prompt = SUMMARY_TEMPLATE.format(text=text)
    response = _make_llama_request(prompt, {"temperature": 0.3})

    if response:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            log.error("Failed to parse summary JSON")
    return None


def translate_text(text: str) -> Optional[str]:
    """Translate Italian text to English preserving style"""
    prompt = TRANSLATION_TEMPLATE.format(text=text)
    return _make_llama_request(prompt, {
        "temperature": 0.5,
        "n_predict": 1024
    })


def analyze_scene(scene_text: str) -> Dict[str, Any]:
    """Comprehensive scene analysis pipeline"""
    return {
        "style_analysis": analyze_style(scene_text),
        "summary": generate_summary(scene_text),
        "translation": translate_text(scene_text)
    }

