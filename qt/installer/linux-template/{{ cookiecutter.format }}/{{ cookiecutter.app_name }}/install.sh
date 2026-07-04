#!/bin/bash

set -e

if [ "$(dirname "$(realpath "$0")")" != "$(realpath "$PWD")" ]; then
  echo "Please run from the folder install.sh is in."
  exit 1
fi

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

# Run a command with root privileges: directly when already root, otherwise
# through sudo when it is available.
_as_root() {
  if [ "$(id -u)" = "0" ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    return 1
  fi
}

# Ask a yes/no question on the controlling terminal. Works even when stdin is
# not the terminal (e.g. the script was piped). $1 = prompt, $2 = default
# answer used when there is no terminal or the user just presses Enter.
_ask_yes_no() {
  local prompt="$1" default="$2" reply=""
  # Only prompt when /dev/tty can actually be opened (a controlling terminal
  # exists); otherwise fall back to the default answer silently.
  if { true < /dev/tty; } 2>/dev/null; then
    printf "%s " "$prompt" > /dev/tty 2>/dev/null || true
    read -r reply < /dev/tty 2>/dev/null || reply=""
  fi
  reply="${reply:-$default}"
  case "$reply" in
    [Yy]*) return 0 ;;
    *)     return 1 ;;
  esac
}

_install_deps() {
  if [ ! -f /etc/os-release ]; then
    echo "Warning: /etc/os-release not found; skipping dependency installation."
    return
  fi

  # shellcheck disable=SC1091
  . /etc/os-release

  DEBIAN_DEPS=(
    libdbus-1-3 libfontconfig1 libfreetype6 libgl1 libnss3
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0
    libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 libxcb-xkb1
    libxcomposite1 libxcursor1 libxi6 libxkbcommon0 libxkbcommon-x11-0
    libxrandr2 libxrender1 libxtst6
  )

  _apt() {
    # libglib2.0-0 was renamed to libglib2.0-0t64 in Ubuntu 24.04+
    local glib_pkg=libglib2.0-0
    apt-cache show libglib2.0-0t64 >/dev/null 2>&1 && glib_pkg=libglib2.0-0t64
    _as_root apt-get install -y "${DEBIAN_DEPS[@]}" "$glib_pkg"
  }

  case "${ID:-}" in
    debian|ubuntu|linuxmint|pop)      _apt    ;;
    *)
      case "${ID_LIKE:-}" in
        *debian*|*ubuntu*) _apt    ;;
        *)
          echo "Warning: unknown distribution '${ID:-}'; skipping dependency installation."
          echo "Please run Anki with QT_DEBUG_PLUGINS=1 to show missing Qt dependencies."
          ;;
      esac
      ;;
  esac
}

_install_deps || echo "Warning: dependency installation failed; continuing anyway."

# ---------------------------------------------------------------------------
# choose install location
# ---------------------------------------------------------------------------
#
# When run as root we install system-wide to /usr/local; otherwise we do a
# per-user install under ~/.local so no sudo is required. Set PREFIX to
# override either default.

if [ "$PREFIX" = "" ]; then
  if [ "$(id -u)" = "0" ]; then
    PREFIX=/usr/local
  else
    PREFIX="$HOME/.local"
  fi
fi
PREFIX=$(realpath -m "$PREFIX")

# Transparently escalate the file operations with sudo when the destination is
# a system location the current user cannot write to.
_needs_root=0
if [ "$(id -u)" != "0" ] && [ ! -w "$PREFIX" ] && [ ! -w "$(dirname "$PREFIX")" ]; then
  _needs_root=1
fi
_run() {
  if [ "$_needs_root" = "1" ]; then _as_root "$@"; else "$@"; fi
}

echo "Installing Anki to $PREFIX ..."

if [ -f "$PREFIX"/share/anki/uninstall.sh ]; then
  _run bash "$PREFIX"/share/anki/uninstall.sh
fi
_run rm -rf "$PREFIX"/share/anki "$PREFIX"/bin/anki
_run mkdir -p "$PREFIX"/share/anki
_run cp -av --no-preserve=owner,context -- app app_packages python anki anki.1 anki.desktop anki.png anki.xml anki.xpm uninstall.sh README.md "$PREFIX"/share/anki/
_run mkdir -p "$PREFIX"/bin
_run ln -sf "$PREFIX"/share/anki/anki "$PREFIX"/bin/anki

# Install the icon and man page (harmless, and the shortcut points at the icon).
_run mkdir -p "$PREFIX"/share/pixmaps "$PREFIX"/share/man/man1
_run cp -f "$PREFIX"/share/anki/anki.png "$PREFIX"/share/pixmaps/anki.png
_run cp -f "$PREFIX"/share/anki/anki.xpm "$PREFIX"/share/pixmaps/anki.xpm
_run cp -f "$PREFIX"/share/anki/anki.1  "$PREFIX"/share/man/man1/anki.1

# ---------------------------------------------------------------------------
# optional desktop shortcut
# ---------------------------------------------------------------------------

_install_launcher() {
  # Build a .desktop entry with absolute Exec/Icon paths so it launches
  # regardless of whether $PREFIX/bin is on PATH or the icon is in a theme.
  local tmp; tmp="$(mktemp)"
  sed -e "s|^Exec=.*|Exec=$PREFIX/bin/anki %f|" \
      -e "s|^TryExec=.*|TryExec=$PREFIX/bin/anki|" \
      -e "s|^Icon=.*|Icon=$PREFIX/share/pixmaps/anki.png|" \
      "$PREFIX"/share/anki/anki.desktop > "$tmp"

  # System-wide app-menu entry (matches a normal package install).
  if [ -f "$PREFIX"/share/applications ]; then _run rm -f "$PREFIX"/share/applications; fi
  _run mkdir -p "$PREFIX"/share/applications
  _run cp -f "$tmp" "$PREFIX"/share/applications/anki.desktop

  # Per-user entry so it shows up in the (WSLg) Start Menu / app launcher for
  # the invoking user immediately, without a PATH or session refresh.
  local user_apps="$HOME/.local/share/applications"
  mkdir -p "$user_apps"
  cp -f "$tmp" "$user_apps/anki.desktop"
  chmod +x "$user_apps/anki.desktop"
  command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$user_apps" >/dev/null 2>&1 || true

  # A clickable icon on the Desktop, if the user has one.
  if [ -d "$HOME/Desktop" ]; then
    cp -f "$tmp" "$HOME/Desktop/anki.desktop"
    chmod +x "$HOME/Desktop/anki.desktop"
    command -v gio >/dev/null 2>&1 && \
      gio set "$HOME/Desktop/anki.desktop" metadata::trusted true >/dev/null 2>&1 || true
  fi
  rm -f "$tmp"

  # File-type associations for .colpkg/.apkg/.ankiaddon.
  if command -v xdg-mime >/dev/null 2>&1; then
    xdg-mime install anki.xml --novendor >/dev/null 2>&1 || true
    xdg-mime default anki.desktop application/x-colpkg    >/dev/null 2>&1 || true
    xdg-mime default anki.desktop application/x-apkg      >/dev/null 2>&1 || true
    xdg-mime default anki.desktop application/x-ankiaddon >/dev/null 2>&1 || true
  fi
}

if _ask_yes_no "Add a desktop shortcut for Anki (Start Menu / Applications + Desktop)? [Y/n]" "${ANKI_DESKTOP_SHORTCUT:-y}"; then
  _install_launcher
  echo "Desktop shortcut added."
else
  echo "Skipped desktop shortcut."
fi

rm -f install.sh

# ---------------------------------------------------------------------------
# done
# ---------------------------------------------------------------------------

case ":$PATH:" in
  *":$PREFIX/bin:"*) _hint="Type 'anki' to run." ;;
  *)                 _hint="Launch it with: $PREFIX/bin/anki   (or add $PREFIX/bin to your PATH)" ;;
esac
echo
echo "Install complete. $_hint"
