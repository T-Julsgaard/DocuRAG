---
summary: "Troubleshooting steps when files won't sync between the desktop app and the cloud."
category: "Troubleshooting"
tags: "sync, not syncing, stuck, upload, pending, sync error, offline"
url: "https://help.nimbus.example/troubleshooting/sync"
---

# Files not syncing

Work through these in order; most sync problems are fixed by step 3.

1. **Check the connection.** The app must show **Connected** (green) in the tray
   icon. If it shows offline, confirm internet access.
2. **Check storage.** A full account pauses uploads. Free space or upgrade — see
   [Plans and pricing](../Billing/plans-and-pricing.md).
3. **Pause and resume sync.** Tray icon → **Pause syncing**, wait 10 seconds,
   then **Resume**. This clears most stuck transfers.
4. **Check the file name.** These characters block syncing on some systems:
   `< > : " / \ | ? *`. Rename the file to remove them.
5. **Restart the app.** Fully quit Nimbus and reopen it.
6. **Re-link the account.** Settings → Account → **Unlink this device**, then
   sign in again. No files are lost — they re-download from the cloud.

## Still stuck?

Collect the sync log from **Settings → Advanced → Export logs** and escalate to
second-line support with the file name and account email.

## Common error codes

| Code | Meaning | Fix |
|---|---|---|
| **E-101** | No connection | Check network, then resume sync |
| **E-204** | Storage full | Free space or upgrade plan |
| **E-307** | Invalid file name | Rename to remove blocked characters |
| **E-500** | Server error | Wait 15 minutes and retry; escalate if it persists |
