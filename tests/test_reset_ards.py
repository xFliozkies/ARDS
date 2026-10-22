import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"scripts"),str(ROOT/"website")]
import memory
import server
import reset_ards


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace=Path(self.tmp.name)/"ards-fixture"
        for p in ("scripts/memory.py","website/server.py"):
            target=self.workspace/p
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text("# Marker file for isolated reset test\n")
        (self.workspace/"data").mkdir()
        (self.workspace/"audit").mkdir()
        (self.workspace/"data"/"authoring").mkdir()
        (self.workspace/"data"/"authoring"/"test-case.json").write_text('{"original":true}')
        with memory.connect(self.workspace/"data/ards.db") as db:
            db.execute("INSERT INTO challenges(external_id,session_type,status,source,created_at) "
                       "VALUES ('TEST-1','RACG','selected','synthetic','2020-01-01')")
            db.commit()
        server.initialize_site(self.workspace/"data/ards-studio.db")

    def test_preview_makes_no_changes(self):
        result=reset_ards.reset(self.workspace,confirm=False)
        self.assertEqual(result["mode"],"preview")
        self.assertEqual(result["counts"]["challenges"],1)
        with sqlite3.connect(self.workspace/"data/ards.db") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],1)
        self.assertTrue((self.workspace/"data/authoring/test-case.json").exists())

    def test_confirmed_reset_preserves_archive_and_empty_schemas(self):
        result=reset_ards.reset(self.workspace,confirm=True)
        self.assertEqual(result["mode"],"reset")
        self.assertGreater(result["verified_backup_files"],0)
        archive=Path(result["archive"])
        self.assertEqual((archive/"data/authoring/test-case.json").read_text(),'{"original":true}')
        self.assertTrue((archive/"MANIFEST.json").exists())
        with sqlite3.connect(self.workspace/"data/ards.db") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],0)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        with sqlite3.connect(self.workspace/"data/ards-studio.db") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ppc_drafts").fetchone()[0],0)
        self.assertEqual(list((self.workspace/"data/authoring").glob("*")),[])

    def test_explicit_no_backup_discards_active_state_and_preserves_code(self):
        old_archive=Path(self.tmp.name)/"ards-fixture-reset-backups"
        old_archive.mkdir()
        (old_archive/"older-backup.txt").write_text("older",encoding="utf-8")
        validation=self.workspace/"data/validation/old-artefacts"
        validation.mkdir(parents=True)
        (validation/"case.json").write_text("old",encoding="utf-8")
        result=reset_ards.reset(self.workspace,confirm=True,no_backup=True)
        self.assertEqual(result["mode"],"reset")
        self.assertIs(result["backup_created"],False)
        self.assertEqual(result["former_counts"]["challenges"],1)
        self.assertEqual(list(old_archive.iterdir()),[old_archive/"older-backup.txt"])
        self.assertEqual((old_archive/"older-backup.txt").read_text(),"older")
        self.assertFalse((validation/"case.json").exists())
        self.assertEqual(list((self.workspace/"data/authoring").iterdir()),[])
        for source in ("scripts/memory.py","website/server.py"):
            self.assertTrue((self.workspace/source).is_file())
        with sqlite3.connect(self.workspace/"data/ards.db") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM challenges").fetchone()[0],0)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
        with sqlite3.connect(self.workspace/"data/ards-studio.db") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ppc_drafts").fetchone()[0],0)
        note=(self.workspace/"data/README.md").read_text(encoding="utf-8")
        self.assertIn("no new backup",note)
        self.assertTrue(note.startswith("# Fresh ARDS learning state"+chr(10)*2+"Reset on"))

    def test_symlink_reset_scope_is_refused(self):
        linked=self.workspace/"audit/link"
        linked.symlink_to(self.workspace/"data/ards.db")
        with self.assertRaisesRegex(ValueError,"symlink"):
            reset_ards.reset(self.workspace,confirm=True)
        self.assertEqual(list(Path(self.tmp.name).glob("*reset-backups")),[])


if __name__=="__main__":
    unittest.main()
