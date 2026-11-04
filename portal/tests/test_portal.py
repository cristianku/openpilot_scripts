import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog  # noqa: E402
import jobs as jobs_module  # noqa: E402
import server  # noqa: E402
import status  # noqa: E402

TOKEN = 'a-test-code-of-enough-length'


class CatalogTest(unittest.TestCase):
    def test_every_skill_has_an_entry(self):
        self.assertEqual(catalog.skills_without_entry(), [])

    def test_a_setup_builds_on_the_commit_asked(self):
        argv, _ = catalog.resolve('setup-testing', {'variant': 'sunny', 'base': 'master', 'commit': 'abc1234'}, False)
        self.assertEqual(argv[-2:], ['sunny', 'master=abc1234'])

    def test_each_opendbc_variant_merges_in_its_own_clone(self):
        dirs = {catalog.resolve('merge-upstream', {'variant': variant}, False)[1]['OPENDBC_DIR'] for variant in ('sunny', 'comma')}
        self.assertEqual(len(dirs), 2)

    def test_a_parameter_outside_its_list_is_refused(self):
        for params in ({'variant': '-x', 'base': 'master'}, {'variant': 'sunny', 'base': 'master; id'},
                       {'variant': 'sunny', 'base': 'master', 'commit': '--upload-pack=x'},
                       {'variant': 'sunny', 'base': 'release', 'commit': 'abc1234'}):
            with self.assertRaises(catalog.ActionError):
                catalog.resolve('setup-testing', params, False)

    def test_a_skill_without_a_button_cannot_run(self):
        for action in ('news', 'apply-nav-alpha', 'nothing'):
            with self.assertRaises(catalog.ActionError):
                catalog.resolve(action, {}, False)

    def test_a_trial_publishes_nothing_and_stays_out_of_the_workspace(self):
        _, env = catalog.resolve('setup-speed', {'base': 'master', 'commit': ''}, True)
        self.assertEqual(env['NO_PUSH'], 'true')
        self.assertNotEqual(env['WORKSPACE_ROOT'], str(catalog.WORKSPACE))
        argv, _ = catalog.resolve('update-comma', {'reboot': 'yes'}, True)
        self.assertIn('--dry-run', argv)

    def test_no_trial_where_there_is_none(self):
        with self.assertRaises(catalog.ActionError):
            catalog.resolve('reset-learned', {'reboot': 'no'}, True)

    def test_whatever_moves_a_branch_says_what_goes_into_what(self):
        for skill in catalog.SKILLS:
            if skill['group'] in ('Keep up to date', 'Build for the car', 'Promote to stable'):
                self.assertTrue(skill['flow'], skill['id'])
                self.assertTrue(all(' → ' in line for lines in skill['flow'].values() for line in lines), skill['id'])

    def test_a_flow_per_choice_matches_the_choices(self):
        for skill in catalog.SKILLS:
            keys = set(skill.get('flow', {})) - {''}
            if keys:
                self.assertEqual(keys, {value for value, _ in skill['params'][0]['choices']}, skill['id'])

    def test_the_page_gets_no_command(self):
        self.assertFalse({'argv', 'env', 'dry_env'} & set(catalog.public(catalog.BY_ID['setup-testing'])))


class SyncForkTest(unittest.TestCase):
    """scripts/sync_fork.sh against two local bare repositories in place of GitHub."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.work = self.root / 'work'
        self.git('init', '-q', '-b', 'master', str(self.work), cwd=self.root)
        self.commit('first')
        for repo in ('sunnypilot/sunnypilot', 'cristianku/sunnypilot'):
            self.bare(repo).parent.mkdir(parents=True, exist_ok=True)
            self.git('clone', '-q', '--bare', str(self.work), str(self.bare(repo)), cwd=self.root)

    def bare(self, repo):
        return self.root / 'hub' / f'{repo}.git'

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd or self.work, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        self.git('-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def sync(self, **env):
        script = catalog.REPO / 'scripts' / 'sync_fork.sh'
        return subprocess.run(['bash', str(script), 'sunnypilot'], capture_output=True, text=True,
                              env={**os.environ, 'GITHUB': str(self.root / 'hub'),
                                   'FORK_CACHE': str(self.root / 'cache.git'), **env})

    def master(self, repo):
        return self.git('rev-parse', 'master', cwd=self.bare(repo))

    def publish(self, repo):
        self.git('push', '-q', str(self.bare(repo)), 'master')

    def test_the_fork_moves_to_upstream(self):
        head = self.commit('new')
        self.publish('sunnypilot/sunnypilot')
        self.assertEqual(self.sync().returncode, 0)
        self.assertEqual(self.master('cristianku/sunnypilot'), head)

    def test_a_trial_moves_nothing(self):
        before = self.master('cristianku/sunnypilot')
        self.commit('new')
        self.publish('sunnypilot/sunnypilot')
        self.assertEqual(self.sync(NO_PUSH='true').returncode, 0)
        self.assertEqual(self.master('cristianku/sunnypilot'), before)

    def test_a_fork_with_its_own_commits_is_not_touched(self):
        self.commit('mine')
        self.publish('cristianku/sunnypilot')
        mine = self.master('cristianku/sunnypilot')
        self.git('reset', '-q', '--hard', 'HEAD~1')
        self.commit('theirs')
        self.publish('sunnypilot/sunnypilot')
        self.assertEqual(self.sync().returncode, 1)
        self.assertEqual(self.master('cristianku/sunnypilot'), mine)


class FakeCache:
    """A branch per key: head, parent, commits counted between two names, submodule pointers, files."""

    def __init__(self):
        self.counts = {}
        self.links = {}
        self.tree = {'nav.py': 'n1', 'speed.py': 's1', 'list.py': 'd1', 'both.py': 'merged'}
        self.nav = {'nav.py': 'n1', 'both.py': 'n2'}
        self.speed = {'speed.py': 's1', 'both.py': 's2', '.gitmodules': 'g'}
        self.master = {}

    def head(self, key):
        return 'h-' + key

    def time(self, key):
        return 1

    def parent(self, key):
        return 'base'

    def base(self, one, other):
        return 'base-' + other

    def count(self, since, until):
        return self.counts.get((since, until), 0)

    def link(self, key, path):
        return self.links.get((key, path), 'h-' + {status.NEURAL_PATH: status.NEURAL, 'opendbc_repo': status.OPENDBC_TESTING,
                                                   status.MODELS_PATH: status.MODELS}[path])

    def files(self, key):
        return self.tree

    def changes(self, since, key):
        return {status.NAV: self.nav, status.SPEED: self.speed, status.DISTILLED: {'list.py': 'd1'},
                status.SUNNY: self.master}[key]


def clean_cache():
    cache = FakeCache()
    # What Nav2Pilot adds on master is one commit.
    for key, upstream in ((status.NAV, status.SUNNY), ('cristianku/openpilot:nav-alpha', status.COMMA)):
        cache.counts[(upstream, key)] = 1
    return cache


class EvaluateTest(unittest.TestCase):
    def build_of(self, cache):
        return status.evaluate(cache)[0]

    def test_the_comma_ai_sources_are_shown_but_never_a_step(self):
        cache = clean_cache()
        cache.counts[('cristianku/openpilot:nav-alpha', status.COMMA)] = 13
        items = status.evaluate(cache)
        item = next(item for item in items if item['branch'] == 'nav-alpha' and item['repo'] == 'cristianku/openpilot')
        self.assertEqual((item['group'], item['state']), ('comma-sources', 'behind'))
        self.assertEqual(status.to_do(items, None), [])

    def test_nothing_changed_means_nothing_to_do(self):
        items = status.evaluate(clean_cache())
        self.assertEqual(self.build_of(clean_cache())['state'], 'ok')
        self.assertEqual(status.to_do(items, None), [])

    def test_a_realignment_alone_asks_for_no_build(self):
        cache = clean_cache()
        cache.time = lambda key: 100 if key == status.NAV else 1
        self.assertEqual(self.build_of(cache)['state'], 'ok')

    def test_a_file_two_branches_change_says_nothing_about_either(self):
        self.assertEqual(self.build_of(clean_cache())['reasons'], [])

    def test_new_content_in_an_injected_branch_asks_for_a_build(self):
        cache = clean_cache()
        cache.nav = {'nav.py': 'n2', 'both.py': 'n2'}
        self.assertEqual(self.build_of(cache)['reasons'], ['Nav2Pilot changed'])

    def test_a_file_master_changed_too_is_merged_in_the_build(self):
        cache = clean_cache()
        cache.tree['list.py'] = 'merged'
        cache.master = {'list.py': 'm1'}
        self.assertEqual(self.build_of(cache)['reasons'], [])

    def test_a_new_master_asks_for_a_build(self):
        cache = clean_cache()
        cache.counts[('base', status.SUNNY)] = 3
        item = self.build_of(cache)
        self.assertEqual(item['state'], 'behind')
        self.assertEqual(item['fix']['action'], 'setup-testing')

    def test_a_moved_submodule_asks_for_a_build(self):
        cache = clean_cache()
        cache.links[(status.TESTING, 'opendbc_repo')] = 'old'
        self.assertEqual(self.build_of(cache)['reasons'], ['opendbc changed'])

    def test_new_networks_are_seen_on_both_sides(self):
        cache = clean_cache()
        cache.links[(status.SPEED, status.MODELS_PATH)] = 'old'
        items = {item['id']: item for item in status.evaluate(cache)}
        self.assertEqual(items[status.MODELS]['state'], 'behind')
        self.assertIn('The speed limit networks changed', items[status.TESTING]['reasons'])

    def test_a_nav_branch_of_two_commits_is_not_fine(self):
        cache = clean_cache()
        cache.counts[(status.SUNNY, status.NAV)] = 2
        item = next(item for item in status.evaluate(cache) if item['id'] == status.NAV)
        self.assertEqual(item['fix'], {'hint': 'Ask Claude to redo it with OP-apply-nav-alpha.'})

    def test_steps_go_from_the_forks_to_the_comma(self):
        cache = clean_cache()
        cache.counts[('base', status.SUNNY)] = 1
        cache.counts[(status.DISTILLED, status.SUNNY)] = 1
        cache.counts[('cristianku/sunnypilot:master', status.SUNNY)] = 1
        steps = status.to_do(status.evaluate(cache), {'reachable': True, 'latest': False})
        self.assertEqual([step['id'] for step in steps], ['cristianku/sunnypilot:master', status.DISTILLED, status.TESTING, 'comma'])

    def test_a_comma_that_is_away_is_not_a_step(self):
        self.assertEqual(status.to_do([], {'reachable': False}), [])

    def test_stale_branches_of_other_variants_are_no_step(self):
        cache = clean_cache()
        cache.counts[('cristianku/opendbc:psa-torque-sunny', status.OPENDBC_TESTING)] = 111
        self.assertEqual(status.to_do(status.evaluate(cache), None), [])


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.jobs = jobs_module.Jobs(Path(self.dir.name))

    def wait(self, job_id):
        for _ in range(100):
            job = next(job for job in self.jobs.list() if job['id'] == job_id)
            if job['state'] != 'running':
                return job
            time.sleep(.05)
        self.fail('the job did not end')

    def test_a_job_ends_with_its_exit_code(self):
        job_id = self.jobs.start('dummy', 'Dummy', ['bash', '-c', 'echo hello; exit 3'], {}, dry=False)
        job = self.wait(job_id)
        self.assertEqual((job['state'], job['code']), ('failed', 3))
        self.assertIn('hello', self.jobs.log(job_id, 0)['text'])

    def test_one_job_at_a_time(self):
        job_id = self.jobs.start('dummy', 'Dummy', ['sleep', '30'], {}, dry=False)
        with self.assertRaises(jobs_module.JobError):
            self.jobs.start('other', 'Other', ['true'], {}, dry=False)
        self.jobs.stop(job_id)
        self.assertEqual(self.wait(job_id)['state'], 'stopped')

    def test_a_build_started_elsewhere_blocks_a_job(self):
        with mock.patch.object(jobs_module, 'outside_jobs', return_value=['send_to_car.sh']):
            with self.assertRaises(jobs_module.JobError):
                self.jobs.start('dummy', 'Dummy', ['true'], {}, dry=False)

    def test_outside_scripts_are_found_by_name(self):
        script = Path(self.dir.name) / 'send_to_car.sh'
        script.write_text('sleep 30\n')
        import subprocess
        process = subprocess.Popen(['bash', str(script)])
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        time.sleep(.1)
        self.assertIn('send_to_car.sh', jobs_module.outside_jobs())

    def test_a_job_id_cannot_leave_the_logs(self):
        with self.assertRaises(jobs_module.JobError):
            self.jobs.log('../../etc/passwd', 0)

    def test_colours_are_stripped(self):
        job_id = self.jobs.start('dummy', 'Dummy', ['printf', r'\033[32mok\033[0m'], {}, dry=False)
        self.wait(job_id)
        self.assertNotIn('\x1b', self.jobs.log(job_id, 0)['text'])


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.app = server.App(Path(self.dir.name), TOKEN, port=0, allowed=set(), proxies=set(), hosts={'ops.test'})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(self.app))
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def request(self, method, path, body=None, *, host='ops.test', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        all_headers = {'Host': host, **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body)
            all_headers.update({'Content-Type': 'application/json', 'X-Requested-With': 'ops-web'})
        connection.request(method, path, data, all_headers)
        response = connection.getresponse()
        payload = response.read()
        connection.close()
        return response, payload

    def cookie(self):
        response, _ = self.request('POST', '/api/sign-in', {'code': TOKEN})
        self.assertEqual(response.status, 200)
        return {'Cookie': response.getheader('Set-Cookie').split(';')[0]}

    def test_a_wrong_host_is_refused(self):
        self.assertEqual(self.request('GET', '/', host='evil.test')[0].status, 403)

    def test_an_address_outside_the_list_is_refused(self):
        self.app.allowed = {'192.0.2.1'}
        self.assertEqual(self.request('GET', '/')[0].status, 403)

    def test_nothing_without_signing_in(self):
        self.assertEqual(self.request('GET', '/api/state')[0].status, 401)
        self.assertEqual(self.request('POST', '/api/run', {'action': 'news'})[0].status, 401)

    def test_sign_in_opens_the_state(self):
        response, payload = self.request('GET', '/api/state', headers=self.cookie())
        self.assertEqual(response.status, 200)
        self.assertNotIn('argv', json.loads(payload)['skills'][0])
        self.assertNotIn(TOKEN, payload.decode())

    def test_a_forged_session_is_refused(self):
        forged = {'Cookie': f'{server.COOKIE}=9999999999.deadbeef'}
        self.assertEqual(self.request('GET', '/api/state', headers=forged)[0].status, 401)

    def test_a_post_needs_the_custom_header(self):
        headers = {**self.cookie(), 'Content-Length': '2'}
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_address[1], timeout=10)
        connection.request('POST', '/api/refresh', '{}', {'Host': 'ops.test', **headers})
        self.assertEqual(connection.getresponse().status, 400)
        connection.close()

    def test_proxy_headers_count_only_from_the_proxy(self):
        headers = {'X-authentik-username': 'cristian', 'X-authentik-groups': 'farm|other',
                   'X-Ops-Proxy-Secret': 'the-secret'}
        self.app.proxy_secret = 'the-secret'
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0].status, 401)
        self.app.proxies = {'127.0.0.1'}
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0].status, 200)
        headers['X-authentik-groups'] = 'other'
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0].status, 401)

    def test_the_proxy_address_alone_signs_nobody_in(self):
        self.app.proxies = {'127.0.0.1'}
        headers = {'X-authentik-username': 'cristian', 'X-authentik-groups': 'farm'}
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0].status, 401)
        self.app.proxy_secret = 'the-secret'
        headers['X-Ops-Proxy-Secret'] = 'a-guess'
        self.assertEqual(self.request('GET', '/api/state', headers=headers)[0].status, 401)

    def test_a_job_runs_only_from_the_list(self):
        response, payload = self.request('POST', '/api/run', {'action': 'nothing'}, headers=self.cookie())
        self.assertEqual(response.status, 409)
        self.assertIn('cannot run', json.loads(payload)['error'])

    def test_failed_codes_are_limited(self):
        with mock.patch.object(server.time, 'sleep'):
            for _ in range(server.FAILURES_PER_MINUTE):
                self.request('POST', '/api/sign-in', {'code': 'wrong'})
            self.assertEqual(self.request('POST', '/api/sign-in', {'code': TOKEN})[0].status, 401)


if __name__ == '__main__':
    unittest.main()
