#!/usr/bin/env python3
# [joseph sync] - START
"""Import Joseph's training logs, with explicitly optional destination cleanup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile

SOURCE_HOST = "admin@truenas.local"
SOURCE = "/mnt/POOL/FILEBROWSER/DATA/comma/joseph/realdata"
TARGET_HOST = "openpilot-nnlc-joseph"
TARGET = Path("/root/openpilot-nnlc-tools/data")
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
       "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"]
LOG_NAMES = {"rlog.zst", "rlog.bz2"}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_data(path):
    if path.name != "data" or not path.is_dir() or path.is_mount() or path.resolve() != path.absolute():
        raise ValueError(f"Unsafe data directory: {path}")
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            child = Path(parent) / name
            if child.is_symlink() or child.is_mount() or not (child.is_dir() or child.is_file()):
                raise ValueError(f"Unsafe entry in data: {child}")


def snapshot(path):
    validate_data(path)
    return {str(p.relative_to(path)): [p.stat().st_size, p.stat().st_mtime_ns]
            for p in sorted(path.rglob("*")) if p.is_file()}


def clean_data(path):
    validate_data(path)
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def prepare(incoming, ready, paths=None):
    manifest = {}
    files = [incoming / p for p in paths] if paths is not None else sorted(incoming.rglob("*"))
    for src in files:
        if not src.is_file():
            continue
        rel = src.relative_to(incoming)
        if src.name in LOG_NAMES:
            out_rel = rel
            archive = None
        elif src.name.startswith("rlog.") and src.suffix == ".zip":
            archive = zipfile.ZipFile(src)
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if len(entries) != 1:
                archive.close()
                raise ValueError(f"Expected one rlog in {src}")
            member = Path(entries[0].filename)
            if (member.is_absolute() or ".." in member.parts or member.name not in LOG_NAMES
                    or member.parent != rel.parent or entries[0].is_dir()):
                archive.close()
                raise ValueError(f"Unexpected ZIP member: {src}: {member}")
            out_rel = member
        else:
            continue
        out = ready / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_name(out.name + ".preparing")
        try:
            expanded_size = src.stat().st_size if archive is None else entries[0].file_size
            if shutil.disk_usage(ready).free < expanded_size:
                raise ValueError(f"Insufficient space to prepare {out_rel}")
            if archive is None:
                shutil.copyfile(src, temp)
            else:
                with archive, archive.open(entries[0]) as reader, temp.open("wb") as writer:
                    shutil.copyfileobj(reader, writer)
            entry = {"size": temp.stat().st_size, "sha256": digest(temp)}
            if str(out_rel) in manifest and manifest[str(out_rel)] != entry:
                raise ValueError(f"Conflicting logs for {out_rel}")
            if not out.exists() or digest(out) != entry["sha256"]:
                temp.replace(out)
                os.utime(out, (src.stat().st_mtime, src.stat().st_mtime))
            manifest[str(out_rel)] = entry
        finally:
            temp.unlink(missing_ok=True)
    if not manifest:
        raise ValueError("No training logs found; destination was not cleaned")
    return manifest


def remote(action, payload):
    if socket.gethostname() != TARGET_HOST:
        raise ValueError("Unexpected destination hostname; refusing operation")
    current = snapshot(TARGET)
    marker = TARGET.parent / ".nnlc-joseph-truncate-pending"
    if action == "inspect":
        return {"snapshot": current, "free": shutil.disk_usage(TARGET).free,
                "cleanup_pending": marker.exists()}
    if action == "truncate":
        if current != payload["snapshot"]:
            raise ValueError("Destination changed since preflight; refusing cleanup")
        marker.write_text("Cleanup started; do not import until cleanup is complete.\n")
        clean_data(TARGET)
        if list(TARGET.iterdir()):
            raise ValueError("Cleanup incomplete")
        marker.unlink()
        return {"removed_files": len(current)}
    if marker.exists():
        raise ValueError("Incomplete cleanup; verification refused")
    expected = payload["manifest"]
    for rel, entry in expected.items():
        file = TARGET / rel
        if (not file.is_file() or file.stat().st_size != entry["size"]
                or digest(file) != entry["sha256"]):
            raise ValueError(f"Verification failed: {rel}")
    if payload["exact"] and set(current) != set(expected):
        raise ValueError("Unexpected files remain after truncate/import")
    return {"verified_files": len(expected), "total_files": len(current),
            "bytes": sum(x["size"] for x in expected.values())}


def source_inventory():
    code = f'''import json, pathlib, hashlib
p = pathlib.Path({SOURCE!r})
if not p.is_dir() or p.resolve() != p: raise ValueError("Invalid source")
result = {{}}
for f in p.rglob("*"):
    if f.name in {{"rlog.zst", "rlog.bz2"}} or (f.name.startswith("rlog.") and f.suffix == ".zip"):
        if not f.is_file() or f.resolve() != f: raise ValueError("Invalid source file: " + str(f))
        before = f.stat()
        h = hashlib.sha256()
        with f.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        if (before.st_size, before.st_mtime_ns) != (f.stat().st_size, f.stat().st_mtime_ns):
            raise ValueError("Source changed during hashing: " + str(f))
        result[str(f.relative_to(p))] = {{"size": before.st_size, "sha256": h.hexdigest()}}
if not result: raise ValueError("Empty source")
print(json.dumps(result))'''
    result = subprocess.run(SSH + [SOURCE_HOST, shlex.join(["python3", "-c", code])],
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def transfer(source, target, paths):
    command = ["rsync", "-rlt", "--checksum", "--partial", "--stats", "--from0", "--files-from=-",
               "-e", shlex.join(SSH), source, target]
    subprocess.run(command, input=b"".join(os.fsencode(p) + b"\0" for p in sorted(paths)), check=True)


def verify_files(root, manifest):
    if not manifest:
        raise ValueError("Empty manifest")
    root = root.resolve()
    for rel, entry in manifest.items():
        path = Path(rel)
        file = root / path
        if path.is_absolute() or ".." in path.parts or file.resolve() != file:
            raise ValueError(f"Unsafe manifest path: {rel}")
        if not file.is_file() or file.stat().st_size != entry["size"] or digest(file) != entry["sha256"]:
            raise ValueError(f"SHA-256 verification failed: {rel}")


def export_usb(volume, dry_run=False):
    volume = volume.absolute()
    if not volume.is_mount() or volume.resolve() != volume:
        raise ValueError(f"USB volume is not mounted at {volume}")
    source = source_inventory()
    total = sum(entry["size"] for entry in source.values())
    print(f"TrueNAS: {len(source)} compressed files, {total:,} bytes. Source is read-only.", flush=True)
    bundle = volume / "joseph-nnlc"
    incoming = bundle / "realdata"
    if incoming.resolve() != incoming:
        raise ValueError("USB destination must not contain symlinks")
    for name in ("sync_logs.py", "manifest.json", "manifest.json.tmp"):
        metadata = bundle / name
        if metadata.resolve() != metadata:
            raise ValueError(f"USB metadata must not be a symlink: {metadata}")
    for rel in source:
        target = incoming / rel
        if target.resolve() != target:
            raise ValueError(f"USB destination contains a symlink: {target}")
    if dry_run:
        print(f"Dry run: copy to {incoming}; no Joseph connection, cleanup, or ZIP extraction.")
        return
    missing = sum(entry["size"] for rel, entry in source.items()
                  if not (incoming / rel).is_file() or (incoming / rel).stat().st_size != entry["size"])
    if shutil.disk_usage(volume).free < missing + max(entry["size"] for entry in source.values()):
        raise ValueError("Insufficient USB space")
    incoming.mkdir(parents=True, exist_ok=True)
    transfer(f"{SOURCE_HOST}:{SOURCE}/", str(incoming) + "/", source)
    verify_files(incoming, source)
    manifest_tmp = bundle / "manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(source, indent=2) + "\n")
    manifest_tmp.replace(bundle / "manifest.json")
    script = bundle / "sync_logs.py"
    script_source = Path(__file__).read_text()
    with script.open("w") as stream:
        stream.write(script_source)
        stream.flush()
        os.fsync(stream.fileno())
    print(f"USB ready: {len(source)} files, {total:,} bytes; SHA-256 matches TrueNAS. {bundle}", flush=True)


def import_usb(volume, truncate=False, dry_run=False):
    before = remote("inspect", {})
    if before["cleanup_pending"] and not truncate:
        raise ValueError("Previous cleanup incomplete; inspect and resume explicitly with --truncate")
    bundle = volume / "joseph-nnlc"
    source = json.loads((bundle / "manifest.json").read_text())
    incoming = bundle / "realdata"
    verify_files(incoming, source)
    print(f"USB verified: {len(source)} compressed files. Truncate: {truncate}", flush=True)
    if dry_run:
        print("Dry run: no destination changes or ZIP extraction.")
        return
    with tempfile.TemporaryDirectory(prefix=".joseph-import-", dir=TARGET.parent) as tmp:
        ready = Path(tmp)
        manifest = prepare(incoming, ready, source)
        if truncate:
            print(json.dumps(remote("truncate", {"snapshot": before["snapshot"]})), flush=True)
        # Prepared files live on the destination filesystem, so replacement needs no second copy.
        for rel in manifest:
            dest = TARGET / rel
            if dest.resolve() != dest:
                raise ValueError(f"Unsafe import path: {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            (ready / rel).replace(dest)
        result = remote("verify", {"manifest": manifest, "exact": truncate})
        print("SHA-256 verification: " + json.dumps(result), flush=True)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Copy Joseph logs from TrueNAS to USB; import offline on Joseph.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--usb", type=Path, help="Export compressed logs to this mounted USB volume (default: /Volumes/chiavetta)")
    mode.add_argument("--import-usb", type=Path, help="Run ON Joseph: import from this USB mount, without network")
    parser.add_argument("--truncate", action="store_true", help="Only with --import-usb: clear Joseph data before import")
    parser.add_argument("--dry-run", action="store_true", help="Read-only preflight")
    args = parser.parse_args(argv)
    if args.truncate and args.import_usb is None:
        parser.error("--truncate is allowed only with --import-usb on Joseph")
    return args


def main():
    args = parse_args()
    if args.import_usb is not None:
        import_usb(args.import_usb, args.truncate, args.dry_run)
    else:
        for name in ("ssh", "rsync"):
            if not shutil.which(name):
                raise ValueError(f"Missing executable: {name}")
        export_usb(args.usb or Path("/Volumes/chiavetta"), args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(f"Command failed (exit {exc.returncode}). {exc.stderr or ''}", file=sys.stderr)
        print("After an interrupted transfer, retry WITHOUT --truncate. Incomplete cleanup is blocked separately.", file=sys.stderr)
        sys.exit(exc.returncode)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
# [joseph sync] - END
