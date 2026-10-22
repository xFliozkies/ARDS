"""Regressions for legacy and new CodeChef-style public problem statements."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'website'))
import statement_format as fmt
from validate_display import validate_package


class StatementFormatTests(unittest.TestCase):
    def test_lantern_markdown_sections_and_three_fenced_examples(self):
        source="""# RACG-0003 — Lanterns
Some **important** words, and $X_i$.
## Input
- First line: $N$ and $R$.
## Constraints
- $1 \\le N \\le 200000$
- Nonnegative real-valued lantern locations.
## Output
Return the **minimum** number.
## Examples
**Example 1**
Input:
""" + chr(96)*3 + """text
6 2
1 2 4 7 8 12
""" + chr(96)*3 + """
Output:
""" + chr(96)*3 + """text
3
""" + chr(96)*3 + """

**Example 2**
Input:
""" + chr(96)*3 + """text
5 0
5 1 1 7 5
""" + chr(96)*3 + """
Output:
""" + chr(96)*3 + """text
3
""" + chr(96)*3 + """

**Example 3**
Input:
""" + chr(96)*3 + """text
5 3
0 3 6 9 12
""" + chr(96)*3 + """
Output:
""" + chr(96)*3 + """text
2
""" + chr(96)*3 + """
## Your task
State the correctness proof.
"""
        view=fmt.format_statement(source)
        self.assertEqual(len(view['samples']),3)
        self.assertEqual(view['samples'][0]['input'],"6 2\n1 2 4 7 8 12")
        self.assertEqual(view['samples'][-1]['output'],'2')
        self.assertEqual(len(view['constraints']),2)
        self.assertIn('**minimum**',view['output_format'])
        self.assertNotIn('## Input',view['description'])
        self.assertNotIn(chr(96)*3,view['samples'][1]['input'])
        self.assertNotIn('notes',view)

    def test_codex_inline_legacy_constraints_not_split_inside_range(self):
        source=("Count distinct markers. Constraints: n<=2000, "
                "coordinates in [-10^9,10^9].\n\nExample input:\n"
                '{"points":[[0,0],[1,1]]}\n\nExample output:\n2\n\n'
                "Give an algorithm, justify correctness.")
        view=fmt.format_statement(source)
        self.assertEqual(len(view['constraints']),2)
        self.assertEqual(view['constraints'][1],'coordinates in [-10^9,10^9]')
        self.assertEqual(view['samples'][0]['output'],'2')
        self.assertNotIn('Example input',view['description'])

    def test_structured_public_specification_has_strict_types_and_excludes_private(self):
        data={
            'description':'Find $\\sum_{i=1}^{N} A_i$.',
            'input_format':'- The first line contains $N$.',
            'output_format':'Print the sum.',
            'constraints':['$1 \\le N \\le 10^5$'],
            'samples':[{'input':'3\n1 2 3','output':'6','explanation':'$1+2+3=6$'}]
        }
        package={'statement_display':data,
                 'teacher_ppc':{'procedure':'SECRET ALGORITHM','correctness':'SECRET PROOF'}}
        view=fmt.format_statement('Ignored legacy text',package)
        self.assertEqual(view['description'],data['description'])
        self.assertNotIn('SECRET',json.dumps(view))
        self.assertEqual(view['samples'][0],{'input':'3\n1 2 3','output':'6'})
        self.assertNotIn('explanation',json.dumps(view))
        self.assertEqual(view['format'],'ards-codechef-v1')
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'package.json'
            file.write_text(json.dumps(package))
            with self.assertRaisesRegex(ValueError,'without explanations'):
                validate_package(file)
            safe={'statement_display':{**data,'samples':[{'input':'3\n1 2 3','output':'6'}]}}
            file.write_text(json.dumps(safe))
            checked=validate_package(file)
            self.assertTrue(checked['valid'])
            self.assertFalse(checked['mathematical_correctness_checked'])

    def test_archived_explanations_and_notes_never_enter_public_format(self):
        historical={
            'description':'Compute the requested value from the input.',
            'input_format':'Read a single integer N.',
            'output_format':'Print the computed integer.',
            'constraints':['1 <= N <= 100'],
            'samples':[{'input':'3','output':'3',
                        'explanation':'Hidden sample explanation MUST NOT reach learners'}],
            'notes':'Hidden note MUST NOT reach learners'
        }
        shown=fmt.format_statement('Ignored',{'statement_display':historical})
        public=fmt.public_markdown(shown)
        self.assertNotIn('notes',shown)
        self.assertNotIn('explanation',shown['samples'][0])
        self.assertNotIn('Hidden note',json.dumps(shown)+public)
        self.assertNotIn('Hidden sample explanation',json.dumps(shown)+public)
        self.assertIn('## Input Format',public)
        self.assertIn('## Sample 1',public)
        self.assertIn('3',public)

    def test_new_authoring_rejects_explanations_and_notes(self):
        base={
            'description':'Count the values.',
            'input_format':'Read N.',
            'output_format':'Print N.',
            'constraints':['1 <= N <= 10'],
            'samples':[{'input':'1','output':'1'}]
        }
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'new.json'
            for invalid in [
                {**base,'notes':''},
                {**base,'notes':'Zero-based indexing'},
                {**base,'samples':[{'input':'1','output':'1','explanation':''}]},
                {**base,'samples':[{'input':'1','output':'1','explanation':'Obvious'}]}
            ]:
                p.write_text(json.dumps({'statement_display':invalid}))
                with self.assertRaisesRegex(ValueError,'Note section|without explanations'):
                    validate_package(p)
            p.write_text(json.dumps({'statement_display':base}))
            self.assertTrue(validate_package(p)['valid'])

    def test_historical_typed_json_sample_payloads(self):
        view=fmt.format_statement(
            'Given distinct integer coordinate points, return their count.',
            {'samples':[{'input':{'points':[[0,0],[1,1]]},'output':2}]}
        )
        self.assertEqual(view['samples'][0]['input'],'{"points":[[0,0],[1,1]]}')
        self.assertEqual(view['samples'][0]['output'],'2')

    def test_reject_unknown_fields_and_empty_samples(self):
        base={'description':'Statement','samples':[{'input':'1','output':'2'}]}
        for invalid in [
            {**base,'private_solution':'do X'},
            {**base,'samples':[{'input':'','output':'2'}]},
            {**base,'samples':[{'input':'1','output':'2','teacher_ppc':'spoiler'}]},
            {'description':' '},
            {'description':'text','constraints':['']}
        ]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):fmt.validate(invalid)

    def test_no_guessing_absent_io(self):
        view=fmt.format_statement('Compute a valid answer.')
        self.assertEqual(view['input_format'],'')
        self.assertEqual(view['output_format'],'')
        self.assertEqual(view['constraints'],[])
        self.assertEqual(view['samples'],[])


if __name__=='__main__':
    unittest.main()
