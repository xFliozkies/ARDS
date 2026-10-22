"""Regression counterexamples from the independent audit; no live data access."""
import copy
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import strict_json,ppc3,ppc2,ards2,memory,ppc3_lean,ppc3_stress


def variable(name): return {'op':'var','name':name}
def chain(n):
    return {'kind':'finite_transition_system','input_domain':[0], 'cases':[{
        'input_id':0,'initial':['s0'],'allowed_outputs':[0],
        'states':{'s'+str(i):{'halt':i==n-1,'next':[] if i==n-1 else ['s'+str(i+1)],'output':0} for i in range(n)}}]}
def package(i=0): return ppc2.make_problem(i,random.Random(20261020+i))


class JSONBoundaryTests(unittest.TestCase):
    def test_duplicate_members_and_nonfinite_numbers_fail_closed(self):
        for text in ('{"x":0,"x":1}','{"outer":{"x":0,"x":1}}','NaN','Infinity','-Infinity','1e999'):
            with self.subTest(text=text),self.assertRaises(ValueError): strict_json.loads(text)
        bad=chain(1);bad['cases'][0]['allowed_outputs']=[float('nan')]
        bad['cases'][0]['states']['s0']['output']=float('nan')
        self.assertEqual(ppc3.check_machine(bad)['status'],'rejected')

    def test_duplicate_state_definition_is_rejected_by_actual_cli(self):
        raw='{"kind":"finite_transition_system","input_domain":[0],"cases":[{"input_id":0,"initial":["s0"],"allowed_outputs":[0],"states":{"s0":{"halt":false,"next":["s0"],"output":0},"s0":{"halt":true,"next":[],"output":0}}}]}'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'model.json';path.write_text(raw)
            r=subprocess.run([sys.executable,str(ROOT/'scripts/ppc3.py'),'finite-machine','--file',str(path)],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,1)
        self.assertEqual(json.loads(r.stdout)['status'],'rejected')
        self.assertIn('duplicate',json.loads(r.stdout)['reason'])

    def test_node_byte_depth_budgets_and_cyclic_objects(self):
        for value,limits in (([1]*20,{'max_nodes':10}),('x'*100,{'max_bytes':30}),([[[1]]],{'max_depth':1})):
            with self.subTest(limits=limits),self.assertRaises(strict_json.ResourceLimitError):strict_json.validate(value,**limits)
        cyclic=[];cyclic.append(cyclic)
        with self.assertRaisesRegex(ValueError,'cyclic'):strict_json.validate(cyclic)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'large';p.write_bytes(b'x'*100)
            with self.assertRaises(strict_json.ResourceLimitError):strict_json.load(p,max_bytes=20)

    def test_original_valid_canonical_encoding_is_preserved(self):
        value={'b':True,'a':[0,1,'λ',None]}
        self.assertEqual(strict_json.canonical(value),json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')))


class RestrictedKernelHardeningTests(unittest.TestCase):
    def test_deep_iff_identity_finishes_in_bounded_subprocess(self):
        form=variable('A')
        for _ in range(90):form={'op':'iff','left':form,'right':{'op':'top'}}
        cert={'kind':'propositional','assumptions':{'a':form},'conclusion':copy.deepcopy(form),'proof':{'rule':'hyp','name':'a'}}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'proof.json';p.write_text(json.dumps(cert))
            r=subprocess.run([sys.executable,str(ROOT/'scripts/ppc3.py'),'proposition','--file',str(p)],capture_output=True,text=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['status'],'fragment_machine_checked')

    def test_full_advertised_chain_size_and_long_nondeterministic_cycle(self):
        c=chain(10000)
        r=ppc3.check_machine(c)
        self.assertEqual(r['status'],'finite_domain_machine_checked',r)
        self.assertEqual(r['reachable_states'],10000)
        c['cases'][0]['states']['s9999'].update(halt=False,next=['s9998'])
        self.assertEqual(ppc3.check_machine(c)['status'],'rejected')

    def test_resource_limits_are_distinct_from_invalid_proofs(self):
        form=variable('A')
        for _ in range(110):form={'op':'not','arg':form}
        cert={'kind':'propositional','assumptions':{'a':form},'conclusion':form,'proof':{'rule':'hyp','name':'a'}}
        self.assertEqual(ppc3.check_proposition(cert)['status'],'resource_limit')
        cert={'kind':'propositional','assumptions':{},'conclusion':variable('A'),'proof':{'rule':'axiom'}}
        self.assertEqual(ppc3.check_proposition(cert)['status'],'rejected')

    def test_secondary_semantic_audit_has_a_work_budget(self):
        form=variable('A0')
        for _ in range(90):form={'op':'iff','left':form,'right':{'op':'top'}}
        c={'kind':'propositional','assumptions':{**{'h':form,'extra':copy.deepcopy(form)},**{f'a{i}':variable(f'A{i}') for i in range(12)}},'conclusion':copy.deepcopy(form),'proof':{'rule':'hyp','name':'h'}}
        r=ppc3.check_proposition(c)
        self.assertEqual(r['status'],'fragment_machine_checked',r)
        self.assertFalse(r['truth_table']['audited'])
        self.assertIn('work budget',r['truth_table']['reason'])


class PackageHardeningTests(unittest.TestCase):
    def test_range_sum_enforces_integer_types_and_answer_shape(self):
        p=package(4);p['model']['parameters'].update(max_len=1,alphabet=[1])
        p['ppc']['model_hash']=ppc2.sha256(p['model']);p=ards2.prepare_reference(p)
        for array,output in (([True],[1]),([1.0],[1]),([1],[True]),([1],[1.0]),([1],[]),([1],'1')):
            q=copy.deepcopy(p);q['samples']=[{'input':json.dumps({'array':array,'queries':[[0,0]]}),'output':json.dumps(output)}]
            with self.subTest(array=array,output=output):self.assertEqual(ards2.verify_body(q)['outcome'],'failed')
        p['samples']=[{'input':'{"array":[1],"queries":[[0,0]]}','output':'[1]'}]
        self.assertEqual(ards2.verify_body(p)['outcome'],'test_verified')

    def test_malformed_techniques_and_patterns_return_rejections(self):
        for technique in ([],{},None,False):
            p=package();p['ppc']['technique']=technique
            self.assertEqual(ppc2.check_certificate(p)['status'],'rejected')
        p=package();p['patterns']=[{}]
        self.assertEqual(ards2.verify_body(p)['outcome'],'failed')

    def test_deep_acyclic_obligation_dependencies_do_not_use_python_recursion(self):
        p=package()
        for i in range(1600):p['ppc']['obligations'].append({'id':f'aux{i}','claim':'auxiliary claim','argument':'unverified prose','depends_on':[] if i==0 else [f'aux{i-1}']})
        self.assertEqual(ppc2.check_certificate(p)['status'],'structure_checked')
        p['ppc']['obligations'][-1600]['depends_on']=['aux1599']
        self.assertEqual(ppc2.check_certificate(p)['status'],'rejected')

    def test_fragment_correspondence_checks_the_exact_finite_specification(self):
        p=package();params=p['model']['parameters'];c=chain(1)
        p['ppc3']={'model_hash':ppc3.fingerprint(p['model']),'scope':'explicit_finite_model','certificate':c}
        self.assertEqual(ards2.verify_body(p)['outcome'],'failed')
        domain=list(range(params['min_n'],params['max_n']+1));c['input_domain']=domain;c['cases']=[]
        for n in domain:
            value=n*(params['discounted'] if n>=params['threshold'] else params['full'])
            c['cases'].append({'input_id':n,'initial':['s'],'allowed_outputs':[value],'states':{'s':{'halt':True,'next':[],'output':value}}})
        r=ards2.verify_body(p)
        self.assertEqual(r['outcome'],'test_verified',r)
        self.assertEqual(r['fragment_evidence']['correspondence'],'finite_specification_relation_checked')
        self.assertEqual(r['fragment_evidence']['implementation_refinement'],'unproved')
        c['cases'][0]['allowed_outputs']=[-1];c['cases'][0]['states']['s']['output']=-1
        self.assertEqual(ppc3.check_machine(c)['status'],'finite_domain_machine_checked')
        self.assertEqual(ards2.verify_body(p)['outcome'],'failed')
        p['ppc3']['scope']='auxiliary_finite_model'
        r=ards2.verify_body(p)
        self.assertEqual(r['outcome'],'test_verified')
        self.assertEqual(r['fragment_evidence']['correspondence'],'auxiliary_only')

    def test_wrong_authored_solution_and_forged_receipt_cannot_be_released(self):
        p=package();p['reference_solution']='Return WRONG for all inputs.'
        # A caller can calculate a hash. It still cannot label arbitrary prose a registered algorithm.
        p['reference_binding']=ards2._reference_binding(p)
        with tempfile.TemporaryDirectory() as tmp:
            con=memory.connect(Path(tmp)/'ards.db')
            selection=lambda previous:{'topic_id':43,'topic_label':'Mathematics','difficulty':1,'continuation':False,'story':False,'presentation':'direct','rolls':{'O':99,'X':142,'Y':1,'P':99}}
            ident=memory.record_random_selection(con,selection)['external_id'];plan=ards2.plan(con,ident,randbelow=lambda n:0)
            if plan['primary_pattern'] not in p['patterns']:p['patterns'].append(plan['primary_pattern'])
            ards2.register(con,ident,p);r=ards2.verify(con,ident)
            self.assertEqual(r['outcome'],'experimental')
            self.assertEqual(r['reference_test_outcome'],'test_verified')
            self.assertEqual(r['authored_solution_status'],'unverified_proposal')
            with self.assertRaisesRegex(ValueError,'verification'):ards2.release(con,ident)
            self.assertEqual(memory.get_challenge(con,ident)['status'],'selected')
            con.close()

    def test_preparation_replaces_prose_explicitly_without_mutating_the_input(self):
        p=package();p['reference_solution']='WRONG';original=copy.deepcopy(p)
        fixed=ards2.prepare_reference(p)
        self.assertEqual(p,original)
        self.assertTrue(ards2.reference_matches(fixed))
        self.assertNotEqual(fixed['reference_solution'],'WRONG')
        fixed['reference_binding']['registry_sha256']='0'*64
        self.assertFalse(ards2.reference_matches(fixed))

    def test_source_change_requires_new_verification_without_rewriting_the_package(self):
        p=package()
        with tempfile.TemporaryDirectory() as tmp:
            con=memory.connect(Path(tmp)/'ards.db')
            selection=lambda previous:{'topic_id':43,'topic_label':'Mathematics','difficulty':1,'continuation':False,'story':False,'presentation':'direct','rolls':{'O':99,'X':142,'Y':1,'P':99}}
            ident=memory.record_random_selection(con,selection)['external_id'];plan=ards2.plan(con,ident,randbelow=lambda n:0)
            if plan['primary_pattern'] not in p['patterns']:p['patterns'].append(plan['primary_pattern'])
            ards2.register(con,ident,p);ards2.verify(con,ident)
            next_identity=ards2._reference_identity(p)
            next_identity['source_sha256']['ppc3.py']='1'*64
            with patch.object(ards2,'_reference_identity',return_value=next_identity):
                with self.assertRaisesRegex(ValueError,'stale'):ards2.release(con,ident)
                self.assertTrue(ards2.verify(con,ident)['reference_binding_matches'])
                self.assertTrue(ards2.release(con,ident)['released'])
            self.assertEqual(ards2.load_package(con,memory.get_challenge(con,ident))[1],p)
            con.close()

    def test_pricing_and_rotation_samples_respect_their_domains(self):
        p=package();p['samples']=[{'input':'0','output':'0'}]
        self.assertEqual(ards2.verify_body(p)['outcome'],'failed')
        p=package(1);p['samples']=[{'input':'zz','output':'YES'}]
        self.assertEqual(ards2.verify_body(p)['outcome'],'failed')


class LeanBoundaryTests(unittest.TestCase):
    def test_malformed_approval_manifest_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            pins=Path(tmp)/'manifest.json';pins.write_text('{"schema":"ppc3-approved-lean-v1","sources":[]}')
            with patch.object(ppc3_lean,'MANIFEST',pins),patch.object(ppc3_lean,'_tool',side_effect=AssertionError('must not execute')):
                r=ppc3_lean.check_examples()
        self.assertEqual(r['status'],'rejected')
        self.assertIn('manifest',r['reason'])

    def test_changed_source_is_rejected_before_any_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            altered=Path(tmp)/'PPC3Examples.lean';altered.write_text('theorem forgery : True := True.intro\n')
            with patch.object(ppc3_lean,'TRUSTED',altered),patch.object(ppc3_lean,'_tool',side_effect=AssertionError('must not execute')):
                r=ppc3_lean.check_examples()
        self.assertEqual(r['status'],'rejected');self.assertIn('Unreviewed',r['reason'])

    def test_expected_interface_rejects_true_even_if_its_source_pin_is_updated(self):
        if not (ppc3_lean._tool('lean') and shutil.which('bwrap')):self.skipTest('Lean and bubblewrap required')
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);altered=directory/'PPC3Examples.lean'
            source=ppc3_lean.TRUSTED.read_text();a=source.index('theorem conjunction_swap');b=source.index('#print axioms')
            altered.write_text(source[:a]+'theorem conjunction_swap : True := True.intro\ntheorem implication_compose : True := True.intro\n'+source[b:])
            manifest=json.loads(ppc3_lean.MANIFEST.read_text());manifest['sources'][altered.name]=hashlib.sha256(altered.read_bytes()).hexdigest()
            pins=directory/'manifest.json';pins.write_text(json.dumps(manifest))
            with patch.object(ppc3_lean,'TRUSTED',altered),patch.object(ppc3_lean,'MANIFEST',pins),patch.object(ppc3_lean,'ARTIFACT_DIR',directory/'runs'):
                r=ppc3_lean.check_examples()
        self.assertEqual(r['status'],'rejected',r)
        self.assertFalse(r['lean_kernel_checked'])
        self.assertTrue(any(c['exit_code']!=0 for c in r['commands']))
        self.assertIn('PPC3Expected.lean',r['reason'])
        self.assertIn('True',r['reason'])


class ProvenanceTests(unittest.TestCase):
    def test_benchmarks_record_sources_and_cannot_overwrite_prior_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=ppc3_stress.run(4,77,directory=tmp)
            self.assertEqual(r['provenance']['source_sha256']['scripts/ppc3.py'],hashlib.sha256((ROOT/'scripts/ppc3.py').read_bytes()).hexdigest())
            self.assertEqual(r,ppc3_stress.run(4,77,directory=tmp))
            target=Path(tmp)/'seed-77-n4/report.json';target.write_text('preserve me')
            with self.assertRaises(FileExistsError):ppc3_stress.run(4,77,directory=tmp)
            self.assertEqual(target.read_text(),'preserve me')


if __name__=='__main__':unittest.main()
