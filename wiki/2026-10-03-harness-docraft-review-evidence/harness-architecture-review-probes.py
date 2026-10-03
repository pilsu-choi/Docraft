import sys,json,uuid
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,'/home/pilsu/projects/mirae-assets/harness-v2/.worktrees/architecture-review-20261003/src')
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from mlife_harness.api.app import create_app
from mlife_harness.api.jobs import Job,PostgresJobStore,notify,now_iso
from mlife_harness.config import Settings
from mlife_harness.pipeline import HarnessPipeline
from mlife_harness.rules.engine import RuleEngine
from mlife_harness.rules.spec import default_ruleset_dir,load_rule_catalog
from mlife_harness.persistence.recorder import PersistenceRecorder
from mlife_harness.persistence.postgres.repositories import create_all
from mlife_harness.ingest.contract import validate_input

settings=Settings(master_required_for_ready=False, master_embedding_enabled=False)
pipeline=HarnessPipeline(rule_engine=RuleEngine(catalog=load_rule_catalog(default_ruleset_dir())),settings=settings)
with TestClient(create_app(pipeline=pipeline,settings=settings)) as client:
 sync=client.post('/v2/jobs:sync',files={'json':('input.json',b'{}','application/json')})
 async_response=client.post('/v2/jobs',files={'json':('input.json',b'{}','application/json')})
 jid=async_response.json()['job_id']
 status=client.get('/v2/jobs/'+jid).json()
 print('empty_object_api',json.dumps({'sync_http':sync.status_code,'sync_tier':sync.json().get('harness',{}).get('tier'),'async_http':async_response.status_code,'async_final_status':status['status']}))
image=Path('/tmp/harness-architecture-review-input.bin');image.write_bytes(b'not-decoded-at-ingest')
print('empty_object_batch_rejections',[str(r.code) for r in validate_input({},image,settings).rejections])

engine=create_engine('sqlite://');create_all(engine)
recorder=PersistenceRecorder(engine=engine)
store=PostgresJobStore(recorder,cache_reads=False)
job=Job(job_id=uuid.uuid4().hex,submitted_at=now_iso())
with patch('mlife_harness.persistence.recorder.session_scope',side_effect=RuntimeError('simulated transient database write outage')):
 store.put(job)
print('lost_insert',json.dumps({'durable_flag':store.durable,'put_returned_without_exception':True,'get_after_database_recovery':store.get(job.job_id)}))

from mlife_harness.domain.tier import JobStatus
stored=Job(job_id=uuid.uuid4().hex,submitted_at=now_iso())
store.put(stored)
stored.status=JobStatus.COMPLETED
stored.finished_at=now_iso()
stored.result={'harness':{'tier':'pass'},'medical_personal_data':'sample'}
with patch('mlife_harness.persistence.recorder.JobResultRepository.upsert',side_effect=RuntimeError('simulated result save failure')):
 store.put(stored)
restored=store.get(stored.job_id)
print('lost_result',json.dumps({'status':str(restored.status),'result':restored.result,'put_returned_without_exception':True}))

job.result={'medical_personal_data':'sample'}
with patch('httpx.post',return_value=Mock()) as post:
 notify('http://127.0.0.1:9999/internal',job)
 print('callback_destination',post.call_args.args[0],'includes_full_result',post.call_args.kwargs['json']['result']==job.result)

with TestClient(create_app(settings=Settings(api_auth_mode='mtls'))) as client:
 print('mtls_without_header',client.get('/v2/jobs/x').status_code,'mtls_with_client_supplied_success',client.get('/v2/jobs/x',headers={'X-Client-Verified':'SUCCESS forged'}).status_code)
