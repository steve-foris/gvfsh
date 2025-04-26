#!/usr/bin/env python3

import os
import sys
import shlex
import subprocess
from pathlib import Path

import readline
readline.parse_and_bind("tab: complete")

GVFS_BASE = Path(f"/run/user/{os.getuid()}/gvfs")
ROOT = next(GVFS_BASE.glob("google-drive:*"), None)
if not ROOT:
    print("No Google Drive mount found in GVFS.")
    sys.exit(1)

current_path = ROOT

def get_display_name(path):
    try:
        output = subprocess.check_output(["gio", "info", str(path)], text=True)
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("standard::display-name:"):
                return line.replace("standard::display-name:", "").strip()
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to run gio info on {path}:\n{e}")
        return None
    except FileNotFoundError:
        print("[FATAL] 'gio' not found in PATH. Install 'gvfs' and 'glib2'.")
        sys.exit(1)

def list_dir(path, mapping_store=None, silent=False):
    entries = list(path.iterdir())
    mapping = {}
    for entry in entries:
        display_name = get_display_name(entry)
        if display_name:
            mapping[display_name] = entry
    if not silent:
        for name in sorted(mapping):
            print(name)
    if mapping_store is not None:
        mapping_store.clear()
        mapping_store.update(mapping)
    return mapping

def completer(text, state):
    # Combine GVFS display names and system filenames
    matches = []

    try:
        # Local dir matches (real FS)
        real_matches = [f for f in os.listdir('.') if f.startswith(text)]
        matches.extend(real_matches)
    except Exception:
        pass

    try:
        # GVFS display name matches
        mapping = list_dir(current_path, silent=True)
        gvfs_matches = [name for name in mapping if name.startswith(text)]
        matches.extend(gvfs_matches)
    except Exception:
        pass

    matches = sorted(set(matches))
    if state < len(matches):
        return matches[state]
    return None


def repl():
    global current_path
    path_stack = [current_path]
    name_to_path = {}

    while True:
        try:
            display_path = []
            for p in path_stack[1:]:  # Skip root
                name = get_display_name(p)
                display_path.append(name if name else p.name)
            prompt_path = "/" + "/".join(display_path) if display_path else "/"
            cmd_input = input(f"[gvfsh] {prompt_path} > ")
        except EOFError:
            break

        parts = shlex.split(cmd_input.strip())
        if not parts:
            continue

        cmd = parts[0]
        args = parts[1:]

        if cmd == "exit":
            break

        elif cmd == "ls":
            mapping = list_dir(current_path, name_to_path)

        elif cmd == "cd":
            if not args:
                print("cd: missing argument")
                continue

            target = args[0].strip()
            if target == "..":
                if len(path_stack) > 1:
                    path_stack.pop()
                    current_path = path_stack[-1]
                continue

            # Refresh mapping before resolving target
            name_to_path.clear()
            mapping = list_dir(current_path, name_to_path, silent=True)

            if target in name_to_path:
                new_path = name_to_path[target]
                path_stack.append(new_path)
                current_path = new_path
            else:
                print(f"cd: no such file or directory: {target}")

        elif cmd == "mkdir":
            if not args:
                print("mkdir: missing argument")
                continue

            dir_name = args[0].strip()
            mapping = list_dir(current_path, silent=True)
            if dir_name in mapping:
                print(f"mkdir: directory already exists: {dir_name}")
                continue

            new_dir = current_path / dir_name
            try:
                new_dir.mkdir()
                print(f"Created directory: {dir_name}")
            except Exception as e:
                print(f"mkdir: failed: {e}")


        elif cmd == "cp":
            if len(args) != 2:
                print("cp: usage: cp <src> <dst>")
                continue

            src_arg, dst_arg = args
            src_path = Path(src_arg)
            mapping = list_dir(current_path, silent=True)

            if src_path.is_absolute() and src_path.exists():
                # Local filesystem → GVFS
                dst = mapping.get(dst_arg)
                if dst is None:
                    dst = current_path / dst_arg  # Assume creating a new file
                try:
                    subprocess.run(["cp", str(src_path), str(dst)], check=True)
                    print(f"Copied {src_path} → {dst}")
                except subprocess.CalledProcessError as e:
                    print(f"cp: failed: {e}")
            else:
                # GVFS file → something
                src = mapping.get(src_arg)
                if src is None:
                    print(f"cp: no such file: {src_arg}")
                    continue

                if dst_arg.startswith("/"):
                    # GVFS → real filesystem
                    dst_path = Path(dst_arg)
                    if dst_path.is_dir():
                        display_name = get_display_name(src)
                        if display_name:
                            dst_path = dst_path / display_name
                    try:
                        subprocess.run(["gio", "copy", str(src), str(dst_path)], check=True)
                        print(f"Copied {src} → {dst_path} via gio")
                    except subprocess.CalledProcessError as e:
                        print(f"gio cp failed: {e}")
                else:
                    # GVFS → GVFS
                    dst = current_path / dst_arg
                    try:
                        subprocess.run(["cp", str(src), str(dst)], check=True)
                        print(f"Copied {src} → {dst}")
                    except subprocess.CalledProcessError as e:
                        print(f"cp: failed: {e}")

                

        elif cmd == "pwd":
            display_path = []
            for p in path_stack[1:]:  # Skip the root '/'
                name = get_display_name(p)
                display_path.append(name if name else str(p.name))
            print("/" + "/".join(display_path) if display_path else "/")

        elif cmd == "clear":
            os.system("clear")

        elif cmd == "info":
            if not args:
                print("info: missing argument")
                continue

            target = args[0].strip()
            mapping = list_dir(current_path, silent=True)
            if target not in mapping:
                print(f"info: no such file: {target}")
                continue

            target_path = mapping[target]
            try:
                output = subprocess.check_output(["gio", "info", str(target_path)], text=True)
                print(output)
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed to get info on {target_path}:\n{e}")

        elif cmd == "help":
            print("""
            Available commands:
            ls               - List contents of the current directory
            cd <name>        - Change directory by display name (quoted if needed)
            cp <src> <dest>  - Copy files (real ↔ GVFS, or GVFS ↔ real)
            pwd              - Show current human-readable path
            help             - Show this help message
            exit             - Exit gvfsh like a responsible adult
            clear            - Clears the screen
            info             - shows gio info about file
                  
            Tips:
            - Use quotes for names with spaces (e.g. cd "My Drive")
            - Files are copied using gio if needed to handle GVFS madness
            - All filenames shown are their actual Google Drive names (not IDs)
            - Tab completion should work too.
            """)

        else:
            print(f"{cmd}: command not found")


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
    gvfsh.py - Google Drive Shell over GVFS

    Usage:
    ./gvfsh.py           Launch interactive shell
    ./gvfsh.py --help    Show this message and exit

    Requirements:
    - Google Drive mounted via GVFS (e.g. Nautilus)
    - Python 3.7+
    - Packages: glib2, gvfs, gio (CLI)

    This shell allows Google Drive navigation and file operations using display names instead of cryptic IDs.

    Inside the shell, type `help` for a list of commands.
    """)
        sys.exit(0)

    readline.set_completer(completer)
    print("Welcome to GVFS-Shell — CLI navigation of Google Drive")
    repl()

