# Voice Agent Development Plan (Streamlit STT/TTS + Daily Check-in)

## Executive Summary
Build a high-fidelity Korean voice agent in Streamlit with full duplex interaction
(speech input + speech output), daily check-in and 1:1 flows, and HCI-aligned
social presence. This plan prioritizes audio quality, low latency, and
transparent progress tracking.

## Scope
- In scope: STT + TTS integration, conversational loop, daily check-in/1:1,
  memory/logging, evaluation, and HCI-aligned behaviors.
- Out of scope (v1): full mobile app, custom TTS model training, real-time
  multi-party calls.

## Key Requirements
### Functional
- Speech input (STT) and speech output (TTS) in Korean.
- Daily check-in and 1:1 flows with structured logging.
- Emotion-aware responses with explicit explanation of yesterday's learnings.
- Streamlit UI with push-to-talk or always-on toggle.

### Non-Functional
- Audio quality is primary: MOS target >= 4.2 (subjective).
- Latency: end-to-end response <= 2.5s for short utterances.
- Reliability: graceful fallback to text-only mode.
- Privacy: logs stored locally or in approved storage, no raw audio retention by default.

## Architecture (v1)
- Client (Streamlit)
  - Audio capture: streamlit-webrtc or custom component (Web Speech API).
  - Playback: streamed or chunked audio.
- Backend
  - STT: cloud provider with streaming support (Azure, Google, Naver, etc.).
  - LLM: existing agent stack.
  - Memory: short-term + long-term summaries, emotion state.
  - TTS: high-quality neural TTS (Azure/Google/ElevenLabs/Naver).
- Storage
  - JSON logs for sessions, daily check-ins, emotion summaries, and feedback.

## Research Baseline (for review)
- 2025 EMNLP survey: "Towards Controllable Speech Synthesis in the Era of LLMs"
  - Control tasks: prosody, timbre, emotion, style.
  - Control strategies: tags, reference prompts, natural language descriptions,
    instruction-guided control.
  - Quality tradeoffs: continuous vs discrete speech representations.
- HCI: relational agents, social presence, and personal informatics.

## Evaluation Plan
- Speech quality: MOS, AB/ABX for preference.
- Intelligibility: WER (STT back-check on TTS output).
- Expressiveness: instruction-following score and emotion consistency.
- HCI: Godspeed (anthropomorphism/likeability), social presence survey items.

## Implementation Phases
### M0: Research and Benchmarks
- Compare 3-4 STT/TTS vendors on Korean quality, latency, and cost.
- Produce a short report with audio samples and ratings.

### M1: Audio Capture + STT
- Implement audio capture in Streamlit.
- Integrate streaming STT with transcript display and latency metrics.

### M2: TTS Pipeline
- Integrate TTS with selectable voices and emotion/style controls.
- Add audio playback and caching for recent responses.

### M3: Conversational Loop
- Wire STT -> LLM -> TTS.
- Add turn-taking controls and barge-in behavior (optional).

### M4: Daily Check-in + 1:1
- Create a daily flow: yesterday log -> learnings -> emotion state -> today plan.
- Add weekly summary report and insights.

### M5: Memory and Emotion Modeling
- Create structured memory: events, reflections, emotion, and action items.
- Add emotion inference + explicit explanation in responses.

### M6: Observability and Hardening
- Add logging, error handling, and fallback to text-only mode.
- Define testing scripts and a smoke test path.

## Codex Progress Tracking
Update this section as work proceeds. Use [ ] for todo, [~] for in progress,
[x] for done. Add a dated note in the log.

- [~] M0 in progress: vendor comparison and decision memo
- [~] M1 in progress: audio capture + STT wiring (non-streaming)
- [ ] M2 complete: TTS playback with voice selection
- [ ] M3 complete: end-to-end conversation loop
- [ ] M4 complete: daily check-in/1:1 flow
- [ ] M5 complete: memory + emotion modeling
- [ ] M6 complete: observability + fallback + smoke test

### Progress Log
- 2025-12-24: Plan created.
- 2025-12-24: M0 started, vendor shortlist drafted in VOICE_VENDOR_RESEARCH.md.
- 2025-12-24: M1 started, Streamlit voice page + CLOVA STT/TTS wiring added.
- 2025-12-24: Supabase voice log integration added (voice_logs table).
- 2025-12-24: Check-in now reads Supabase logs for "어제 기록" context.
- 2025-12-24: Local STT/TTS (faster-whisper + Piper) option added for CPU deployments.
- 2025-12-24: Added MMS TTS + check-in JSON summaries stored in Supabase.
- 2025-12-24: Check-in review page added for Supabase summaries + raw logs.

## Decision Rationale (Summary)
These are concise, user-facing reasons for design choices.
- Audio quality prioritized over model customization in v1.
- Instruction-guided control is preferred to align with natural speech requests.
- Separate emotion state from content to avoid drift and maintain consistency.

## Risks and Mitigations
- Vendor lock-in: add abstraction layer for STT/TTS providers.
- Latency spikes: use streaming STT and chunked TTS playback.
- Privacy concerns: opt-out audio retention, local-first logs.

## Open Questions
- Preferred STT/TTS vendor for Korean quality (Azure vs Google vs Naver vs others)?
- Required emotion taxonomy (basic vs granular)?
- Daily check-in cadence and retention period?
