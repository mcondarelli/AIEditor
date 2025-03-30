import requests

from logging_config import LoggingConfig

log = LoggingConfig.get_logger('AI', _default=4)

# Llama.cpp server details
LLAMA_SERVER_URL = "http://192.168.7.13:9070/completion"

# AI Prompt for analysis
PROMPT_TEMPLATE = """
You are a professional Italian editor. Analyze the following Italian text for stylistic weaknesses, repetition, inconsistencies, and potential errors. Provide constructive feedback in clear and concise Italian.  

### Testo:  
{scene_text}  

### Analisi:  
- Debolezze stilistiche:  
- Ripetizioni:  
- Incongruenze:  
- Errori potenziali:  
"""
PROMPT_TEMPLATE0 = """
Analyze the following Italian text for stylistic weaknesses, repetition, inconsistencies, and potential errors.  
Provide constructive feedback as if you were a professional editor, using clear and concise explanations.

### Step 1: Translation  
First, translate the text into English while preserving style and nuances.  

### Step 2: Summary  
Summarize the translated text in English, focusing on key events and themes.  

### Step 3: Analysis  
Critique the text based on literary standards, considering style, flow, repetition, and inconsistencies.  

### Italian Text:  
{scene_text}

### English Translation:
(Provide the English translation here)

### Summary:
(Provide a brief summary of the scene here)

### Analysis:
(Provide the literary critique here)
"""


# Function to perform a check on the scene
def ai_ask_commentary(scene_text):
    scene_text = scene_text.replace('@q{', '"').replace('}q@', '"')
    scene_text = scene_text.replace('@Q[name]{', '<<').replace('}Q@', '>>')
    scene_text = scene_text.replace('@b{', '').replace('}b@', '')
    scene_text = scene_text.replace('@e{', '').replace('}e@', '')
    prompt = PROMPT_TEMPLATE.format(scene_text=scene_text)
    payload = {
        "prompt": prompt,
        "temperature": 0.7,
        "top_k": 50,
        "top_p": 0.9,
        "n_predict": 512  # Adjust output length as needed
    }

    try:
        response = requests.post(LLAMA_SERVER_URL, json=payload)
        response.raise_for_status()
        comment = response.json().get("content", "").strip()
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to llama-server: {e}")
        comment = "Errore: impossibile analizzare il testo."
    return comment

