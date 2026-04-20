import os
from pathlib import Path
from TTS.api import TTS
import uuid

# ---------------- PATHS ---------------- #

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

VOICE_DIR = BASE_DIR / "voice"
VOICE_DIR.mkdir(exist_ok=True)

VOICE_CACHE_DIR = BASE_DIR / "voice_cache"
VOICE_CACHE_DIR.mkdir(exist_ok=True)

# ---------------- VOICE FILES ---------------- #

# Use up to 3 clean samples
SPEAKER_WAVS = [
    str(VOICE_DIR / "voice1.wav"),
    str(VOICE_DIR / "voice2.wav"),
    str(VOICE_DIR / "voice3.wav"),
]

# Filter out missing files automatically
SPEAKER_WAVS = [v for v in SPEAKER_WAVS if os.path.exists(v)]

if not SPEAKER_WAVS:
    raise FileNotFoundError(
        "No voice files found. Put voice1.wav, voice2.wav, or voice3.wav inside /voice/"
    )

# ---------------- LOAD MODEL ---------------- #

# XTTS v2 supports multi-speaker cloning
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

# ---------------- GENERATE AUDIO ---------------- #

def clone_to_file(
    text: str,
    filename: str = "output.wav",
    language: str = "en",
    speaker_id: str = "peter"
) -> str:
    """
    Generate speech and overwrite file.
    """
    if not text or not text.strip():
        raise ValueError("Text is required")

    output_path = STATIC_DIR / filename

    tts.tts_to_file(
        text=text,
        speaker_wav=SPEAKER_WAVS,
        speaker=speaker_id,
        voice_dir=str(VOICE_CACHE_DIR),
        language=language,
        file_path=str(output_path)
    )

    return f"/static/{filename}"


def clone_to_unique_file(
    text: str,
    language: str = "en",
    speaker_id: str = "peter"
) -> str:
    """
    Generate speech with unique filename so responses don’t overwrite each other.
    """
    unique_name = f"{uuid.uuid4().hex}.wav"
    return clone_to_file(
        text=text,
        filename=unique_name,
        language=language,
        speaker_id=speaker_id
    )
