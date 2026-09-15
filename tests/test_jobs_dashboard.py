import shutil
import subprocess

import pytest

from app.jobs.dashboard import SCRIPT, install_jobs_dashboard


def test_panel_is_installed():
    page = install_jobs_dashboard('<section class="card job"></section></body>')
    assert page.index('id="active-jobs"') < page.index('class="card job"')
    assert 'jobs-list' in page


def test_navigation_restoration_and_reconnection():
    if not shutil.which('node'):
        pytest.skip('Node is required for browser-controller test')
    harness = r'''
const assert=require('node:assert/strict');
class Element {
 constructor(){this.style={};this.dataset={};this.children=[];this.textContent='';this.disabled=false}
 replaceChildren(){this.children=[]}
 append(child){this.children.push(child)}
 setAttribute(){}
 addEventListener(){}
 scrollIntoView(){}
}
const elements=new Map();
const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
const document={hidden:false,getElementById:get,createElement:()=>new Element(),addEventListener(){}};
const window={addEventListener(){}};
const localStorage={getItem:()=> 'completed',setItem(){},removeItem(){}};
let jobId,timer,watch,action,lastRendered;
const $=selector=>get(selector.slice(1)),submit=get('submit'),jobBox=get('job'),fa=String;
function render(job){lastRendered=job.id;submit.disabled=false}
let scheduled;
function setInterval(callback){scheduled=callback}
function clearInterval(){}
function alert(message){throw Error(message)}
let offline=false,requests=0;
let jobs=[{id:'completed',filename:'Old',status:'completed',created_at:'1',progress:{percent:100}},{id:'running',filename:'<b>New</b>',status:'running',created_at:'2',progress:{percent:30}}];
async function fetch(){requests++;if(offline)throw Error('offline');return {ok:true,json:async()=>({items:jobs})}}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
'''
    assertions = r'''
(async()=>{
await flush();
assert.equal(jobId,'running');
assert.equal(lastRendered,'running');
assert.equal(submit.disabled,true);
assert.equal(get('jobs-list').children[0].textContent.includes('<b>New</b>'),true);
get('jobs-list').children[1].onclick();
assert.equal(lastRendered,'completed');
assert.equal(submit.disabled,true);
scheduled();await flush();
assert.equal(jobId,'completed');
offline=true;scheduled();await flush();
assert.equal(submit.disabled,true);
assert.equal(get('resume').disabled,true);
offline=false;jobs=jobs.filter(job=>job.id==='running');scheduled();await flush();
assert.equal(jobId,'running');
jobs[0].status='completed';scheduled();await flush();
assert.equal(submit.disabled,false);
jobs=[];scheduled();await flush();
assert.equal(jobBox.style.display,'none');
assert.equal(jobId,undefined);
console.log('Dashboard restoration and reconnection OK');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    script = SCRIPT.removeprefix('<script>').removesuffix('</script>')
    result = subprocess.run(['node'], input=harness + script + assertions, text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0, result.stderr
