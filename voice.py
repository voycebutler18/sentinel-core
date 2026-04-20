import os
from pathlib import Path
from TTS.api import TTS
import uuid

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

_tts = None

def get_tts():
    global _tts
    if _tts is None:
        _tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
    return _tts

def clone_to_file(
    text: str,
    filename: str = "output.wav",
) -> str:
    if not text or not text.strip():
        raise ValueError("Text is required")

    output_path = STATIC_DIR / filename
    tts = get_tts()

    tts.tts_to_file(
        text=text,
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
    )
