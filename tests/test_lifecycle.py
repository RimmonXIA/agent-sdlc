import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('manage_skill', ROOT / 'scripts' / 'manage_skill.py')
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        base = Path(os.environ.get('AGENT_SDLC_SCRATCH_DIR', Path.home()/'.codex'/'scratchpads'/'agent-sdlc-tests'))
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='lifecycle-', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'distribution' / 'repo-continuity'
        shutil.copytree(ROOT / 'skills' / manage.NAME, self.source)
        self.directory = self.root / 'user skills'
        self.target = self.directory / manage.NAME

    def test_install_and_repeat_preserve_unrelated_skills(self):
        unrelated = self.directory / 'other-skill' / 'SKILL.md'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('user owned')
        self.assertEqual(manage.install(self.source, self.directory)['status'], 'installed')
        stamp = (self.target / 'SKILL.md').stat().st_mtime_ns
        self.assertEqual(manage.install(self.source, self.directory)['status'], 'unchanged')
        self.assertEqual((self.target / 'SKILL.md').stat().st_mtime_ns, stamp)
        self.assertEqual(unrelated.read_text(), 'user owned')

    def test_update_from_new_distribution(self):
        manage.install(self.source, self.directory)
        updated = self.source / 'references' / 'judgment.md'
        updated.write_text(updated.read_text() + '\nNew guidance.\n')
        self.assertEqual(manage.install(self.source, self.directory)['status'], 'updated')
        self.assertEqual((self.target / 'references' / 'judgment.md').read_text(), updated.read_text())
        self.assertEqual(manage.status(self.directory)['status'], 'installed')

    def test_missing_reference_refused_before_installation(self):
        (self.source / 'references' / 'judgment.md').unlink()
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.directory)
        self.assertFalse(self.target.exists())

    def test_unowned_name_collision_is_never_overwritten(self):
        self.target.mkdir(parents=True)
        owned = self.target / 'SKILL.md'
        owned.write_text('someone else')
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.directory)
        self.assertEqual(owned.read_text(), 'someone else')

    def test_local_edits_block_update_and_uninstall(self):
        manage.install(self.source, self.directory)
        edited = self.target / 'SKILL.md'
        edited.write_text('local customization')
        for operation in (lambda: manage.install(self.source, self.directory), lambda: manage.uninstall(self.directory)):
            with self.assertRaises(manage.LifecycleError):
                operation()
        self.assertEqual(edited.read_text(), 'local customization')

    def test_extra_file_blocks_removal(self):
        manage.install(self.source, self.directory)
        personal = self.target / 'personal.md'
        personal.write_text('keep me')
        with self.assertRaises(manage.LifecycleError):
            manage.uninstall(self.directory)
        self.assertEqual(personal.read_text(), 'keep me')

    def test_uninstall_is_scoped_and_idempotent(self):
        manage.install(self.source, self.directory)
        unrelated = self.directory / 'other'
        unrelated.mkdir()
        self.assertEqual(manage.uninstall(self.directory)['status'], 'removed')
        self.assertFalse(self.target.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(manage.uninstall(self.directory)['status'], 'absent')

    def test_source_not_needed_after_install(self):
        manage.install(self.source, self.directory)
        shutil.rmtree(self.source)
        self.assertEqual(manage.status(self.directory)['status'], 'installed')
        self.assertTrue((self.target / 'references' / 'judgment.md').is_file())
        self.assertEqual(manage.uninstall(self.directory)['status'], 'removed')

    def test_symlink_source_and_target_refused(self):
        self.directory.mkdir()
        self.target.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.directory)
        self.assertTrue(self.target.is_symlink())
        self.target.unlink()
        (self.source / 'linked.md').symlink_to(self.source / 'SKILL.md')
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.directory)

    def test_overlapping_distribution_and_installation_refused(self):
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.source.parent)
        self.assertTrue((self.source / 'SKILL.md').exists())

    def test_active_operation_refused_without_removing_lock(self):
        self.directory.mkdir()
        lock = self.directory / f'.{manage.NAME}.lock'
        lock.mkdir()
        with self.assertRaises(manage.LifecycleError):
            manage.install(self.source, self.directory)
        self.assertTrue(lock.is_dir())
        self.assertFalse(self.target.exists())

    def test_failed_update_restores_previous_installation(self):
        manage.install(self.source, self.directory)
        previous = (self.target / 'SKILL.md').read_bytes()
        path = self.source / 'SKILL.md'
        path.write_text(path.read_text() + '\nUpdated.\n')
        replace = os.replace
        def fail_activation(src, dst):
            if Path(src).name == 'new':
                raise OSError('injected activation failure')
            return replace(src, dst)
        with mock.patch.object(manage.os, 'replace', side_effect=fail_activation):
            with self.assertRaises(OSError):
                manage.install(self.source, self.directory)
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), previous)
        self.assertEqual(manage.status(self.directory)['status'], 'installed')

    def test_failed_restore_keeps_backup_for_recovery(self):
        manage.install(self.source, self.directory)
        previous = (self.target / 'SKILL.md').read_bytes()
        path = self.source / 'SKILL.md'
        path.write_text(path.read_text() + '\nUpdated.\n')
        replace = os.replace
        def fail_activation_and_restore(src, dst):
            if Path(src).name in ('new', 'old'):
                raise OSError('injected filesystem failure')
            return replace(src, dst)
        with mock.patch.object(manage.os, 'replace', side_effect=fail_activation_and_restore):
            with self.assertRaises(manage.LifecycleError):
                manage.install(self.source, self.directory)
        backups = list(self.directory.parent.glob('.repo-continuity-transaction-*/old/SKILL.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), previous)

    def test_portable_bundle_installs_after_relocation(self):
        archive = self.root / 'release.zip'
        manage.bundle(archive)
        one = archive.read_bytes()
        manage.bundle(archive)
        self.assertEqual(one, archive.read_bytes())
        extracted = self.root / 'different machine'
        with zipfile.ZipFile(archive) as package:
            self.assertFalse(any('/Users/' in name or name.startswith('/') for name in package.namelist()))
            package.extractall(extracted)
        result = subprocess.run([sys.executable, str(extracted/'scripts'/'manage_skill.py'), 'install', '--skills-dir', str(self.directory)], cwd=self.root, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'installed')
        self.assertEqual(manage.status(self.directory)['status'], 'installed')

    def test_cli_absent_status_does_not_create_directory(self):
        result = subprocess.run([sys.executable, str(ROOT/'scripts'/'manage_skill.py'), 'status', '--skills-dir', str(self.directory)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'absent')
        self.assertFalse(self.directory.exists())


if __name__ == '__main__':
    unittest.main()
