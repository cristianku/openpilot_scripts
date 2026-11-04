#!/usr/bin/env python3
"""ops-web: openpilot cristianku home. It shows what is behind and starts the skills of this repository.

Python standard library only. See portal/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

import catalog  # noqa: E402
from jobs import JobError, Jobs  # noqa: E402
from status import Status  # noqa: E402

PAGE = Path(__file__).with_name('index.html')
ROOT = Path(os.environ.get('OPS_WEB_ROOT', '/root/work/ops-web'))
COOKIE = 'ops_web'
SESSION_S = 30 * 24 * 3600
MAX_BODY = 16 * 1024
FAILURES_PER_MINUTE = 5
JOB_PATH = re.compile(r'/api/jobs/([0-9a-z-]+)/(log|stop)')
LOOPBACK = {'127.0.0.1', '::1'}


def _ips(name: str) -> set[str]:
    return {str(ipaddress.ip_address(value.strip())) for value in os.environ.get(name, '').split(',') if value.strip()}


class App:
    def __init__(self, root: Path, token: str, *, port: int, allowed: set[str], proxies: set[str], hosts: set[str],
                 interval: int = 600, group: str = 'farm', proxy_secret: str = ''):
        self.token = token
        self.proxy_secret = proxy_secret
        self.key = hashlib.sha256(b'ops-web session\0' + token.encode()).digest()
        self.allowed = allowed | proxies | LOOPBACK
        self.proxies = proxies
        self.hosts = hosts | {f'127.0.0.1:{port}', f'localhost:{port}'}
        self.group = group
        self.status = Status(root, interval=interval)
        self.jobs = Jobs(root)
        self.failures = []
        self.lock = threading.Lock()
        self.watched = None

    def session(self) -> str:
        expires = str(int(time.time()) + SESSION_S)
        return expires + '.' + hmac.new(self.key, expires.encode(), hashlib.sha256).hexdigest()

    def session_valid(self, value: str) -> bool:
        expires, _, mac = value.partition('.')
        if not expires.isdigit() or int(expires) < time.time():
            return False
        return hmac.compare_digest(mac, hmac.new(self.key, expires.encode(), hashlib.sha256).hexdigest())

    def sign_in(self, code: str) -> bool:
        with self.lock:
            now = time.time()
            self.failures = [moment for moment in self.failures if now - moment < 60]
            if len(self.failures) >= FAILURES_PER_MINUTE:
                return False
            if hmac.compare_digest(code.encode(), self.token.encode()):
                return True
            self.failures.append(now)
            return False

    def state(self) -> dict:
        jobs = self.jobs.list()
        running = next((job for job in jobs if job['state'] == 'running'), None)
        # A finished job may have moved a branch: read GitHub again.
        if self.watched and not running:
            self.status.wake.set()
        self.watched = running['id'] if running else None
        return {'status': self.status.read(), 'jobs': jobs, 'groups': catalog.GROUPS,
                'skills': [catalog.public(skill) for skill in catalog.SKILLS],
                'missing': catalog.skills_without_entry()}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        server_version = 'ops-web'
        sys_version = ''
        timeout = 60

        def log_message(self, *args):
            pass

        def _send(self, code: int, body: bytes, kind: str, headers=()):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: dict, headers=()):
            self._send(code, json.dumps(payload).encode(), 'application/json', headers)

        def _peer_allowed(self) -> bool:
            peer = self.client_address[0].removeprefix('::ffff:')
            if peer in app.allowed:
                return True
            print(f"refused {peer} {self.command} {urlsplit(self.path).path} "
                  f"host={self.headers.get('Host', '-')} forwarded={self.headers.get('X-Forwarded-For', '-')}", flush=True)
            return False

        def _authentik(self) -> bool:
            """The proxy has signed the person in. The address alone does not prove it: every container of the proxy's
            machine leaves from that address, so only Traefik's secret header makes these headers count."""
            peer = self.client_address[0].removeprefix('::ffff:')
            secret = self.headers.get('X-Ops-Proxy-Secret', '')
            if peer not in app.proxies or not app.proxy_secret or not self.headers.get('X-authentik-username'):
                return False
            if not hmac.compare_digest(secret.encode(), app.proxy_secret.encode()):
                return False
            return app.group in self.headers.get('X-authentik-groups', '').split('|')

        def _signed_in(self) -> bool:
            if self._authentik():
                return True
            for part in self.headers.get('Cookie', '').split(';'):
                name, _, value = part.strip().partition('=')
                if name == COOKIE and app.session_valid(value):
                    return True
            return False

        def _cookie(self, value: str, age: int) -> tuple[str, str]:
            secure = '; Secure' if self.headers.get('X-Forwarded-Proto') == 'https' else ''
            return 'Set-Cookie', f'{COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}{secure}'

        def _guard(self) -> bool:
            if not self._peer_allowed():
                self._send(403, b'Forbidden', 'text/plain')
                return False
            if self.headers.get('Host', '') not in app.hosts:
                self._send(403, b'Forbidden', 'text/plain')
                return False
            return True

        def do_GET(self):
            if not self._guard():
                return
            url = urlsplit(self.path)
            if url.path == '/':
                self._send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
            elif not self._signed_in():
                self._json(401, {'error': 'Sign in first.'})
            elif url.path == '/api/state':
                self._json(200, app.state())
            elif (match := JOB_PATH.fullmatch(url.path)) and match.group(2) == 'log':
                offset = parse_qs(url.query).get('offset', ['0'])[0]
                try:
                    self._json(200, app.jobs.log(match.group(1), int(offset) if offset.isdigit() else 0))
                except JobError as exc:
                    self._json(404, {'error': str(exc)})
            else:
                self._json(404, {'error': 'Not found.'})

        def _body(self) -> dict | None:
            length = self.headers.get('Content-Length', '')
            if not length.isdigit() or int(length) > MAX_BODY:
                return None
            try:
                body = json.loads(self.rfile.read(int(length)) or b'{}')
            except ValueError:
                return None
            return body if isinstance(body, dict) else None

        def do_POST(self):
            if not self._guard():
                return
            body = self._body()
            # A form of another site cannot set this header: no request forgery.
            if body is None or self.headers.get('X-Requested-With') != 'ops-web':
                self.close_connection = True
                self._json(400, {'error': 'Bad request.'})
                return
            path = urlsplit(self.path).path
            if path == '/api/sign-in':
                if app.sign_in(str(body.get('code', ''))):
                    self._json(200, {'ok': True}, [self._cookie(app.session(), SESSION_S)])
                else:
                    time.sleep(1)
                    self._json(401, {'error': 'That code is not right.'})
            elif path == '/api/sign-out':
                self._json(200, {'ok': True}, [self._cookie('', 0)])
            elif not self._signed_in():
                self._json(401, {'error': 'Sign in first.'})
            elif path == '/api/refresh':
                app.status.wake.set()
                self._json(200, {'ok': True})
            elif path == '/api/run':
                self._run(body)
            elif (match := JOB_PATH.fullmatch(path)) and match.group(2) == 'stop':
                try:
                    app.jobs.stop(match.group(1))
                    self._json(200, {'ok': True})
                except JobError as exc:
                    self._json(409, {'error': str(exc)})
            else:
                self._json(404, {'error': 'Not found.'})

        def _run(self, body: dict):
            action = str(body.get('action', ''))
            dry = body.get('dry') is True
            params = body.get('params') if isinstance(body.get('params'), dict) else {}
            try:
                argv, env = catalog.resolve(action, params, dry)
                title = catalog.BY_ID[action]['title']
                self._json(200, {'id': app.jobs.start(action, title, argv, env, dry=dry)})
            except (catalog.ActionError, JobError) as exc:
                self._json(409, {'error': str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8768)
    args = parser.parse_args()
    token = os.environ.get('OPS_WEB_TOKEN', '')
    if len(token) < 16:
        sys.exit('OPS_WEB_TOKEN is missing or too short: see portal/install_service.sh')
    ROOT.mkdir(parents=True, exist_ok=True)
    hosts = {host.strip() for host in os.environ.get('OPS_WEB_HOSTS', 'ops.farm.14bodhi.com').split(',') if host.strip()}
    app = App(ROOT, token, port=args.port, allowed=_ips('OPS_WEB_ALLOWED_IPS'), proxies=_ips('OPS_WEB_PROXY_IPS'),
              hosts=hosts, proxy_secret=os.environ.get('OPS_WEB_PROXY_SECRET', ''))
    app.status.start()
    print(f'ops-web on {args.host}:{args.port}', flush=True)
    ThreadingHTTPServer((args.host, args.port), make_handler(app)).serve_forever()


if __name__ == '__main__':
    main()
