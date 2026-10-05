import hashlib
import json
from pathlib import Path
import sys
import threading

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import catalog
import core


@pytest.fixture
def small_catalog(tmp_path):
    data = b'GGUF' + b'verified-content' * 100
    entries = [dict(id=mid, name=mid, filename=mid+'.gguf', repo='trusted/test', revision='pinned',
                    size=len(data), sha256=hashlib.sha256(data).hexdigest()) for mid in ('first','second')]
    (tmp_path/'models-catalog.json').write_text(json.dumps(entries))
    (tmp_path/'models').mkdir()
    return catalog.ModelCatalog(tmp_path), data


class Response:
    status_code = 206
    def __init__(self, data, offset):
        self.data = data[offset:]
        self.headers = {'Content-Range':f'bytes {offset}-{len(data)-1}/{len(data)}'}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def raise_for_status(self): pass
    def iter_content(self, size): yield self.data


def test_resume_verifies_model_and_persists_defaults(small_catalog, monkeypatch):
    c, data = small_catalog
    part=c.path('first').with_suffix('.gguf.part')
    part.write_bytes(data[:100])
    def get(url,headers,**kwargs):
        assert '/pinned/' in url
        assert headers['Range']=='bytes=100-'
        return Response(data,100)
    monkeypatch.setattr(catalog.requests,'get',get)
    c.start_download('first'); c.thread.join(3)
    assert c.download['status']=='done'
    assert c.path('first').read_bytes()==data
    assert not part.exists()
    c.set_default('first');c.set_execution('cpu')
    restarted=catalog.ModelCatalog(c.root)
    assert restarted.default()=='first' and restarted.execution=='cpu'
    with pytest.raises(ValueError): c.resolve('second')
    with pytest.raises(ValueError): c.resolve('../outside')
    with pytest.raises(ValueError): c.resolve_execution('invalid')


def test_corrupt_download_never_becomes_installed(small_catalog,monkeypatch):
    c,data=small_catalog
    monkeypatch.setattr(catalog.requests,'get',lambda *a,**kw:Response(b'x'*len(data),0))
    c.start_download('first');c.thread.join(3)
    assert c.download['status']=='error'
    assert not c.path('first').exists()
    assert not c.path('first').with_suffix('.gguf.part').exists()


def test_cancel_retains_partial_file_for_resume(small_catalog,monkeypatch):
    c,data=small_catalog
    part=c.path('first').with_suffix('.gguf.part');part.write_bytes(data[:10])
    class CancelResponse(Response):
        def iter_content(self,size):
            c.cancelled.set()
            yield self.data
    monkeypatch.setattr(catalog.requests,'get',lambda *a,**kw:CancelResponse(data,10))
    c.start_download('first');c.thread.join(3)
    assert c.download['status']=='cancelled'
    assert part.read_bytes()==data[:10]
    assert not c.installed('first')


def test_cpu_uses_cpu_binary_without_detecting_cuda(small_catalog,monkeypatch):
    c,data=small_catalog;c.path('first').write_bytes(data)
    exe=c.root/'bin/cpu/llama-server.exe';exe.parent.mkdir(parents=True);exe.touch()
    monkeypatch.setattr(core,'ROOT',c.root)
    import ctranslate2
    def forbidden(): raise AssertionError('CPU must not query CUDA')
    monkeypatch.setattr(ctranslate2,'get_cuda_device_count',forbidden)
    captured=[]
    class Process:
        def poll(self):return None
        def terminate(self):pass
        def wait(self,**kwargs):pass
    monkeypatch.setattr(core.subprocess,'Popen',lambda args,**kwargs:captured.append(args) or Process())
    monkeypatch.setattr(core.requests,'get',lambda *a,**kw:type('Health',(),{'ok':True})())
    llm=core.LocalLLM(c);llm.execution='cpu'
    try:
        llm.start(threading.Event())
        args=captured[0]
        assert args[0]==str(exe)
        assert args[args.index('-ngl')+1]=='0'
        assert args[args.index('--device')+1]=='none'
        assert str(c.path('first')) in args
        assert llm.device=='cpu'
    finally: llm.stop()


def test_retry_records_choice_without_relabelling_previous_report(small_catalog,tmp_path,monkeypatch):
    c,data=small_catalog
    for mid in c.entries:c.path(mid).write_bytes(data)
    meetings=tmp_path/'reunions';meetings.mkdir()
    monkeypatch.setattr(core,'DATA',meetings)
    studio=core.Studio();studio.catalog=c
    m=studio.create('Test','missing.mp4',llm_model='first')
    studio.update(m['id'],report={'overview':'Previous'},report_model='first',segments=[{'start':0,'text':'Valid'}])
    monkeypatch.setattr(threading.Thread,'start',lambda self:None)
    studio.launch(m['id'],summary_only=True,llm_model='second',execution='cpu')
    updated=studio.read(m['id'])
    assert updated['llm_model']=='second' and updated['execution']=='cpu'
    assert updated['report_model']=='first' and updated['report']['overview']=='Previous'
