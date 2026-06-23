import argparse
import os
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

VOICE2_ENDPOINT = os.getenv('MAI_VOICE_2_ENDPOINT', '')
VOICE2_KEY = os.getenv('MAI_VOICE_2_KEY', '')

OUT_DIR = Path('.')
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEMO_SSML = """<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xml:lang="en-US">
  <voice name="en-US-Ethan:MAI-Voice-2">Wait—what if the Numbers aren't 'magic'? What if they're a moral test with really bad marketing?</voice>
</speak>"""


def headers() -> dict:
    return {
        'Content-Type': 'application/ssml+xml',
        'X-Microsoft-OutputFormat': 'audio-24khz-160kbitrate-mono-mp3',
        'User-Agent': 'mai-voice-2-sample',
        'Ocp-Apim-Subscription-Key': VOICE2_KEY,
    }


def synthesize_to_file(ssml: str, out_file: str, timeout: int = 600) -> Path:
    url = f"{VOICE2_ENDPOINT.rstrip('/')}/cognitiveservices/v1"
    print('Generating text to speech with MAI2')
    # Use a 60-second per-chunk idle timeout: if the server stops sending data
    # for 60s (e.g. chunked stream never sends the final empty chunk), we treat
    # whatever has been received as the complete file.
    resp = requests.post(url, headers=headers(), data=ssml.encode('utf-8'), timeout=(30, 60), stream=True)
    if not resp.ok:
        print(f"Status: {resp.status_code}, Body: {resp.text!r}")
    resp.raise_for_status()
    print(f"Response headers: {dict(resp.headers)}")
    p = OUT_DIR / out_file
    bytes_written = 0
    with p.open('wb') as f:
        try:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bytes_written += len(chunk)
                    print(f"\rReceived {bytes_written:,} bytes", end='', flush=True)
        except requests.exceptions.ReadTimeout:
            print(f"\nStream idle for 60s after {bytes_written:,} bytes — treating as complete")
    print()
    return p


def main():
    parser = argparse.ArgumentParser(description="Synthesize speech via MAI Voice 2 API")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--ssml-file', type=Path, help='Path to an SSML XML file')
    group.add_argument('--ssml', type=str, help='Inline SSML string')
    parser.add_argument('--out', type=str, default='speech.mp3', help='Output filename (default: speech.mp3)')
    parser.add_argument('--timeout', type=int, default=600, help='Request timeout in seconds (default: 600)')
    args = parser.parse_args()

    if args.ssml_file:
        ssml = args.ssml_file.read_text(encoding='utf-8')
    elif args.ssml:
        ssml = args.ssml
    else:
        print("No SSML provided — using demo snippet.")
        ssml = DEMO_SSML

    result = synthesize_to_file(ssml, args.out, timeout=args.timeout)
    print(f"MAI-2 API call succeeded: {result}")


if __name__ == '__main__':
    main()
