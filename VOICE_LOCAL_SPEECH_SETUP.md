# Local Speech Setup (CPU)

This setup enables open-source STT/TTS for Streamlit deployments.

## Dependencies
1) ffmpeg
   - macOS: `brew install ffmpeg`
   - Ubuntu: `sudo apt-get install ffmpeg`

2) Python packages
```
pip install faster-whisper
pip install piper-tts
pip install transformers soundfile
# torch install depends on your OS (CPU build recommended)
```

## Models
### STT (faster-whisper)
- Choose a model size: `tiny`, `base`, `small`, `medium`
- Set it in the UI under "Whisper Model"

### TTS (MMS, open-source)
- Default option for Korean: `facebook/mms-tts-kss`
- The app will download on first use if `transformers` and `torch` are installed.
- Optional pre-download:
```
python scripts/download_voice_models.py --mms
```

### TTS (Piper, optional)
- Piper does not ship an official Korean voice in the default bundle.
- Use Piper only if you have a Korean .onnx model from a trusted source.
- Set paths in the UI:
  - Piper Model Path
  - Piper Config Path (optional)
  - Piper Binary (default: `piper`)
- Optional download (if you have URLs):
```
python scripts/download_voice_models.py --piper-model-url <URL> --piper-config-url <URL>
```

## Notes
- This mode is CPU-friendly but can be slower than cloud APIs.
- If MMS/Piper is missing, the app falls back to text-only output.
