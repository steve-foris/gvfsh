# gvfsh - GVFS Google Drive Shell

A command-line shell for navigating and managing Google Drive files mounted via GVFS, using human-readable display names instead of opaque file IDs.

## Features

- 📁 `ls`, `cd`, `pwd` with display-name mapping
- 🔁 `cp` with support for local ↔ GVFS and GVFS ↔ local
- 🧠 `tab completion` for both local and Drive files
- 📜 `info` command for detailed metadata via `gio`
- 📚 Command history (arrow keys)
- 🧼 Clean human-readable prompt (`/My Drive/Backups`)
- 🧙‍♂️ 100% written in Python, no external deps beyond GVFS

## Requirements

- Linux (GVFS available at `/run/user/UID/gvfs`)
- Python 3.7+
- `gio` CLI tools (`glib2`, `gvfs`)

## Installation

Clone the repo and run it directly:

```bash
chmod +x gvfsh.py
./gvfsh.py
