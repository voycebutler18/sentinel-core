import os
os.environ["COQUI_TOS_AGREED"] = "1"

from pathlib import Path
from TTS.api import TTS
import uuid

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

VOICE_DIR = BASE_DIR / "voice"
VOICE_DIR.mkdir(exist_ok=True)

SPEAKER_WAVS = [
    str(VOICE_DIR / "voice1.wav"),
    str(VOICE_DIR / "voice2.wav"),
    str(VOICE_DIR / "voice3.wav"),
]

SPEAKER_WAVS = [v for v in SPEAKER_WAVS if os.path.exists(v)]

if not SPEAKER_WAVS:
    raise FileNotFoundError(
        "No voice files found. Put voice1.wav, voice2.wav, or voice3.wav inside /voice/"
    )

_tts = None

def get_tts():
    global _tts
    if _tts is None:
        _tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    return _tts

def clone_to_file(
    text: str,
    filename: str = "output.wav",
    language: str = "en",
) -> str:
    if not text or not text.strip():
        raise ValueError("Text is required")

    output_path = STATIC_DIR / filename
    tts = get_tts()

    tts.tts_to_file(
        text=text,
        speaker_wav=SPEAKER_WAVS,
        language=language,
        file_path=str(output_path)
    )

    return f"/static/{filename}"

def clone_to_unique_file(
    text: str,
    language: str = "en",
) -> str:
    unique_name = f"{uuid.uuid4().hex}.wav"
    return clone_to_file(
        text=text,
        filename=unique_name,
        language=language,
    )
