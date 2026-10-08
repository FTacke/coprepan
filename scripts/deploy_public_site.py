"""Deploy the small static public site of CO.PRE.PAN (2026-10-08, O-2).

The site lives in ``web/coprepan/`` and is served as plain files by an existing nginx virtual host;
this script changes **files only** — no nginx configuration, no certificate, no other site. It uses
the operator's own ``ssh`` / ``scp`` configuration (a host alias); it reads and prints no credential.

    python scripts/deploy_public_site.py manifest                 # what would be deployed (local, no network)
    python scripts/deploy_public_site.py backup  --host H --out D # copy the live docroot + vhost aside, with SHA-256
    python scripts/deploy_public_site.py deploy  --host H         # stage, place, set modes, verify by SHA-256
    python scripts/deploy_public_site.py verify  --url U          # fetch the public pages of this site and compare

This is a deployment tool of the operator's own site. It is not part of the pipeline and it never
touches an outlet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import ssl
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "web" / "coprepan"
REMOTE_ROOT = "/srv/webapps/coprepan"
VHOST = "/etc/nginx/sites-available/coprepan-hispanistica.conf"
_HOST = re.compile(r"[A-Za-z0-9._-]+")
_PATH = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*")


def manifest() -> list[dict]:
    """``{path, sha256, size}`` of every file of the site source, in path order."""
    rows = []
    for path in sorted(p for p in SITE.rglob("*") if p.is_file()):
        relative = path.relative_to(SITE).as_posix()
        if _PATH.fullmatch(relative) is None:
            raise SystemExit(f"not a deployable file name: {relative!r}")
        data = path.read_bytes()
        if b"\r" in data:
            raise SystemExit(f"{relative} has CR bytes: the site source is LF")
        rows.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    return rows


def _host(value: str) -> str:
    if _HOST.fullmatch(value) is None:
        raise SystemExit(f"not a host alias: {value!r}")
    return value


def _ssh(host: str, command: str, *, check: bool = True) -> str:
    done = subprocess.run(["ssh", "-o", "BatchMode=yes", host, command], capture_output=True, text=True, encoding="utf-8")
    if check and done.returncode != 0:
        raise SystemExit(f"remote command failed ({done.returncode}): {done.stderr.strip()[:300]}")
    return done.stdout


def _push(host: str, source: Path, target: str) -> None:
    """Write a local file to a remote path through ssh (no scp: the server's sftp subsystem is not relied on)."""
    done = subprocess.run(["ssh", "-o", "BatchMode=yes", host, f"cat > {target}"], input=source.read_bytes(), capture_output=True)
    if done.returncode != 0:
        raise SystemExit(f"copy failed: {done.stderr.decode(errors='replace').strip()[:300]}")


def _pull(host: str, remote: str) -> bytes:
    done = subprocess.run(["ssh", "-o", "BatchMode=yes", host, f"cat {remote}"], capture_output=True)
    if done.returncode != 0:
        raise SystemExit(f"read failed for {remote}: {done.stderr.decode(errors='replace').strip()[:300]}")
    return done.stdout


def backup(host: str, out: Path) -> dict:
    """Copy the live docroot and the vhost file aside (outside the repository) and record SHA-256."""
    host, out = _host(host), Path(out)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = out / f"coprepan-site-backup-{stamp}"
    target.mkdir(parents=True, exist_ok=False)
    listing = _ssh(host, f"cd {REMOTE_ROOT} && find . -type f | sort")
    files = [line[2:] for line in listing.splitlines() if line.startswith("./")]
    receipt = {"taken_at": stamp, "remote_root": REMOTE_ROOT, "files": []}
    for relative in files:
        if _PATH.fullmatch(relative) is None:
            raise SystemExit(f"unexpected remote file name: {relative!r}")
        destination = target / "docroot" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(_pull(host, f"{REMOTE_ROOT}/{relative}"))
        receipt["files"].append({"path": relative, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "size": destination.stat().st_size})
    vhost = target / "vhost.conf"
    vhost.write_bytes(_pull(host, VHOST))
    receipt["vhost"] = {"remote_path": VHOST, "sha256": hashlib.sha256(vhost.read_bytes()).hexdigest()}
    (target / "RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return {"backup_directory": target.name, **receipt}


def deploy(host: str) -> dict:
    """Stage the site next to the docroot, place each file, set modes, and verify by SHA-256.

    Files only. The docroot's ownership and the existing virtual host are left as they are; nginx
    is neither reloaded nor restarted (it serves files from disk). ``nginx -t`` is run as a check.
    """
    host = _host(host)
    rows = manifest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stage = f"{REMOTE_ROOT}.incoming-{stamp}"
    directories = sorted({str(Path(row["path"]).parent.as_posix()) for row in rows} - {"."})
    _ssh(host, f"set -e; mkdir {stage}; " + "".join(f"mkdir -p {stage}/{d}; " for d in directories))
    for row in rows:
        _push(host, SITE / row["path"], f"{stage}/{row['path']}")
    checks = "".join(f"echo '{row['sha256']}  {stage}/{row['path']}' | sha256sum -c --quiet -; " for row in rows)
    _ssh(host, "set -e; " + checks)                                     # staged bytes are the source bytes
    place = "".join(f"mkdir -p {REMOTE_ROOT}/{d}; chmod 755 {REMOTE_ROOT}/{d}; " for d in directories)
    place += "".join(f"install -m 644 -o root -g root {stage}/{row['path']} {REMOTE_ROOT}/{row['path']}; " for row in rows)
    _ssh(host, "set -e; " + place)
    _ssh(host, "set -e; " + "".join(f"echo '{row['sha256']}  {REMOTE_ROOT}/{row['path']}' | sha256sum -c --quiet -; " for row in rows))
    _ssh(host, f"rm -r {stage}")                                        # our own staging directory, named above
    tested = subprocess.run(["ssh", "-o", "BatchMode=yes", host, "nginx -t"], capture_output=True, text=True)
    return {"deployed_at": stamp, "remote_root": REMOTE_ROOT, "files": rows, "nginx_t": "ok" if tested.returncode == 0 else "FAILED",
            "nginx_t_output": tested.stderr.strip().splitlines()[-1:] }


def verify(url: str) -> dict:
    """Fetch the public pages of this site over HTTPS and compare them with the source."""
    base = url.rstrip("/")
    results = []
    context = ssl.create_default_context()
    for row in manifest():
        path = "/" + row["path"].removesuffix("index.html")
        request = urllib.request.Request(base + path, headers={"User-Agent": "coprepan-site-deploy-check/1"})
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            body = response.read()
            results.append({"url": base + path, "status": response.status, "sha256_matches_source": hashlib.sha256(body).hexdigest() == row["sha256"],
                            "content_type": response.headers.get("Content-Type")})
    return {"checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tls_verified": True, "pages": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("manifest")
    for name in ("backup", "deploy"):
        sub = commands.add_parser(name)
        sub.add_argument("--host", required=True, help="an ssh host alias from the operator's own configuration")
        if name == "backup":
            sub.add_argument("--out", type=Path, required=True)
    sub = commands.add_parser("verify")
    sub.add_argument("--url", required=True)
    arguments = parser.parse_args(argv)
    if arguments.command == "manifest":
        result = {"source": "web/coprepan", "files": manifest()}
    elif arguments.command == "backup":
        result = backup(arguments.host, arguments.out)
    elif arguments.command == "deploy":
        result = deploy(arguments.host)
    else:
        result = verify(arguments.url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
