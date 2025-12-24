# Voice Logs - Supabase Setup

This module stores daily check-ins and 1:1 logs in Supabase when configured.

## Environment
Either set env vars:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=service_role_or_server_key
```

Or Streamlit secrets:
```
[supabase]
url = "https://xxx.supabase.co"
key = "service_role_or_server_key"
```

## Table Schema
Run this once in Supabase SQL editor:
```sql
create table if not exists voice_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  mode text,
  session_id text,
  user_text text,
  assistant_text text,
  transcript text,
  created_at timestamptz default now()
);

create index if not exists voice_logs_user_time_idx
  on voice_logs (user_id, created_at desc);

create table if not exists voice_checkins (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  mode text,
  session_id text,
  summary_date date,
  summary_json jsonb,
  created_at timestamptz default now()
);

create index if not exists voice_checkins_user_time_idx
  on voice_checkins (user_id, created_at desc);
```

## RLS
If you enable RLS, add a policy for your server key or disable RLS for this table.
This app uses a server-side key and stores `user_id` as a hash of the Claude API key.

## Notes
- Raw audio is not stored.
- If Supabase is unavailable, logs fall back to local JSONL files in `chat_history/voice/`.
