---
title: Polling Timeout Fix
date: 2026-06-15
status: approved
---

## Problem

Bot running on Raspberry Pi under systemd shows variable response delays (sometimes 10s, rarely 30s+). Root cause: `poll_timeout=30` means the HTTP socket waits up to 35s before detecting a silent TCP drop. Network instability on Pi causes these drops.

## Scope

Single-line change in `bot.py`. No architectural changes.

## `/restart` Command

Current implementation uses `os.execv(sys.executable, [sys.executable] + sys.argv[:1])`. This replaces the process image in-place, keeping the same PID. Systemd (Type=simple) tracks the main PID and sees the service as still running — correct behavior. No change needed.

## Polling Fix

**Change:** `poll_timeout = 5 if active else 30` → `poll_timeout = 5 if active else 10`

**Why 10s:** Long-polling still delivers messages instantly when connection is alive. The timeout only determines how quickly the bot recovers after a silent connection drop. Reducing from 30s to 10s cuts max delay from ~35s to ~15s with negligible increase in API calls.

## Success Criteria

- Max observed delay after fix: ~15s (previously up to ~35s)
- No change to normal message response time (still < 1s on stable connection)
