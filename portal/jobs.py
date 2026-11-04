"""The jobs of the portal: one at a time, in the background, each with its log on disk.

A job outlives a restart of the site: its process group is its own, and its log's last line is the exit code.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

from catalog import BUSY_SCRIPTS

WRAPPER = '"$@"; code=$?; echo; echo "== finished with code $code"; exit $code'
FINISHED = re.compile(r'== finished with code (\d+)\s*$')
JOB_ID = re.compile(r'[0-9]{8}-[0-9]{6}-[a-z-]+')
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
CHUNK = 64 * 1024
HISTORY = 15


class JobError(ValueError):
    pass


def outside_jobs() -> list[str]:
    """The scripts of BUSY_SCRIPTS running on this machine, whoever started them."""
    found = set()
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            words = (entry / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        for word in words[:4]:
            name = os.path.basename(word.decode(errors='replace'))
            if name in BUSY_SCRIPTS:
                found.add(name)
    return sorted(found)


class Jobs:
    def __init__(self, root: Path):
        self.root = root / 'logs'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.children = {}

    def start(self, action: str, title: str, argv: list[str], env: dict, *, dry: bool) -> str:
        with self.lock:
            running = self.running()
            if running:
                raise JobError(f"Wait for “{running['title']}” to finish.")
            busy = outside_jobs()
            if busy:
                raise JobError('A build is running outside the portal (' + ', '.join(busy) + '). Try again when it ends.')
            job_id = time.strftime('%Y%m%d-%H%M%S-') + action
            log = self.root / f'{job_id}.log'
            with log.open('wb') as out:
                process = subprocess.Popen(['nice', '-n', '10', 'bash', '-c', WRAPPER, 'ops-web', *argv],
                                           stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                           start_new_session=True, env={**os.environ, **env}, cwd=str(self.root))
            self.children[job_id] = process
            (self.root / f'{job_id}.json').write_text(json.dumps(
                {'id': job_id, 'action': action, 'title': title, 'dry': dry, 'pid': process.pid, 'started': time.time()}))
            return job_id

    def _describe(self, meta_file: Path) -> dict | None:
        try:
            job = json.loads(meta_file.read_text())
        except (OSError, ValueError):
            return None
        log = meta_file.with_suffix('.log')
        # /proc can read empty while a child execs: a job of this process is asked directly, which also collects it.
        child = self.children.get(job['id'])
        alive = child.poll() is None if child is not None else self._alive(job['pid'])
        job['finished'] = None
        try:
            with log.open('rb') as handle:
                handle.seek(max(0, log.stat().st_size - 200))
                match = FINISHED.search(handle.read().decode(errors='replace'))
        except OSError:
            match = None
        if match:
            job['state'] = 'done' if match.group(1) == '0' else 'failed'
            job['code'] = int(match.group(1))
            job['finished'] = log.stat().st_mtime
        elif alive:
            job['state'] = 'running'
        else:
            job['state'] = 'stopped'
            job['finished'] = log.stat().st_mtime if log.exists() else None
        return job

    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
            return state != 'Z' and b'ops-web' in Path(f'/proc/{pid}/cmdline').read_bytes()
        except (OSError, IndexError):
            return False

    def list(self) -> list[dict]:
        jobs = [self._describe(path) for path in sorted(self.root.glob('*.json'), reverse=True)[:HISTORY]]
        return [job for job in jobs if job]

    def running(self) -> dict | None:
        return next((job for job in self.list() if job['state'] == 'running'), None)

    def stop(self, job_id: str):
        meta = self._file(job_id, 'json')
        job = self._describe(meta)
        if not job or job['state'] != 'running':
            raise JobError('This job is not running.')
        try:
            os.killpg(job['pid'], signal.SIGTERM)
        except OSError as exc:
            raise JobError('This job is not running.') from exc

    def _file(self, job_id: str, suffix: str) -> Path:
        path = self.root / f'{job_id}.{suffix}'
        if not JOB_ID.fullmatch(job_id) or not path.is_file():
            raise JobError('No such job.')
        return path

    def log(self, job_id: str, offset: int) -> dict:
        path = self._file(job_id, 'log')
        with path.open('rb') as handle:
            handle.seek(offset)
            data = handle.read(CHUNK)
        job = self._describe(self._file(job_id, 'json'))
        return {'text': ANSI.sub('', data.decode(errors='replace')), 'offset': offset + len(data), 'job': job}
