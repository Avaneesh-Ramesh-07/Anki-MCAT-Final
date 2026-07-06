# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

"""Small, dependency-free MCAT constants shared across the Qt layer.

Deliberately imports nothing from ``aqt`` (no Qt/UI modules), so it's safe to
import from anywhere — including the home-page unit tests — without pulling in
heavy UI modules like the deck browser."""

# Hard ceiling on new cards introduced per day for a deck studied via the garden
# ("Plant seeds"), regardless of the deck's preset — so a topic never dumps its
# whole backlog at once. Also used by the Home page's "flashcards to study today"
# count so the count matches this cap on open (single source of truth).
MCAT_NEW_PER_DAY_CAP = 20
