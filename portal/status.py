"""How far every branch is from what it follows, read from GitHub into a small bare cache.

The list of sources is docs/external-branches.md. Only commits and trees are fetched (no file contents), so counting
commits and reading submodule pointers needs no token and no rate limit. This cache is not FORK_CACHE: a refresh must
not get in the way of a running update.
"""
from __future__ import annotations

import json
import subprocess
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPOS = {
    'sunnypilot/sunnypilot': ['master'],
    'commaai/openpilot': ['master'],
    'cristianku/sunnypilot': ['master', 'distilled', 'speed-limits', 'nav-alpha'],
    'cristianku/openpilot': ['master', 'sunny-nav-alpha', 'nav-alpha', 'distilled', 'psa-torque-sunny-testing',
                             'psa-torque-testing', 'psa-torque-sunny', 'psa-torque', 'psa-torque-sunny-speed'],
    'sunnypilot/opendbc': ['master'],
    'commaai/opendbc': ['master'],
    'cristianku/opendbc': ['psa-torque-sunny-testing', 'psa-torque-testing', 'psa-torque-sunny', 'psa-torque'],
    'sunnypilot/neural-network-data': ['master'],
    'cristianku/neural-network-data': ['master'],
    'cristianku/speed-limits-models': ['main'],
}
SUNNY = 'sunnypilot/sunnypilot:master'
COMMA = 'commaai/openpilot:master'
TESTING = 'cristianku/openpilot:psa-torque-sunny-testing'
OPENDBC_TESTING = 'cristianku/opendbc:psa-torque-sunny-testing'
NEURAL = 'cristianku/neural-network-data:master'
SPEED = 'cristianku/sunnypilot:speed-limits'
MODELS = 'cristianku/speed-limits-models:main'
NAV = 'cristianku/openpilot:sunny-nav-alpha'
DISTILLED = 'cristianku/sunnypilot:distilled'
NEURAL_PATH = 'openpilot/sunnypilot/neural_network_data'
MODELS_PATH = 'openpilot/sunnypilot/speed_limits/models'
# Set by the setup itself, and compared one by one in _testing.
BUILD_PATHS = {'.gitmodules', 'opendbc_repo', NEURAL_PATH, MODELS_PATH}
NO_BLOB = '0' * 40
SITES = [('speedlimits-web', 'Speed limits site'), ('distill-web', 'Distill site'), ('perception-web', 'Perception site')]
INTERVAL_S = 600
ASK_CLAUDE = 'Ask Claude to merge sunnypilot master into speed-limits.'


def _ref(key: str) -> str:
    return 'refs/ops/' + key.replace(':', '/')


def _plural(count: int, word: str = 'commit') -> str:
    return f'{count} {word}{"" if count == 1 else "s"}'


class Cache:
    """The bare repository of the refs of REPOS."""

    def __init__(self, path: Path):
        self.path = path

    def git(self, *args: str, timeout: int = 180) -> str:
        return subprocess.run(['git', '-C', str(self.path), *args], check=True, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()

    def prepare(self):
        if not (self.path / 'HEAD').exists():
            self.path.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'init', '-q', '--bare', str(self.path)], check=True)
            self.git('config', 'gc.auto', '0')

    def update(self, repo: str, branches: list[str]) -> list[str]:
        """Fetches the branches of a repository that moved; the keys of those GitHub no longer has come back."""
        url = f'https://github.com/{repo}.git'
        listed = subprocess.run(['git', 'ls-remote', '--heads', url], check=True, capture_output=True, text=True,
                                timeout=60).stdout
        remote = {line.split('\t')[1].removeprefix('refs/heads/'): line.split('\t')[0] for line in listed.splitlines()}
        moved = [branch for branch in branches if branch in remote and remote[branch] != self.head(f'{repo}:{branch}')]
        if moved:
            self.git('fetch', '-q', '--no-tags', '--filter=blob:none', url,
                     *[f'+refs/heads/{branch}:{_ref(f"{repo}:{branch}")}' for branch in moved], timeout=600)
        return [f'{repo}:{branch}' for branch in branches if branch not in remote]

    def head(self, key: str) -> str | None:
        try:
            return self.git('rev-parse', '--verify', '-q', _ref(key))
        except subprocess.CalledProcessError:
            return None

    def parent(self, key: str) -> str:
        return self.git('rev-parse', _ref(key) + '^')

    def count(self, since: str, until: str) -> int:
        """Commits of ``until`` that ``since`` does not have; either a key or a commit."""
        return int(self.git('rev-list', '--count', f'{self._name(since)}..{self._name(until)}'))

    def time(self, key: str) -> int:
        return int(self.git('log', '-1', '--format=%ct', _ref(key)))

    def link(self, key: str, path: str) -> str | None:
        """The commit a submodule of this branch points to."""
        line = self.git('ls-tree', _ref(key), path)
        return line.split()[2] if line else None

    def base(self, one: str, other: str) -> str:
        return self.git('merge-base', _ref(one), _ref(other))

    def files(self, key: str) -> dict[str, str]:
        """Path and object of everything in a branch; trees only, so no file has to be downloaded."""
        lines = self.git('ls-tree', '-r', _ref(key)).splitlines()
        return {line.split('\t', 1)[1]: line.split()[2] for line in lines}

    def changes(self, since: str, key: str) -> dict[str, str]:
        """Path and new object of what a branch changed since a commit."""
        lines = self.git('diff-tree', '-r', '--no-commit-id', since, _ref(key)).splitlines()
        return {line.split('\t', 1)[1]: line.split()[3] for line in lines}

    @staticmethod
    def _name(name: str) -> str:
        return _ref(name) if ':' in name else name


def _item(cache, key: str, group: str, title: str, what: str, **extra) -> dict:
    repo, branch = key.split(':')
    head = cache.head(key)
    return {'id': key, 'group': group, 'title': title, 'what': what, 'repo': repo, 'branch': branch,
            'url': f'https://github.com/{repo}/tree/{branch}', 'head': head,
            'time': cache.time(key) if head else None, 'state': 'ok', 'summary': 'Up to date', 'reasons': [], **extra}


def _follows(cache, key: str, upstream: str, group: str, title: str, what: str, *, fix: dict | None = None,
             quiet: bool = False) -> dict:
    """A branch that must hold everything of its upstream."""
    item = _item(cache, key, group, title, what, quiet=quiet)
    if item['head'] is None or cache.head(upstream) is None:
        return {**item, 'state': 'unknown', 'summary': 'Not on GitHub'}
    behind = cache.count(key, upstream)
    item['behind'] = behind
    if behind:
        item.update(state='behind', summary=f'{_plural(behind)} behind {upstream.replace(":", " ")}', fix=fix)
    return item


def _nav(cache, key: str, upstream: str, group: str, title: str, action: str, *, quiet: bool = False) -> dict:
    item = _follows(cache, key, upstream, group, title,
                    'Nav2Pilot: what the apps need to send routes to the comma. One commit on top of master.',
                    fix={'action': action}, quiet=quiet)
    if item['head'] and cache.head(upstream) and cache.count(upstream, key) != 1:
        item.update(state='behind', summary='Not one commit on master any more',
                    fix={'hint': 'Ask Claude to redo it with OP-apply-nav-alpha.'})
    return item


def _injected_changes(cache) -> list[str]:
    """Which injected branches the build does not hold. A realignment moves a branch without changing what it adds,
    so files are compared, not dates. A file that two branches change, or that master changed too, ends up merged in
    the build, with neither one's content, and is left out."""
    bases = {'Nav2Pilot': (cache.parent(NAV), NAV), 'speed-limits': (cache.base(SUNNY, SPEED), SPEED),
             'distilled': (cache.base(SUNNY, DISTILLED), DISTILLED)}
    sources = {label: cache.changes(base, key) for label, (base, key) in bases.items()}
    seen = Counter(path for changed in sources.values() for path in changed)
    built = cache.files(TESTING)
    reasons = []
    for label, changed in sources.items():
        merged = cache.changes(bases[label][0], SUNNY)
        if any(built.get(path, NO_BLOB) != blob for path, blob in changed.items()
               if seen[path] == 1 and path not in BUILD_PATHS and path not in merged):
            reasons.append(f'{label} changed')
    return reasons


def _testing(cache) -> dict:
    """The branch of the comma: it is out of date when anything it is built from moved after it was built."""
    item = _item(cache, TESTING, 'car', 'The branch your comma runs',
                 'Rebuilt from master with everything below. Commits made on it directly are lost at the next build.')
    if item['head'] is None:
        return {**item, 'state': 'unknown', 'summary': 'Not on GitHub'}
    reasons = []
    behind = cache.count(cache.parent(TESTING), SUNNY)
    if behind:
        reasons.append(f'sunnypilot master has {_plural(behind, "new commit")}')
    for label, path, source in (('opendbc', 'opendbc_repo', OPENDBC_TESTING), ('The steering model', NEURAL_PATH, NEURAL)):
        if cache.link(TESTING, path) != cache.head(source):
            reasons.append(f'{label} changed')
    if cache.link(TESTING, MODELS_PATH) != cache.link(SPEED, MODELS_PATH):
        reasons.append('The speed limit networks changed')
    reasons += _injected_changes(cache)
    if reasons:
        item.update(state='behind', summary=reasons[0] if len(reasons) == 1 else f'{len(reasons)} things changed',
                    reasons=reasons, fix={'action': 'setup-testing', 'params': {'variant': 'sunny', 'base': 'master'}})
    return item


def _models(cache) -> dict:
    item = _item(cache, MODELS, 'sources', 'Speed limit networks',
                 'The networks that go on the comma. Models › Publish on the speed limits site puts new ones here.')
    if item['head'] and cache.link(SPEED, MODELS_PATH) != item['head']:
        item.update(state='behind', summary='speed-limits points to an older version',
                    fix={'hint': 'Models › Publish on the speed limits site moves the pointer.'})
    return item


def _generated(cache, key: str, upstream: str, title: str) -> dict:
    item = _item(cache, key, 'other', title, 'A generated branch your comma does not run.', quiet=True)
    if item['head'] is None:
        return {**item, 'state': 'unknown', 'summary': 'Not on GitHub'}
    behind = cache.count(cache.parent(key), upstream)
    item['behind'] = behind
    if behind:
        item.update(state='behind', summary=f'Built {_plural(behind)} ago')
    return item


def _promote(cache, stable: str, testing: str, title: str, action: str) -> dict:
    item = _item(cache, stable, 'other', title, 'Stable opendbc. It takes the testing branch once the port is proven.',
                 quiet=True)
    waiting = cache.count(stable, testing)
    item['behind'] = waiting
    if waiting:
        item.update(state='behind', summary=f'{_plural(waiting)} waiting in testing', fix={'action': action})
    return item


def evaluate(cache) -> list[dict]:
    fork_hint = {'hint': 'Sync fork on GitHub: only you can do this one.'}
    return [
        _testing(cache),
        _nav(cache, NAV, SUNNY, 'sources', 'Nav2Pilot', 'update-sunny-nav-alpha'),
        _follows(cache, DISTILLED, SUNNY, 'sources', 'Distill models list',
                 'Shows your driving models in the Models menu of the comma and in SunnyLink.',
                 fix={'action': 'update-distilled'}),
        _follows(cache, SPEED, SUNNY, 'sources', 'Speed limits',
                 'Map Data + Vision, speedvisiond and the networks submodule.', fix={'hint': ASK_CLAUDE}),
        _models(cache),
        _follows(cache, OPENDBC_TESTING, 'sunnypilot/opendbc:master', 'sources', 'PSA port (opendbc)',
                 'The Peugeot 3008 port and the radar logging.',
                 fix={'action': 'merge-upstream', 'params': {'variant': 'sunny'}}),
        _follows(cache, NEURAL, 'sunnypilot/neural-network-data:master', 'sources', 'Steering model',
                 'The NNLC lateral model of the 3008.', fix=fork_hint),
        _follows(cache, 'cristianku/sunnypilot:master', SUNNY, 'forks', 'sunnypilot fork',
                 'Your copy of sunnypilot master.', fix=fork_hint),
        _follows(cache, 'cristianku/openpilot:master', COMMA, 'forks', 'openpilot fork',
                 'Your copy of comma.ai master.', fix=fork_hint),
        _nav(cache, 'cristianku/openpilot:nav-alpha', COMMA, 'other', 'Nav2Pilot for comma.ai', 'update-nav-alpha',
             quiet=True),
        _follows(cache, 'cristianku/opendbc:psa-torque-testing', 'commaai/opendbc:master', 'other',
                 'PSA port for comma.ai', 'The port on comma.ai opendbc.',
                 fix={'action': 'merge-upstream', 'params': {'variant': 'comma'}}, quiet=True),
        _promote(cache, 'cristianku/opendbc:psa-torque-sunny', OPENDBC_TESTING, 'Stable PSA port, sunnypilot',
                 'merge-sunny-stable'),
        _promote(cache, 'cristianku/opendbc:psa-torque', 'cristianku/opendbc:psa-torque-testing',
                 'Stable PSA port, comma.ai', 'merge-comma-stable'),
        _generated(cache, 'cristianku/openpilot:psa-torque-testing', COMMA, 'comma.ai testing branch'),
        _generated(cache, 'cristianku/openpilot:psa-torque-sunny', SUNNY, 'sunnypilot stable branch'),
        _generated(cache, 'cristianku/openpilot:psa-torque', COMMA, 'comma.ai stable branch'),
        _generated(cache, 'cristianku/openpilot:psa-torque-sunny-speed', SUNNY, 'Speed-limit work branch'),
    ]


def to_do(items: list[dict], comma: dict | None) -> list[dict]:
    """What needs doing, first things first: a build takes its sources from the forks, and the comma from the build."""
    order = ['forks', 'sources', 'car']
    steps = sorted((item for item in items if item['state'] == 'behind' and not item.get('quiet')),
                   key=lambda item: order.index(item['group']))
    steps = [{'id': item['id'], 'title': item['title'], 'summary': item['summary'], 'fix': item.get('fix'),
              'url': item['url'], 'repo': item['repo'], 'branch': item['branch']} for item in steps]
    if comma and comma.get('reachable') and not comma.get('latest'):
        steps.append({'id': 'comma', 'title': 'Your comma', 'summary': 'It is not on the latest build',
                      'fix': {'action': 'update-comma'}})
    return steps


def read_comma(testing_head: str | None) -> dict:
    """What the comma runs. Read-only; an unreachable comma is normal, it is off or away."""
    try:
        out = subprocess.run(['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes', 'comma',
                              'cd /data/openpilot && git rev-parse HEAD && git rev-parse --abbrev-ref HEAD'],
                             check=True, capture_output=True, text=True, timeout=15).stdout.split()
    except (subprocess.SubprocessError, OSError):
        return {'reachable': False}
    return {'reachable': True, 'head': out[0], 'branch': out[1], 'latest': out[0] == testing_head}


def read_sites() -> list[dict]:
    sites = []
    for name, title in SITES:
        state = subprocess.run(['systemctl', 'is-active', name], capture_output=True, text=True).stdout.strip()
        sites.append({'name': name, 'title': title, 'up': state == 'active'})
    return sites


class Status:
    """The last reading, kept on disk so the page never waits for GitHub."""

    def __init__(self, root: Path, *, interval: int = INTERVAL_S):
        self.file = root / 'status.json'
        self.cache = Cache(root / 'cache.git')
        self.interval = interval
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.refreshing = False
        self.state = {'items': [], 'comma': None, 'sites': [], 'todo': [], 'checked_at': None, 'errors': []}
        if self.file.is_file():
            self.state = json.loads(self.file.read_text())

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            self.refresh()
            self.wake.wait(self.interval)
            self.wake.clear()

    def refresh(self):
        with self.lock:
            if self.refreshing:
                return
            self.refreshing = True
        try:
            self.cache.prepare()
            errors = []

            def fetch(entry):
                try:
                    errors.extend(f'{key} is not on GitHub' for key in self.cache.update(*entry))
                except (subprocess.SubprocessError, OSError):
                    errors.append(f'Could not read {entry[0]}')

            with ThreadPoolExecutor(4) as pool:
                list(pool.map(fetch, REPOS.items()))
            items = evaluate(self.cache)
            comma = read_comma(items[0]['head'])
            state = {'items': items, 'comma': comma, 'sites': read_sites(), 'todo': to_do(items, comma),
                     'checked_at': time.time(), 'errors': errors}
            self.state = state
            temporary = self.file.with_suffix('.tmp')
            temporary.write_text(json.dumps(state))
            temporary.replace(self.file)
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            self.state = {**self.state, 'errors': [f'The check failed: {type(exc).__name__}']}
        finally:
            self.refreshing = False

    def read(self) -> dict:
        return {**self.state, 'refreshing': self.refreshing}
