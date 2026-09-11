# [upstream tests] - START
"""Exercise the wrapper with real, offline Git repositories, never the user's fork."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/merge_upstream.sh"


class MergeUpstreamTest(unittest.TestCase):
  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory(prefix="op-merge-test-")
    self.addCleanup(self.tmp.cleanup)
    self.root = Path(self.tmp.name)
    self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                    GIT_AUTHOR_NAME="Test", GIT_AUTHOR_EMAIL="test@example.invalid",
                    GIT_COMMITTER_NAME="Test", GIT_COMMITTER_EMAIL="test@example.invalid",
                    GIT_TERMINAL_PROMPT="0", GIT_ALLOW_PROTOCOL="file")
    self.source = self.root / "source"
    self.git(self.root, "init", "-b", "master", str(self.source))
    self.commit(self.source, "shared.txt", "base\n")
    self.base = self.git(self.source, "rev-parse", "HEAD")
    self.repo = self.root / "working checkout"
    self.git(self.root, "clone", str(self.source), str(self.repo))
    self.git(self.repo, "checkout", "-b", "psa-torque-sunny-testing")
    self.fork = self.root / "fork.git"
    self.git(self.root, "clone", "--bare", str(self.repo), str(self.fork))
    self.configure()

  def git(self, repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], env=self.env,
                                   stderr=subprocess.PIPE, text=True).strip()

  def configure(self):
    self.git(self.repo, "remote", "set-url", "origin", "https://github.com/cristianku/opendbc.git")
    for url, path in [("https://github.com/cristianku/opendbc.git", self.fork),
                      ("https://github.com/sunnypilot/opendbc.git", self.source),
                      ("https://github.com/commaai/opendbc.git", self.source)]:
      self.git(self.repo, "config", "--add", f"url.{path.as_uri()}.insteadOf", url)

  def commit(self, repo, file, content):
    (repo / file).write_text(content)
    self.git(repo, "add", "--", file)
    self.git(repo, "commit", "-m", file)

  def run_wrapper(self, variant="sunny"):
    return subprocess.run(["bash", str(SCRIPT), variant],
                          env=dict(self.env, OPENDBC_DIR=str(self.repo)),
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

  def backups(self):
    return self.git(self.repo, "for-each-ref", "--format=%(objectname)", "refs/heads/backup/").splitlines()

  def assert_pending_merge(self, old_head):
    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), old_head)
    self.assertEqual(self.git(self.repo, "rev-parse", "MERGE_HEAD"),
                     self.git(self.source, "rev-parse", "HEAD"))
    self.assertEqual(self.backups(), [old_head])
    self.assertEqual(self.git(self.fork, "rev-parse", "psa-torque-sunny-testing"), self.base)

  def test_diverged_merge_preserves_custom_changes_and_stops_before_commit(self):
    self.commit(self.repo, "psa.txt", "custom port\n")
    old = self.git(self.repo, "rev-parse", "HEAD")
    self.commit(self.source, "upstream.txt", "new upstream\n")
    result = self.run_wrapper()
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assert_pending_merge(old)
    self.assertEqual((self.repo / "psa.txt").read_text(), "custom port\n")
    self.assertEqual((self.repo / "upstream.txt").read_text(), "new upstream\n")

  def test_fast_forward_also_stops_before_commit(self):
    self.commit(self.source, "upstream.txt", "new upstream\n")
    result = self.run_wrapper()
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assert_pending_merge(self.base)

  def test_conflict_is_left_for_review_and_can_be_aborted(self):
    self.commit(self.repo, "shared.txt", "custom\n")
    old = self.git(self.repo, "rev-parse", "HEAD")
    self.commit(self.source, "shared.txt", "upstream\n")
    result = self.run_wrapper()
    self.assertEqual(result.returncode, 2, result.stdout)
    self.assert_pending_merge(old)
    self.assertEqual(self.git(self.repo, "diff", "--name-only", "--diff-filter=U"), "shared.txt")
    self.git(self.repo, "merge", "--abort")
    self.assertEqual((self.repo / "shared.txt").read_text(), "custom\n")
    self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")

  def test_wrong_variant_refuses_before_fetch(self):
    result = self.run_wrapper("comma")
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("psa-torque-testing", result.stdout)
    self.assertFalse((self.repo / ".git/FETCH_HEAD").exists())
    self.assertEqual(self.backups(), [])

  def test_dirty_worktree_is_preserved(self):
    (self.repo / "shared.txt").write_text("unfinished\n")
    result = self.run_wrapper()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("dirty", result.stdout.lower())
    self.assertEqual((self.repo / "shared.txt").read_text(), "unfinished\n")
    self.assertFalse((self.repo / ".git/FETCH_HEAD").exists())

  def test_untracked_file_is_preserved(self):
    (self.repo / "notes.txt").write_text("personal\n")
    result = self.run_wrapper()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("dirty", result.stdout.lower())
    self.assertEqual((self.repo / "notes.txt").read_text(), "personal\n")

  def test_already_merged_leaves_no_backup_or_pending_merge(self):
    result = self.run_wrapper()
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")
    self.assertFalse((self.repo / ".git/MERGE_HEAD").exists())
    self.assertEqual(self.backups(), [])

  def test_shallow_fork_history_is_completed_before_merge(self):
    self.commit(self.repo, "psa.txt", "custom port\n")
    self.git(self.repo, "push", "origin", "psa-torque-sunny-testing")
    self.repo = self.root / "shallow"
    self.git(self.root, "clone", "--depth=1", "--branch", "psa-torque-sunny-testing",
             self.fork.as_uri(), str(self.repo))
    self.configure()
    self.assertEqual(self.git(self.repo, "rev-parse", "--is-shallow-repository"), "true")
    old = self.git(self.repo, "rev-parse", "HEAD")
    self.commit(self.source, "upstream.txt", "upstream\n")
    result = self.run_wrapper()
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertEqual(self.git(self.repo, "rev-parse", "--is-shallow-repository"), "false")
    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), old)
    self.assertEqual(self.git(self.repo, "rev-parse", "MERGE_HEAD"),
                     self.git(self.source, "rev-parse", "HEAD"))
    self.assertEqual(self.git(self.fork, "rev-parse", "psa-torque-sunny-testing"), old)

  def test_unrelated_history_is_not_forced(self):
    self.git(self.source, "checkout", "--orphan", "unrelated")
    self.commit(self.source, "shared.txt", "unrelated\n")
    self.git(self.source, "branch", "-M", "master")
    result = self.run_wrapper()
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("common ancestor", result.stdout.lower())
    self.assertFalse((self.repo / ".git/MERGE_HEAD").exists())
    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), self.base)

  def test_comma_uses_its_testing_branch(self):
    self.git(self.repo, "checkout", "-b", "psa-torque-testing")
    self.commit(self.source, "upstream.txt", "comma\n")
    result = self.run_wrapper("comma")
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertIn("https://github.com/commaai/opendbc.git", result.stdout)
    self.assert_pending_merge(self.base)

  def test_existing_operation_is_preserved(self):
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "sequencer"):
      with self.subTest(marker=marker):
        path = self.repo / ".git" / marker
        if marker in ("rebase-merge", "sequencer"):
          path.mkdir()
        else:
          path.write_text(self.base + "\n")
        try:
          result = self.run_wrapper()
          self.assertNotEqual(result.returncode, 0)
          self.assertIn("progress", result.stdout.lower())
          self.assertTrue(path.exists())
          self.assertFalse((self.repo / ".git/FETCH_HEAD").exists())
        finally:
          path.rmdir() if path.is_dir() else path.unlink()

  def test_fetch_failure_does_not_start_merge(self):
    self.git(self.source, "branch", "-m", "no-master")
    result = self.run_wrapper()
    self.assertNotEqual(result.returncode, 0)
    self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), self.base)
    self.assertEqual(self.git(self.repo, "status", "--porcelain"), "")
    self.assertEqual(self.backups(), [])


if __name__ == "__main__":
  unittest.main()
# [upstream tests] - END
