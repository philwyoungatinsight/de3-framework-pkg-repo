# Goal
- Document that this is used by the /watchdog skill (CronJob)

# Notes
From Claude:
```
  build-watchdog/check — the cron script. It runs one-shot, appends a single status line to ~/.build-watchdog.log, and exits. The log is currently active (last entry 2 minutes ago). This is what the cron job calls. The session-guard logic prevents two Claude      
  sessions from both writing to it simultaneously.                                                                                                                                                                                                                      
                                                                                                                                                                                                                                                                        
  build-watchdog/run — a separate interactive monitoring loop. It's meant to be used with Claude's Monitor tool during a build session: polls every 30 seconds, prints live status to stdout, runs until killed.                                                        
                                                                                                                                                                                                                                                                        
  The cron job runs check (not run). Looking at the log, something is calling check roughly every 2 minutes — but crontab -l returned nothing. The scheduling is likely done via Claude's CronCreate tool (stored in ~/.claude/tasks/) from a previous session. The log 
  was last written at 00:34, suggesting the cron is still active even though no build is running.
```                                                