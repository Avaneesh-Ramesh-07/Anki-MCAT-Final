# Syncing flashcard progress with the phone (AnkiWeb)

Desktop and phone share progress by both logging into the **same free AnkiWeb
account**. This uses Anki's standard collection sync — no self-hosted server and
no code changes in this fork. Once connected, everything relevant flows both
ways automatically:

- cards, decks, and their due dates / scheduling queues
- the full review history (revlog)
- **FSRS memory state (DSR)** — the MCAT readiness / Mastery Query scores are
  _computed from_ this synced state, so the readiness dashboard matches on both
  devices without syncing anything extra.

## One-time setup

1. **Create an AnkiWeb account** (free) at <https://ankiweb.net> if you don't
   have one.
2. **Desktop:** click **Sync** in the top toolbar (or press **Y**). The first
   time, it prompts for your AnkiWeb email/password, then uploads your
   collection. Auto-sync is already on by default, so after this first login the
   desktop syncs automatically on startup and shutdown.
3. **Phone (AnkiDroid fork):** install the app, open it, and log into the
   **same** AnkiWeb account (menu → Settings → AnkiWeb account, then Sync).
   Enable "Automatic synchronization" in AnkiDroid's sync settings so progress
   flows without manual syncs.

After that, study on either device and press sync (or let auto-sync run) — the
other device picks up the progress on its next sync.

## First-sync direction (read once)

The first time two devices with _different_ data meet on one AnkiWeb account,
Anki can't merge divergent full collections, so it asks you to choose **Upload**
(this device wins) or **Download** (server wins). To avoid losing anything:

- Do the **desktop's first sync into a fresh/empty AnkiWeb account first**
  (Upload). This fork seeds a bundled sample deck on first launch, so the
  desktop has content immediately.
- Then on the phone, choose **Download** for its first sync so it pulls the
  desktop's collection.

Once both sides share a common baseline, subsequent syncs merge normally
(review-by-review), and there are no more direction prompts unless a device goes
badly out of date.

## Notes

- **FSRS:** this fork force-enables FSRS on the desktop, and that setting is part
  of the synced deck config — so the phone inherits FSRS automatically after the
  first sync, keeping the memory model identical on both devices.
- **AnkiWeb vs. self-hosted:** if you later want to run your own server instead
  of AnkiWeb, the same client works — point both devices at a self-hosted
  `anki-sync-server` (see `docs/syncserver/`) via a custom sync URL in
  Preferences → Syncing. No code change needed either way.
