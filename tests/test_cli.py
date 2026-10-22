"""Full CLI integration against a disposable DB, never real learner records."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MEMORY=ROOT/"scripts/memory.py"
RACG=ROOT/"scripts/racg.py"


class CLITests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.db=Path(self.t.name)/"memory.db"
        self.state=Path(self.t.name)/"state.json"

    def run_python(self, script, *args, stdin=None, check=True):
        cmd=[sys.executable,str(script),*map(str,args)]
        result=subprocess.run(cmd,input=stdin,stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE,encoding="utf8",timeout=15)
        if check and result.returncode:
            self.fail(f"exit {result.returncode}: {cmd}\n{result.stderr}")
        return result

    def test_cli_full_cycle_and_copy_integrity(self):
        created=json.loads(self.run_python(MEMORY,"--db",self.db,"--legacy-root",ROOT/"tests"/"fixtures"/"legacy","init").stdout)
        self.assertEqual(created["imported"],["B1","RACG-0002"])
        self.assertEqual(json.loads(self.run_python(RACG,"--db",self.db,"--state",self.state,
                                                   "--preview").stdout)["preview_only"],True)
        # A preview must not leave a selected challenge in the durable ledger.
        self.assertEqual(json.loads(self.run_python(MEMORY,"--db",self.db,"status").stdout)
                         ["total_challenges"],2)

        drawn=json.loads(self.run_python(RACG,"--db",self.db,"--state",self.state).stdout)
        self.assertEqual(drawn["external_id"],"RACG-0003")
        self.assertIn("P",drawn["rolls"])
        self.assertEqual(drawn["story"],drawn["rolls"]["P"]<=70)

        pending=self.run_python(RACG,"--db",self.db,"--state",self.state,check=False)
        self.assertNotEqual(pending.returncode,0)
        self.assertIn("Unpresented",pending.stderr)

        presented=json.loads(self.run_python(
            MEMORY,"--db",self.db,"present",drawn["external_id"],
            "--title","Test Puzzle","--stdin",stdin="Find the smallest missing symbol.\n").stdout)
        self.assertEqual(presented["status"],"presented")
        attempt=json.loads(self.run_python(
            MEMORY,"--db",self.db,"attempt",drawn["external_id"],
            "--stdin","--hint-level","0","--independent","yes",
            "--confidence","70",stdin="My solution is to inspect the set of symbols.\n").stdout)

        with self.assertRaises(AssertionError):
            # first attempt must stay immutable
            bad=self.run_python(MEMORY,"--db",self.db,"attempt",drawn["external_id"],
               "--stdin","--hint-level","0",stdin="Try to overwrite",check=False)
            assert bad.returncode==0

        assessment=json.loads(self.run_python(
            MEMORY,"--db",self.db,"assess",attempt["attempt_id"],
            "--reviewer","integration-test","--correct","unknown",
            "--optimality","unknown","--notes","Not graded in smoke test.").stdout)
        self.assertGreater(assessment["assessment_id"],0)

        found=json.loads(self.run_python(MEMORY,"--db",self.db,"search","missing symbol").stdout)
        self.assertTrue(any(x["external_id"]=="RACG-0003" for x in found))

        backup=Path(self.t.name)/"backup.db"
        out=json.loads(self.run_python(MEMORY,"--db",self.db,"backup","--dest",backup).stdout)
        self.assertTrue(Path(out["backup"]).is_file())
        diagnostic=json.loads(self.run_python(MEMORY,"--db",self.db,"doctor").stdout)
        self.assertEqual(diagnostic["integrity_check"],"ok")
        self.assertEqual(diagnostic["fts_consistency"],"ok")


if __name__=="__main__":
    unittest.main()
