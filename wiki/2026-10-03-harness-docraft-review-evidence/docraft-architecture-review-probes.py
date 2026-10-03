import sys
import io
import threading
from pathlib import Path
from unittest.mock import patch

repo = Path('/home/pilsu/projects/mirae-assets/Docraft/.worktrees/architecture-review-20261003')
sys.path[:0] = [str(repo), str(repo / 'tests')]
import conftest  # isolated local PostgreSQL schema and offline settings
from backend import main, engine
from backend.db import connect, now
from test_api import project, schema, upload, wait_for, client
from openpyxl import load_workbook

p = project('architecture-review')
d = upload(p)
wait_for(d, 'parsed')
entered, release = threading.Event(), threading.Event()

def fake_parse(*args):
    if threading.current_thread().name == 'old-attempt':
        entered.set()
        assert release.wait(5)
        return 'OLD attempt', []
    return 'NEW attempt', []

with patch.object(main, 'parse', fake_parse), patch.object(main, 'dispatch', lambda *args: None):
    with connect() as db:
        db.execute("UPDATE documents SET status='queued',updated_at=? WHERE id=?", (now(), d))
    old = threading.Thread(target=main.run_parse, args=(d,), name='old-attempt')
    old.start()
    assert entered.wait(5)
    response = client.post(f'/api/documents/{d}/parse', json={})
    assert response.status_code == 202
    main.run_parse(d)
    with connect() as db:
        print('retry while running:', response.status_code, 'new completion=', db.execute('SELECT markdown FROM documents WHERE id=?', (d,)).fetchone()['markdown'])
    release.set()
    old.join(5)
    with connect() as db:
        print('late old completion overwrites new=', db.execute('SELECT markdown FROM documents WHERE id=?', (d,)).fetchone()['markdown'])

s = schema(p)
with connect() as db:
    db.execute("UPDATE documents SET schema_id=?,result=?,groundings='{}',status='completed' WHERE id=?", (s, '{"hospital":"ABC Hospital","total_amount":120000}', d))
with patch.object(main, 'dispatch', lambda *args: None):
    queued = client.post(f'/api/documents/{d}/extract', json={'schema_id': s})
    approved = client.post(f'/api/documents/{d}/approve')
    main.run_extract(d, s)
    print('queued extract then approve:', queued.status_code, approved.status_code, 'final=', client.get(f'/api/documents/{d}').json()['status'])

for fmt in ['csv', 'xlsx']:
    response = main.table_response([{'value': '=1+1'}], 'probe', fmt)
    if fmt == 'csv':
        print('CSV formula export:', repr(response.body.decode()))
    else:
        cell = load_workbook(io.BytesIO(response.body)).active['A2']
        print('XLSX formula export:', cell.value, 'data_type=', cell.data_type)

seen = []
def blocked_urlopen(request):
    seen.append(getattr(request, 'full_url', request))
    raise RuntimeError('blocked review probe; no external access')
remote = {'type': 'object', 'properties': {'hospital': {'$ref': 'http://127.0.0.1:12345/internal-schema'}}}
created = client.post(f'/api/projects/{p}/schemas', json={'name': 'remote', 'json_schema': remote})
with patch('urllib.request.urlopen', blocked_urlopen):
    try:
        engine.validate({'hospital': 'value'}, remote, {})
    except Exception as exc:
        print('remote ref accepted=', created.status_code, 'network target=', seen, 'exception=', type(exc).__name__)
