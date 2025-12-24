# Voice Vendor Research (STT/TTS) - M0 Shortlist

Date: 2025-12-24

## Goals
- Select 3-4 STT/TTS stacks for Korean high-fidelity voice interaction.
- Define a benchmark rubric (quality, latency, control, cost).
- Produce a decision memo for the M1 build.

## Shortlist (M0)
1) Naver Cloud (CLOVA Speech Recognition + CLOVA Voice) [Primary]
   - STT: https://api.ncloud-docs.com/docs/ai-naver-clovaspeechrecognition-index
   - TTS: https://api.ncloud-docs.com/docs/ai-naver-clovavoice-index
   - Notes: Korean-first quality, confirm streaming/voice styles.

2) Azure Speech (STT + Neural TTS)
   - STT: https://learn.microsoft.com/azure/ai-services/speech-service/speech-to-text
   - TTS: https://learn.microsoft.com/azure/ai-services/speech-service/text-to-speech
   - Notes: strong streaming support and SSML; enterprise reliability.

3) Google Cloud (STT + Text-to-Speech)
   - STT: https://cloud.google.com/speech-to-text/docs
   - TTS: https://cloud.google.com/text-to-speech/docs
   - Notes: stable infra; multiple voice families and SSML controls.

4) Best-of-breed: Deepgram STT + ElevenLabs TTS
   - STT: https://developers.deepgram.com/docs/
   - TTS: https://docs.elevenlabs.io/
   - Notes: high naturalness for TTS; verify Korean voice quality and licensing.

Optional baseline (local):
- Whisper / faster-whisper for STT quality and offline fallback.
  - https://github.com/openai/whisper
  - https://github.com/SYSTRAN/faster-whisper
- MMS TTS (Korean) for open-source TTS.
  - https://huggingface.co/facebook/mms-tts-kss

## Evaluation Rubric
### Speech Quality (TTS)
- Naturalness (MOS, 1-5)
- Prosody and emotion control (instruction following)
- Speaker consistency across turns

### Intelligibility (STT)
- WER on a Korean test set (read + conversational)
- Punctuation and normalization quality

### Latency
- First token latency (STT partials)
- End-to-end response latency (STT -> LLM -> TTS)

### Integration
- Streaming support (STT and TTS)
- SDK maturity and language support (Python + REST)
- Pricing clarity and quota limits

## Benchmark Protocol (Draft)
- Prepare 30 Korean utterances (short, medium, long) across:
  - neutral, excited, empathetic, formal
  - daily check-in prompts
  - numeric content (dates, money)
- Record in consistent mic environment (16 kHz or 48 kHz).
- Run STT on each vendor and compute WER.
- Run TTS on fixed prompts with style tags and rate control.
- Collect MOS ratings from 3-5 internal reviewers.
- Log end-to-end latency in the same network.

## Decision Gate (M0 -> M1)
- Select one primary stack and one fallback.
- Confirm TTS control features (style/SSML) for emotion cues.
- Document compliance and data retention posture.

## Risks and Notes
- Vendor-specific SSML features may not map 1:1.
- Korean emotional prosody quality varies by vendor.
- Streaming TTS and barge-in support can be limited.
