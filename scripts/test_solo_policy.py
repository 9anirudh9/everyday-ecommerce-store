"""Synthetic solo policy contracts; no hosted enforcement or approval proof."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import release_gate as g
from test_release_contracts import APP, DIGEST, NOW, TREE, policy


def solo():
    p = json.loads((g.ROOT/'config/release-policy.solo-proposal.json').read_text())
    p['environments'] = policy()['environments']
    return p


def branch():
    p=json.loads((g.ROOT/'config/github-protection/solo-maintainer-v1/main.json').read_text())
    for k in ('enforce_admins','allow_force_pushes','allow_deletions','required_conversation_resolution'):
        p[k]={'enabled':p[k]}
    return p


def environment():
    return {'id':42,'protection_rules':[{'type':'required_reviewers','prevent_self_review':False,
        'reviewers':[{'type':'User','reviewer':g.owner_identity(solo())}]}],
        'can_admins_bypass':False, # SYNTHETIC ONLY; REST adapter is unimplemented.
        'deployment_branch_policy':{'protected_branches':True,'custom_branch_policies':False}}


def request():
    return dict(environment='production',application_sha=APP,artifact_sha256=DIGEST,
                authorization_run_id='100',ci_run_id='200',staging_smoke_run_id='300',operation='publish')


def current():
    return dict(id=100,run_attempt=1,actor=g.owner_identity(solo()),triggering_actor=g.owner_identity(solo()))


def review():
    return dict(state='approved',user=g.owner_identity(solo()),environments=[{'id':42,'name':'production'}],
                comment=g.approval_statement(solo(),request()))


class Reader:
    def __init__(self,history=None): self.history=[review()] if history is None else history
    def request(self,path):
        assert path=='/actions/runs/100/approvals',path
        return self.history


class SoloContracts(unittest.TestCase):
    def test_default_strict_and_unknown_or_unbound_profiles(self):
        self.assertEqual(g.protection_profile(policy()),'strict')
        for fields in ({'protection_profile':'typo'},{'solo_policy_sha256':'0'*64},{'owner_id':1}):
            p=solo();p.update(fields)
            with self.subTest(fields=fields),self.assertRaises(ValueError):g.protection_profile(p)
        with self.assertRaises(ValueError):g.verify_branch_protection(branch())
        with self.assertRaises(ValueError):g.verify_environment_protection(environment(),'9anirudh9')

    def test_disabled_proposal_cannot_authorize(self):
        p=json.loads((g.ROOT/'config/release-policy.solo-proposal.json').read_text())
        for name in ('staging','production'):
            with self.assertRaises(ValueError):g.policy_environment(p,name)

    def test_branch_controls_and_pr_object_required(self):
        g.verify_branch_protection(branch(),solo())
        for key,value in [('required_pull_request_reviews',None),('required_conversation_resolution',{'enabled':False}),
                          ('allow_deletions',{'enabled':True}),('allow_force_pushes',{'enabled':True}),('enforce_admins',{'enabled':False})]:
            b=branch();b[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.verify_branch_protection(b,solo())
        for key,value in [('required_approving_review_count',1),('require_code_owner_reviews',True),('require_last_push_approval',True),
                          ('bypass_pull_request_allowances',{'users':['owner']})]:
            b=branch();b['required_pull_request_reviews'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.verify_branch_protection(b,solo())
        for checks in ({'strict':True,'contexts':['P0 checks']},{'strict':False,'checks':[{'context':'P0 checks','app_id':15368}]},
                       {'strict':True,'checks':[{'context':'P0 checks','app_id':1}]}):
            b=branch();b['required_status_checks']=checks
            with self.assertRaises(ValueError):g.verify_branch_protection(b,solo())

    def test_environment_retains_unknown_bypass_block(self):
        g.verify_environment_protection(environment(),'9anirudh9',solo())
        for change in ('missing','true','self','reviewer','branches'):
            e=environment()
            if change=='missing':del e['can_admins_bypass']
            if change=='true':e['can_admins_bypass']=True
            if change=='self':e['protection_rules'][0]['prevent_self_review']=True
            if change=='reviewer':e['protection_rules'][0]['reviewers'][0]['reviewer']['id']=1
            if change=='branches':e['deployment_branch_policy']['protected_branches']=False
            with self.subTest(change=change),self.assertRaises(ValueError):g.verify_environment_protection(e,'9anirudh9',solo())

    def test_provider_owner_review_positive(self):
        result=g.verify_solo_review(Reader(),solo(),request(),current(),environment())
        self.assertEqual(result['user'],g.owner_identity(solo()))
        self.assertEqual(result['environment_id'],42)

    def test_missing_rejected_conflicting_forged_reviews(self):
        variants=[[],[review(),review()]]
        for key,value in [('state','rejected'),('user',{'login':'9anirudh9','id':1,'type':'User'}),
                          ('comment','APPROVE'),('environments',[{'id':99,'name':'production'}]),
                          ('environments',[{'id':42,'name':'staging'}])]:
            r=review();r[key]=value;variants.append([r])
        for history in variants:
            with self.subTest(history=history),self.assertRaises(ValueError):g.verify_solo_review(Reader(history),solo(),request(),current(),environment())

    def test_actor_rerun_and_exact_artifact_policy_binding(self):
        for key,value in [('run_attempt',2),('actor',{}),('triggering_actor',{})]:
            c=current();c[key]=value
            with self.assertRaises(ValueError):g.verify_solo_review(Reader(),solo(),request(),c,environment())
        for key in ('environment','application_sha','artifact_sha256','ci_run_id','staging_smoke_run_id','operation',
                    'rollback_version_id','migration_review_sha256','authorization_run_id'):
            r=request();r[key]='changed'
            with self.subTest(key=key),self.assertRaises(ValueError):g.verify_solo_review(Reader(),solo(),r,current(),environment())

    def test_end_to_end_solo_authorization_and_expiry(self):
        # Adapt the existing strict chain fixture while exercising all real gate functions.
        from datetime import timedelta
        p=solo();p['trusted_bridge_logins']=['approved-provider[bot]']
        class Chain(Reader):
            def protection_request(self,path):return branch()
            def request(self,path):
                if path.startswith('/environments/'):return environment()
                if path.startswith('/branches/'):return {'protected':True,'commit':{'sha':APP}}
                if path.startswith('/compare/'):return {'merge_base_commit':{'sha':APP}}
                if path.startswith('/git/commits/'):return {'tree':{'sha':TREE}}
                return super().request(path)
            def run(self,runid):
                paths={'100':'release-authorize.yml','200':'checks.yml','300':'post-deploy-smoke.yml'}
                return {**current(),'id':int(runid),'repository':{'full_name':p['repository']},'head_sha':APP,
                        'head_branch':'main','path':'.github/workflows/'+paths[str(runid)],'event':'workflow_dispatch',
                        'status':'completed','conclusion':'success','created_at':(NOW-timedelta(minutes=2)).isoformat()}
            def artifact_json(self,run,prefix,filename):
                if filename=='ci-summary.json':return dict(status='PASS',application_sha=APP,artifact_sha256=DIGEST,dirty_status='')
                if filename=='monitor.json':return dict(status='PASS',promotion_ready=True,application_sha=APP,artifact_sha256=DIGEST)
                return dict(status='PASS',environment='staging',application_sha=APP,artifact_sha256=DIGEST,
                            url=p['environments']['staging']['url'],finished_utc=NOW.isoformat(),tests=20,harness_sha=APP)
        result=g.authorize(Chain(),p,request(),NOW)
        self.assertEqual(result['owner_review']['environment_id'],42)
        with self.assertRaisesRegex(ValueError,'expired'):g.authorize(Chain(),p,request(),NOW+timedelta(hours=2))
        with self.assertRaises(ValueError):g.authorize(Chain([]),p,request(),NOW)
        from test_release_contracts import event
        class EventChain(Chain):
            def artifact_json(self,run,prefix,filename):
                if filename=='approval.json':return result
                return super().artifact_json(run,prefix,filename)
        ec=EventChain()
        self.assertEqual(g.verified_event(ec,p,event('production'),NOW)['status'],'succeeded')
        with self.assertRaises(ValueError):g.verified_event(EventChain([]),p,event('production'),NOW)
        with self.assertRaises(ValueError):g.verified_event(ec,p,event('production'),NOW+timedelta(hours=2))
        for key,value in [('owner_review',{}),('authorization_run_id','101'),('expires_utc',(NOW+timedelta(minutes=59)).isoformat()),
                          ('solo_policy_sha256','0'*64)]:
            old=result[key];result[key]=value
            with self.subTest(receipt=key),self.assertRaises(ValueError):g.verified_event(ec,p,event('production'),NOW)
            result[key]=old
        old=result['owner_review']['comment_sha256'];result['owner_review']['comment_sha256']='0'*64
        with self.assertRaises(ValueError):g.verified_event(ec,p,event('production'),NOW)
        result['owner_review']['comment_sha256']=old
        result['solo_policy_sha256']='0'*64
        with self.assertRaises(ValueError):g.validate_approval(result,p,'production',APP,DIGEST,NOW)


if __name__=='__main__':unittest.main(verbosity=2)
