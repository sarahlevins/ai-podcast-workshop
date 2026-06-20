import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

VOICE2_ENDPOINT = os.getenv(
    'MAI_VOICE_2_ENDPOINT', '')
VOICE2_KEY = os.getenv('MAI_VOICE_2_KEY', '')

OUT_DIR = Path('.')
OUT_DIR.mkdir(parents=True, exist_ok=True)

def headers() -> dict:
    h = {
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'audio-24khz-160kbitrate-mono-mp3',
        'User-Agent': 'mai-voice-2-sample',
        'Ocp-Apim-Subscription-Key': VOICE2_KEY
        }
    return h

def synthesize_to_file(ssml: str, out_file: str) -> Path:
    url = f"{VOICE2_ENDPOINT.rstrip('/')}/cognitiveservices/v1"
    resp = requests.post(url, headers=headers(), data=ssml.encode('utf-8'), timeout=180)
    if not resp.ok:
        print(f"Status: {resp.status_code}, Body: {resp.text!r}")
    resp.raise_for_status()
    p = OUT_DIR / out_file
    p.write_bytes(resp.content)
    return p


ssml = """
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-US-Ethan:MAI-Voice-2">Wait—what if the Numbers aren't 'magic'? What if they're a moral test with really bad marketing?</voice>
</speak>"""

synthesize_to_file(ssml, 'lost.mp3')