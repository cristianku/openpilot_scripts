#!/usr/bin/env python3
"""Exercise promotion against a local Git remote, without openpilot setup."""

# [merge only] - START
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SKILL_ROOT = Path(os.environ.get('MERGE_SKILL_ROOT', Path(__file__).resolve().parents[1]))


class MergeOnlyTest(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory()
    self.addCleanup(self.tmp.cleanup)
    self.root = Path(self.tmp.name)
    self.remote = self.root / 'opendbc.git'
    self.seed = self.root / 'seed'
    self.env = dict(os.environ, GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid',
                    GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid')
    self.git('init', '--bare', str(self.remote))
    self.git('init', str(self.seed))
    self.git('-C', str(self.seed), 'checkout', '-b', 'psa-torque')
    (self.seed / 'port.txt').write_text('stable\n')
    self.git('-C', str(self.seed), 'add', '.')
    self.git('-C', str(self.seed), 'commit', '-m', 'stable')
    self.stable = self.git('-C', str(self.seed), 'rev-parse', 'HEAD')
    self.git('-C', str(self.seed), 'checkout', '-b', 'psa-torque-testing')
    (self.seed / 'testing.txt').write_text('PSA changes\n')
    self.git('-C', str(self.seed), 'add', '.')
    self.git('-C', str(self.seed), 'commit', '-m', 'testing')
    self.testing = self.git('-C', str(self.seed), 'rev-parse', 'HEAD')
    self.git('-C', str(self.seed), 'remote', 'add', 'origin', str(self.remote))
    self.git('-C', str(self.seed), 'push', 'origin', 'psa-torque', 'psa-torque-testing')
    self.setup_marker = self.root / 'setup-called'
    self.setup = self.root / 'forbidden-setup.sh'
    self.setup.write_text('#!/bin/bash\ntouch "${SETUP_MARKER}"\nexit 99\n')

  def git(self, *args):
    return subprocess.run(['git', *args], env=self.env, check=True,
                          capture_output=True, text=True).stdout.strip()

  def run_merge(self, test_command='true'):
    env = dict(self.env, OPENDBC_REPO=str(self.remote), WORKSPACE_ROOT=str(self.root),
               SETUP_SCRIPT=str(self.setup), SETUP_MARKER=str(self.setup_marker),
               MERGE_TEST_COMMAND=test_command, SKIP_TESTS='false')
    return subprocess.run(['bash', str(SKILL_ROOT / 'scripts/merge_psa_torque.sh')],
                          env=env, capture_output=True, text=True)

  def stable_sha(self):
    return self.git('--git-dir', str(self.remote), 'rev-parse', 'psa-torque')

  def test_promotion_pushes_merge_without_running_setup(self):
    result = self.run_merge()
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    promoted = self.stable_sha()
    parents = self.git('--git-dir', str(self.remote), 'show', '-s', '--format=%P', promoted)
    self.assertEqual(parents.split(), [self.stable, self.testing])
    self.assertIn(promoted, result.stdout)
    self.assertFalse(self.setup_marker.exists())
    self.assertEqual(self.git('--git-dir', str(self.remote), 'rev-parse', 'psa-torque-testing'), self.testing)

  def test_already_merged_returns_without_setup(self):
    self.git('--git-dir', str(self.remote), 'update-ref', 'refs/heads/psa-torque', self.testing)
    result = self.run_merge()
    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    self.assertEqual(self.stable_sha(), self.testing)
    self.assertFalse(self.setup_marker.exists())

  def test_failed_validation_does_not_push_or_run_setup(self):
    result = self.run_merge('exit 17')
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(self.stable_sha(), self.stable)
    self.assertFalse(self.setup_marker.exists())


if __name__ == '__main__':
  unittest.main()
# [merge only] - END
