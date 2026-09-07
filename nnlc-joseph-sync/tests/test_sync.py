# [joseph sync] - START
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).parents[1] / "scripts" / "sync_logs.py"


class SyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("sync_logs", SCRIPT)
        cls.sync = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.sync)

    def test_default_preserves_destination(self):
        self.assertFalse(self.sync.parse_args([]).truncate)

    def test_usb_export_cannot_truncate(self):
        with self.assertRaises(SystemExit):
            self.sync.parse_args(["--usb", "/Volumes/chiavetta", "--truncate"])

    def test_export_rejects_metadata_symlink(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            bundle = root / "joseph-nnlc"
            bundle.mkdir()
            outside = root / "other-file"
            outside.write_text("keep")
            (bundle / "sync_logs.py").symlink_to(outside)
            with patch.object(Path, "is_mount", return_value=True), \
                 patch.object(self.sync, "source_inventory", return_value={"route--0/rlog.zst": {"size": 1}}):
                with self.assertRaises(ValueError):
                    self.sync.export_usb(root, dry_run=True)
            self.assertEqual(outside.read_text(), "keep")

    def test_cleanup_rejects_data_mount(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp).resolve() / "data"
            data.mkdir()
            (data / "old").write_text("keep")
            with patch.object(Path, "is_mount", lambda path: path == data):
                with self.assertRaises(ValueError):
                    self.sync.clean_data(data)
            self.assertEqual((data / "old").read_text(), "keep")

    def make_bundle(self, root):
        import json
        bundle = root / "usb/joseph-nnlc"
        log = bundle / "realdata/route--0/rlog.zst"
        log.parent.mkdir(parents=True)
        log.write_bytes(b"Joseph compressed log")
        manifest = {"route--0/rlog.zst": {"size": log.stat().st_size, "sha256": self.sync.digest(log)}}
        (bundle / "manifest.json").write_text(json.dumps(manifest))
        return bundle

    def test_usb_import_offline_optional_cleanup(self):
        from unittest.mock import patch
        for truncate in (False, True):
            with self.subTest(truncate=truncate), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                bundle = self.make_bundle(root)
                data = root / "data"
                data.mkdir()
                (data / "old").write_bytes(b"cloned")
                (root / "output").mkdir()
                with patch.object(self.sync, "TARGET", data), \
                     patch.object(self.sync.socket, "gethostname", return_value=self.sync.TARGET_HOST), \
                     patch.object(self.sync.subprocess, "run", side_effect=AssertionError("Network forbidden")):
                    self.sync.import_usb(bundle.parent, truncate, False)
                self.assertEqual((data / "route--0/rlog.zst").read_bytes(), b"Joseph compressed log")
                self.assertEqual((data / "old").exists(), not truncate)
                self.assertTrue((root / "output").is_dir())
                self.assertTrue((bundle / "realdata/route--0/rlog.zst").exists())

    def test_corrupt_usb_cannot_clean_destination(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            bundle = self.make_bundle(root)
            (bundle / "realdata/route--0/rlog.zst").write_bytes(b"corrupt")
            data = root / "data"
            data.mkdir()
            (data / "old").write_text("keep")
            with patch.object(self.sync, "TARGET", data), \
                 patch.object(self.sync.socket, "gethostname", return_value=self.sync.TARGET_HOST):
                with self.assertRaises(ValueError):
                    self.sync.import_usb(bundle.parent, True, False)
            self.assertEqual((data / "old").read_text(), "keep")

    def test_usb_manifest_cannot_escape_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            outside = root / "outside"
            outside.write_bytes(b"log")
            with self.assertRaises(ValueError):
                self.sync.verify_files(root, {"../outside": {"size": 3, "sha256": self.sync.digest(outside)}})

    def test_zip_produces_training_path_without_double_segment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            src = root / "incoming" / "route--0"
            src.mkdir(parents=True)
            with zipfile.ZipFile(src / "rlog.zst.hash.zip", "w") as archive:
                archive.writestr("route--0/rlog.zst", b"training log")
            manifest = self.sync.prepare(root / "incoming", root / "ready")
            self.assertEqual((root / "ready/route--0/rlog.zst").read_bytes(), b"training log")
            self.assertEqual(set(manifest), {"route--0/rlog.zst"})

    def test_invalid_zip_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            src = root / "incoming" / "route--0"
            src.mkdir(parents=True)
            with zipfile.ZipFile(src / "rlog.zst.hash.zip", "w") as archive:
                archive.writestr("../rlog.zst", b"bad")
            with self.assertRaises(ValueError):
                self.sync.prepare(root / "incoming", root / "ready")
            self.assertFalse((root / "rlog.zst").exists())

    def test_conflicting_raw_and_zip_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            src = root / "incoming/route--0"
            src.mkdir(parents=True)
            (src / "rlog.zst").write_bytes(b"one")
            with zipfile.ZipFile(src / "rlog.zst.hash.zip", "w") as archive:
                archive.writestr("route--0/rlog.zst", b"two")
            with self.assertRaises(ValueError):
                self.sync.prepare(root / "incoming", root / "ready")

    def test_empty_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(ValueError):
                self.sync.prepare(root, root / "ready")

    def test_zip_directory_entry_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            src = root / "incoming/route--0"
            src.mkdir(parents=True)
            with zipfile.ZipFile(src / "rlog.zst.hash.zip", "w") as archive:
                archive.writestr("route--0/", b"")
                archive.writestr("route--0/rlog.zst", b"log")
            self.sync.prepare(root / "incoming", root / "ready")
            self.assertEqual((root / "ready/route--0/rlog.zst").read_bytes(), b"log")

    def test_interrupted_cleanup_keeps_marker(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            data = root / "data"
            data.mkdir()
            (data / "old").write_text("old")
            before = self.sync.snapshot(data)
            with patch.object(self.sync, "TARGET", data), \
                 patch.object(self.sync.socket, "gethostname", return_value=self.sync.TARGET_HOST), \
                 patch.object(self.sync, "clean_data", side_effect=OSError("interrupted")):
                with self.assertRaises(OSError):
                    self.sync.remote("truncate", {"snapshot": before})
                self.assertTrue(self.sync.remote("inspect", {})["cleanup_pending"])

    def test_cleanup_preserves_output_and_data_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            data = root / "data"
            data.mkdir()
            (data / "old").write_bytes(b"old log")
            (root / "output").mkdir()
            (root / "output/model.json").write_text("model")
            self.sync.clean_data(data)
            self.assertEqual(list(data.iterdir()), [])
            self.assertEqual((root / "output/model.json").read_text(), "model")

    def test_cleanup_rejects_symlink_and_wrong_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            other = root / "output"
            other.mkdir()
            (other / "model").write_text("keep")
            (root / "data").symlink_to(other, target_is_directory=True)
            for path in (root / "data", other):
                with self.assertRaises(ValueError):
                    self.sync.clean_data(path)
            self.assertTrue((other / "model").exists())


if __name__ == "__main__":
    unittest.main()
# [joseph sync] - END
