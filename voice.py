import os
from pathlib import Path
from TTS.api import TTS

# Where generated audio will be written
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

# Where cached cloned voices will be stored
VOICE_CACHE_DIR = Path("voice_cache")
VOICE_CACHE_DIR.mkdir(exist_ok=True)

# Your reference audio file
DEFAULT_SPEAKER_WAV = "voice.wav"

# Load XTTS v2 once when the app starts
# Coqui supports XTTS v2 voice cloning with speaker_wav
tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")

def clone_to_file(
    text: str,
    speaker_wav: str = DEFAULT_SPEAKER_WAV,
    output_filename: str = "output.wav",
    language: str = "en",
    speaker_id: str = "peter"
) -> str:
    """
    Generate speech from text using a cloned voice and save it to a file.

    Returns a web-friendly relative path like: /static/output.wav
    """
    if not text or not text.strip():
        raise ValueError("Text is required")

    if not os.path.exists(speaker_wav):
        raise FileNotFoundError(f"Speaker reference file not found: {speaker_wav}")

    output_path = STATIC_DIR / output_filename

    # Coqui docs support speaker_wav plus optional speaker/voice_dir caching
    tts.tts_to_file(
        text=text,
        speaker_wav=speaker_wav,
        speaker=speaker_id,
        voice_dir=str(VOICE_CACHE_DIR),
        language=language,
        file_path=str(output_path)
    )

    return f"/static/{output_filename}"


def clone_to_unique_file(
    text: str,
    speaker_wav: str = DEFAULT_SPEAKER_WAV,
    language: str = "en",
    speaker_id: str = "peter"
) -> str:
    """
    Generate speech to a unique filename so responses do not overwrite each other.
    """
    import uuid

    filename = f"{uuid.uuid4().hex}.wav"
    return clone_to_file(
        text=text,
        speaker_wav=speaker_wav,
        output_filename=filename,
        language=language,
        speaker_id=speaker_id
    )
