DATA MODEL:

The data model is found in folders like notes, card, etc. It is like a class that holds attributes that help define what different components of the app is. It also has config modules like deckconfig that specifies scheduling presets (including FSRS parameters) and config that includes settings like scheduler version, rollover hour, etc.

SCHEDULING & STUDY

The scheduler folder is the state machine that determines when to review various cards. The mcat folder is everything specific for mcat studying.
mastery.rs implements the mastery query feature, which quickly returns a statistic of how many cards are mastered and the average retrievability (FSRS's predicted recall probability, augmented with time-based comfort metric). The mastery query is aggregated per AAMC topic (how familiar is the user with this specific topic). It also returns a confidence range, as opposed to simply a number. It also gives up below a minimum number of reviews (give-up-rule).

RENDERING & CONTENT
card_rendering/ renders the card's question/answer HTML from the care template and fields. In essence, preps for Qt and Svelte to fully display the correct UI

STORAGE, SYNC, & LIFECYCLE
storage/ is the SQL layer.
collection/ is the entry to a collection object. The Collection is the whole Anki library, which is the whole database of everything you study.
sync/ each devices sync client syncs its local collection to a sync server (AnkiWeb or self-hosted anki-sync-server). Phone and Desktop sync consistency is a consequence of both talking to the same server.
undo/ is the undo/redo stack that records ecah operation's changes so they can be reversed.
import_export/ handles importing new Anki decks.
media/ handles images/audio attached to cards
search? handles searching cards/notes within your own collection

Terminology:

1. "just" - "make" from Makefile
2. "cargo" - Rust's package manager (similar to pip for Python)
3. "Qt" - GUI framework
   Even though we have a Svelte frontend, it compiles to HTML/CSS/JS and needs a browser to run. By itself, it can't open a window on your OS, read files, or do any OS operations. **Svelte needs QT**, which hosts and surrounds the web UI. On desktop most of the UI is Qt itself, but Svelte onlyu powers embedded pages. On Android, there is no Qt.
4. "Ninja" - low-level build system. Rust decides the plan for how to compile its code (writes a build.ninja manifest) and Ninja just runs the build.ninja. build the frontend, protobuf codegen, Python packaging
5. protobuf codegen
   Protobuf (Protocol Buffers): a file that defines different data structures/types used in the program
