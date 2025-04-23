#!/usr/bin/env python3

import os
import sys
import shlex
import subprocess
from pathlib import Path

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

def list_dir(path, mapping_store=None):
    entries = list(path.iterdir())
    mapping = {}
    for entry in entries:
        display_name = get_display_name(entry)
        if display_name:
            mapping[display_name] = entry
    for name in sorted(mapping):
        print(name)
    if mapping_store is not None:
        mapping_store.clear()
        mapping_store.update(mapping)
    return mapping

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
            target = args[0]
            #print(f"DEBUG cd to {target} mapping: {mapping} name_to_path: {name_to_path}")
            if target == "..":
                if len(path_stack) > 1:
                    path_stack.pop()
                    current_path = path_stack[-1]
            elif target in name_to_path:
                path_stack.append(name_to_path[target])
                current_path = name_to_path[target]
            else:
                print(f"cd: no such file or directory: {target}")

        elif cmd == "cp":
            if len(args) != 2:
                print("cp: usage: cp <src> <dst>")
                continue
            mapping = list_dir(current_path)
            src = mapping.get(args[0])
            dst = args[1]
            if src:
                subprocess.run(["cp", str(src), dst])
            else:
                print(f"cp: no such file: {args[0]}")

        elif cmd == "pwd":
            display_path = []
            for p in path_stack[1:]:  # Skip the root '/'
                name = get_display_name(p)
                display_path.append(name if name else str(p.name))
            print("/" + "/".join(display_path) if display_path else "/")

        else:
            print(f"{cmd}: command not found")

if __name__ == "__main__":
    print("Welcome to GVFS-Hell Shell™ — where Google Drive makes no sense and we fix it anyway.")
    repl()

