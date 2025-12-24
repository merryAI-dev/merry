# Streamlit Deployment (Community Cloud)

## 1) GitHub Push
Ensure all changes are committed and pushed to:
`https://github.com/merryAI-dev/merry`

## 2) Streamlit App
1. Go to https://share.streamlit.io/
2. New app → select repo/branch
3. Main file: `app.py`

## 3) Secrets
In Streamlit Cloud → **App settings → Secrets**, add:
```toml
ANTHROPIC_API_KEY = "sk-..."

[supabase]
url = "https://xxx.supabase.co"
key = "service_role_or_server_key"
```

Optional (for CLOVA STT/TTS):
```toml
NAVER_CLOUD_API_KEY_ID = "..."
NAVER_CLOUD_API_KEY = "..."
```

## 4) OS Packages
`packages.txt` includes:
- `ffmpeg`
- `libsndfile1`

These are required for faster-whisper and soundfile.

## 5) Supabase Tables
Run the SQL in `VOICE_SUPABASE_SETUP.md`:
- `voice_logs`
- `voice_checkins`

## 6) Notes
- Open-source TTS uses `facebook/mms-tts-kss` (CPU).
- First run will download models; cold start can be slow.
- If you want cloud TTS, select CLOVA in the sidebar.
