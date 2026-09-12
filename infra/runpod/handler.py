"""Single-owner RunPod worker; only installed API templates can run."""
import base64,hashlib,json,os,pathlib,re,subprocess,time,urllib.request,uuid
ROOT=pathlib.Path(os.environ.get('EPALLE_ROOT','/runpod-volume/epalle'))
COMFY='http://127.0.0.1:8188'
def request(path,payload=None):
 data=None if payload is None else json.dumps(payload).encode()
 with urllib.request.urlopen(urllib.request.Request(COMFY+path,data=data,headers={'Content-Type':'application/json'}),timeout=30) as r:return json.load(r)
def handler(job):
 inp=job.get('input') or {};name=inp.get('workflow_name','smoke-test')
 if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):return {'error':'Invalid workflow name'}
 template=ROOT/'workflow-api'/f'{name}.json'
 if not template.exists():return {'error':'Template not installed. Export and validate the canvas as API JSON first.'}
 graph=json.loads(template.read_text());encoded=json.dumps(graph,sort_keys=True).encode();fingerprint=hashlib.sha256(encoded).hexdigest()
 if inp.get('dry_run',True):return {'validated_template':name,'workflow_sha256':fingerprint,'node_count':len(graph),'queued':False}
 # API/paid workflows are deliberately excluded from this GPU endpoint.
 if any('MATRIX_' in n.get('class_type','') for n in graph.values()):return {'error':'Dataset operations use the dedicated live=false MATRIX runtime.'}
 job_id=re.sub(r'[^A-Za-z0-9_-]','_',str(job.get('id',uuid.uuid4())))[:120]
 outdir=ROOT/'jobs'/job_id;outdir.mkdir(parents=True,exist_ok=True)
 result_file=outdir/'result.json';admitted=outdir/'admitted.json'
 if result_file.exists():return json.loads(result_file.read_text())
 try:
  with admitted.open('x') as f:json.dump({'workflow_sha256':fingerprint,'started':time.time()},f)
 except FileExistsError:return {'error':'Prior attempt has an indeterminate state; inspect saved job before retrying.'}
 # Standard SaveImage outputs receive a unique prefix. Other save nodes must be configured in the approved template.
 for n in graph.values():
  if n.get('class_type')=='SaveImage':n['inputs']['filename_prefix']=f'epalle/{job_id}/image'
 submit=request('/prompt',{'prompt':graph,'client_id':job_id});pid=submit.get('prompt_id')
 if not pid:return {'error':'ComfyUI rejected template','details':submit.get('node_errors',{})}
 (outdir/'prompt.json').write_text(json.dumps({'prompt_id':pid,'workflow_sha256':fingerprint}))
 for _ in range(1700):
  data=request('/history/'+pid)
  if pid in data:
   rec=data[pid]
   if rec.get('status',{}).get('status_str')=='error':return {'error':'ComfyUI execution failed','prompt_id':pid,'job_path':str(outdir)}
   files=[];total=0
   for node in rec.get('outputs',{}).values():
    for key in ['images','gifs','videos','audio']:
     for asset in node.get(key,[]):
      if not isinstance(asset,dict) or 'filename' not in asset:continue
      kind=asset.get('type','output');base=(ROOT/'ComfyUI'/('temp' if kind=='temp' else 'output')).resolve()
      path=(base/asset.get('subfolder','')/asset['filename']).resolve()
      if not path.is_relative_to(base) or not path.is_file():continue
      size=path.stat().st_size;digest=hashlib.sha256()
      with path.open('rb') as source:
       for chunk in iter(lambda:source.read(8*1024*1024),b''):digest.update(chunk)
      entry={'filename':path.name,'path':str(path),'bytes':size,'sha256':digest.hexdigest()}
      if total+size<=4*1024*1024:
       entry['base64']=base64.b64encode(path.read_bytes()).decode();total+=size
      files.append(entry)
   result={'job_id':job_id,'prompt_id':pid,'workflow_sha256':fingerprint,'files':files,'persistent_job_path':str(outdir)}
   tmp=outdir/'result.tmp';tmp.write_text(json.dumps(result));tmp.replace(result_file);return result
  time.sleep(2)
 return {'error':'Timed out; job may still be active. Inspect prompt_id before retrying.','prompt_id':pid}
if __name__=='__main__':
 import runpod
 ROOT.mkdir(parents=True,exist_ok=True)
 logfile=(ROOT/'logs/serverless-comfy.log').open('a')
 proc=subprocess.Popen([str(ROOT/'venv/bin/python'),str(ROOT/'ComfyUI/main.py'),'--listen','127.0.0.1','--port','8188','--user-directory',str(ROOT/'ComfyUI/user')],cwd=ROOT/'ComfyUI',stdout=logfile,stderr=subprocess.STDOUT)
 for _ in range(180):
  try:request('/system_stats');break
  except Exception:
   if proc.poll() is not None:raise RuntimeError('ComfyUI failed to start; inspect persistent log')
   time.sleep(2)
 else:raise RuntimeError('ComfyUI startup timeout')
 runpod.serverless.start({'handler':handler})
