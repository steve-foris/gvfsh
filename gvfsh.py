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

        elif cmd == "cp":
            if len(args) != 2:
                print("cp: usage: cp <src> <dst>")
                continue

            src_arg, dst_arg = args
            # If absolute path or exists on disk, treat as real file
            src_path = Path(src_arg)
            if src_path.is_absolute() and src_path.exists():
                # dst is assumed to be in current GVFS dir by display name
                mapping = list_dir(current_path)
                dst = mapping.get(dst_arg)
                if dst is None:
                    dst = current_path / dst_arg  # assume target name
                try:
                    subprocess.run(["cp", str(src_path), str(dst)], check=True)
                    print(f"Copied {src_path} → {dst}")
                except subprocess.CalledProcessError as e:
                    print(f"cp: failed: {e}")
            else:
                # Otherwise both are assumed to be display-named GVFS files
                mapping = list_dir(current_path)
                src = mapping.get(src_arg)
                if src is None:
                    print(f"cp: no such file: {src_arg}")
                    continue
                dst = current_path / dst_arg
                try:
                    subprocess.run(["cp", str(src), str(dst)], check=True)
                    print(f"Copied {src} → {dst}")
                except subprocess.CalledProcessError as e:
                    print(f"cp: failed: {e}")

            # Check if copying from GVFS to real FS
            if src and dst_arg.startswith("/"):
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

