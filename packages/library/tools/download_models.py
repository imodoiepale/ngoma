import pathlib
import json
import urllib.request
import urllib.parse
import hashlib
import time
import concurrent.futures
ROOT=pathlib.Path('/workspace/epalle'); TOKEN=pathlib.Path('/tmp/epalle-hf-token').read_text().strip()
class SafeRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  new=super().redirect_request(req,fp,code,msg,headers,newurl)
  if new is not None and urllib.parse.urlparse(newurl).hostname != urllib.parse.urlparse(req.full_url).hostname:new.remove_header('Authorization')
  return new
opener=urllib.request.build_opener(SafeRedirect())
items=json.loads((ROOT/'manifests/models.json').read_text());results=[]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def download(x):
 target=ROOT/'ComfyUI/models'/x['folder']/pathlib.Path(x['file']).name;target.parent.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.part')
 try:
  if target.exists() and target.stat().st_size==x['size'] and digest(target)==x['sha256']:return dict(file=x['file'],status='verified_cached',bytes=x['size'])
  url='https://huggingface.co/'+x['repo']+'/resolve/'+x['revision']+'/'+urllib.parse.quote(x['file'])
  for attempt in range(3):
   try:
    offset=part.stat().st_size if part.exists() else 0
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+TOKEN,'User-Agent':'epalle-model-library/1.0',**({'Range':f'bytes={offset}-'} if offset else {})})
    with opener.open(req,timeout=120) as r:
     mode='ab' if offset and r.status==206 else 'wb'
     with part.open(mode) as f:
      while True:
       chunk=r.read(8*1024*1024)
       if not chunk:break
       f.write(chunk)
    if part.stat().st_size != x['size']:raise ValueError('size mismatch')
    if x['sha256'] and digest(part)!=x['sha256']:raise ValueError('checksum mismatch')
    part.replace(target);print('VERIFIED',x['file'],flush=True);return dict(file=x['file'],status='verified',bytes=x['size'],sha256=x['sha256'])
   except urllib.error.HTTPError as e:
    if e.code in (401,403):raise
    if attempt==2:raise
    time.sleep(3)
  raise RuntimeError('attempts exhausted')
 except Exception as e:return dict(file=x['file'],status='failed',error=type(e).__name__+': '+str(e))
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for r in pool.map(download,items):
   results.append(r);(ROOT/'manifests/model-download-results.json').write_text(json.dumps(results,indent=2));print(r['status'],r['file'],flush=True)
finally:
 pathlib.Path('/tmp/epalle-hf-token').unlink(missing_ok=True)
print('DOWNLOADS_COMPLETE',flush=True)
