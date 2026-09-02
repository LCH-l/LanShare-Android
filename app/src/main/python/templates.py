# -*- coding: utf-8 -*-
"""LanShare 前端页面模板（纯原生 JS，不依赖任何 CDN，断网可用）"""

# ============================================================
# 公共样式
# ============================================================
_COMMON_CSS = """
:root{
  --bg:#f1efe8; --card:#fff; --pri:#534ab7; --pri-d:#3c3489;
  --txt:#26215c; --mut:#5f5e5a; --line:rgba(0,0,0,.1);
  --ok:#0f6e56; --warn:#ba7517; --err:#a32d2d;
}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.6;font-size:14px}
.wrap{max-width:820px;margin:0 auto;padding:16px}
.card{background:var(--card);border-radius:12px;padding:16px;margin-bottom:14px;
  border:.5px solid var(--line)}
h1{font-size:19px;font-weight:500;margin:0 0 2px}
h2{font-size:14px;font-weight:500;margin:0 0 10px}
.sub{color:var(--mut);font-size:12px;margin-bottom:14px}
.btn{display:inline-block;padding:9px 16px;background:var(--pri);color:#fff;
  border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:500;
  text-decoration:none;font-family:inherit}
.btn:hover{background:var(--pri-d)}
.btn:active{opacity:.8}
.btn.gray{background:#888780}
.btn.red{background:var(--err)}
.btn.sm{padding:5px 10px;font-size:12px}
.btn:disabled{opacity:.5;cursor:not-allowed}
input,select{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:8px;
  font-size:13px;font-family:inherit;background:#fff;color:var(--txt)}
input:focus,select:focus{outline:none;border-color:var(--pri)}
label{display:block;font-size:12px;color:var(--mut);margin:10px 0 4px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.row>*{flex:1;min-width:120px}
.tag{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11px;font-weight:500}
.tag.on{background:#e1f5ee;color:var(--ok)}
.tag.off{background:#fcebeb;color:var(--err)}
.mut{color:var(--mut);font-size:12px}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.hint{background:#faf9f5;border-left:3px solid var(--warn);padding:8px 11px;
  border-radius:0 6px 6px 0;font-size:12px;color:#633806;margin:10px 0}
.toast{position:fixed;left:50%;bottom:28px;transform:translateX(-50%);
  background:#26215c;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;
  z-index:999;opacity:0;transition:opacity .25s;pointer-events:none}
.toast.show{opacity:1}
"""

# ============================================================
# 客户端：文件浏览/下载/上传
# ============================================================
CLIENT_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>__TITLE__ · 文件共享</title>
<style>""" + _COMMON_CSS + """
table{width:100%;border-collapse:collapse}
tr{border-bottom:1px solid var(--line)}
tr:hover{background:#faf9f5}
td{padding:9px 6px;font-size:13px}
.ico{width:26px;text-align:center;font-size:16px}
.nm{word-break:break-all}
.nm a{color:var(--txt);text-decoration:none}
.nm a:hover{color:var(--pri)}
.sz{width:88px;text-align:right;color:var(--mut);font-size:12px}
.dt{width:120px;color:var(--mut);font-size:12px}
.op{width:96px;text-align:right;white-space:nowrap}
.crumb{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:12px;font-size:13px}
.crumb a{color:var(--pri);text-decoration:none;padding:3px 7px;border-radius:5px;background:#eeedfe}
.crumb span{color:var(--mut)}
.up-zone{border:2px dashed #cecbf6;border-radius:10px;padding:22px;text-align:center;
  color:var(--mut);font-size:13px;margin-bottom:12px;cursor:pointer;transition:.2s}
.up-zone:hover,.up-zone.over{background:#eeedfe;border-color:var(--pri)}
.bar{height:5px;background:#eeedfe;border-radius:3px;overflow:hidden;margin-top:6px}
.bar>i{display:block;height:100%;background:var(--pri);width:0;transition:width .2s}
.dropdown{position:relative;display:inline-block}
.dd-menu{display:none;position:absolute;right:0;top:100%;background:#fff;border:1px solid var(--line);
  border-radius:8px;z-index:20;min-width:118px;box-shadow:0 4px 14px rgba(0,0,0,.1)}
.dd-menu.show{display:block}
.dd-menu button{display:block;width:100%;padding:9px 13px;border:none;background:none;
  text-align:left;cursor:pointer;font-size:13px;color:var(--txt);font-family:inherit}
.dd-menu button:hover{background:#f1efe8}
@media(max-width:600px){.dt{display:none}.sz{width:70px}.op{width:60px}}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1>__TITLE__</h1>
    <div class="sub">局域网文件共享 · 权限：<b id="permTxt">-</b></div>
    <div class="crumb" id="crumb"></div>
    <div id="tools"></div>
    <table id="list"></table>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
var CUR = "", PERM = "read";

function toast(m){var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
  setTimeout(function(){t.classList.remove('show')},1900);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function fmt(n){if(n<1024)return n+' B';var u=['KB','MB','GB','TB'],i=-1;
  do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(1)+' '+u[i];}

function api(u,opt){return fetch(u,opt||{}).then(function(r){
  if(r.status===401){alert('需要密码');return null;} return r.json();});}

function load(p){
  CUR = p || "";
  api('/api/list?path='+encodeURIComponent(CUR)).then(function(d){
    if(!d) return;
    PERM = d.permission;
    document.getElementById('permTxt').textContent =
      {read:'只读（可下载）',write:'可读写（可上传/新建）',full:'完全控制（可增删改）'}[d.permission]||d.permission;
    renderCrumb(d.path);
    renderTools();
    renderList(d.items);
  });
}

function renderCrumb(p){
  var h='<a href="#" onclick="load(\\'\\');return false;">首页</a>';
  var acc='', parts=p?p.split('/').filter(Boolean):[];
  parts.forEach(function(x,i){
    acc += (i?'/':'')+x;
    h += '<span>/</span><a href="#" onclick="load(\\''+acc.replace(/'/g,"\\\\'")+'\\');return false;">'+esc(x)+'</a>';
  });
  document.getElementById('crumb').innerHTML=h;
}

function renderTools(){
  var t=document.getElementById('tools');
  if(PERM==='read'){ t.innerHTML='<div class="hint">当前为只读模式，可浏览和下载文件。</div>'; return; }
  var h='<div class="up-zone" id="uz" onclick="document.getElementById(\\'fi\\').click()">'+
    '点击选择文件，或拖拽文件到此处上传</div>'+
    '<input type="file" id="fi" multiple style="display:none" onchange="pick(this.files)">'+
    '<div id="prog"></div>';
  if(PERM==='full'){
    h+='<div class="row" style="margin-top:8px">'+
       '<button class="btn gray sm" onclick="mkdir()">新建文件夹</button></div>';
  }
  t.innerHTML=h;
  var uz=document.getElementById('uz');
  ['dragenter','dragover'].forEach(function(e){uz.addEventListener(e,function(ev){
    ev.preventDefault();uz.classList.add('over');});});
  ['dragleave','drop'].forEach(function(e){uz.addEventListener(e,function(ev){
    ev.preventDefault();uz.classList.remove('over');});});
  uz.addEventListener('drop',function(ev){pick(ev.dataTransfer.files);});
}

function renderList(items){
  var h='';
  if(!items.length) h='<tr><td class="mut" style="padding:20px;text-align:center">（空）</td></tr>';
  items.forEach(function(it){
    var pn = CUR ? CUR+'/'+it.name : it.name;
    var icon = it.is_dir ? '📁' : '📄';
    h+='<tr><td class="ico">'+icon+'</td><td class="nm">'+
       (it.is_dir?'<a href="#" onclick="load(\\''+pn.replace(/'/g,"\\\\'")+'\\');return false;">'+esc(it.name)+'</a>'
                 :'<a href="/raw/'+pn.split('/').map(encodeURIComponent).join('/')+'" download>'+esc(it.name)+'</a>')+
       '</td><td class="sz">'+(it.is_dir?'-':fmt(it.size))+'</td>'+
       '<td class="dt">'+esc((it.mtime||'').slice(0,16))+'</td><td class="op">';
    if(PERM==='full'&&!it.is_dir){
      h+='<div class="dropdown"><button class="btn gray sm" onclick="tgl(this)">操作</button>'+
         '<div class="dd-menu"><button onclick="delf(\\''+pn.replace(/'/g,"\\\\'")+'\\')">删除</button>'+
         '<button onclick="renf(\\''+pn.replace(/'/g,"\\\\'")+'\\')">重命名</button></div></div>';
    }
    h+='</td></tr>';
  });
  document.getElementById('list').innerHTML=h;
}

function tgl(b){var m=b.nextElementSibling;
  document.querySelectorAll('.dd-menu').forEach(function(x){if(x!==m)x.classList.remove('show');});
  m.classList.toggle('show');}
document.addEventListener('click',function(e){
  if(!e.target.closest('.dropdown'))document.querySelectorAll('.dd-menu').forEach(function(x){x.classList.remove('show');});});

function pick(files){
  if(!files||!files.length)return;
  var fs=Array.prototype.slice.call(files);
  var i=0;
  (function next(){
    if(i>=fs.length){toast('上传完成');load(CUR);return;}
    var f=fs[i++], fd=new FormData(); fd.append('file',f);
    var url='/api/upload?path='+encodeURIComponent(CUR?CUR+'/'+f.name:f.name);
    var box=document.createElement('div');
    box.innerHTML='<div class="mut">'+esc(f.name)+' <span class="p">0%</span>'+
      '<div class="bar"><i></i></div></div>';
    document.getElementById('prog').appendChild(box);
    var xhr=new XMLHttpRequest();
    xhr.open('PUT',url);
    xhr.upload.onprogress=function(e){
      if(e.lengthComputable){var p=Math.round(e.loaded/e.total*100);
        box.querySelector('.p').textContent=p+'%';box.querySelector('.bar>i').style.width=p+'%';}};
    xhr.onload=function(){
      if(xhr.status===200||xhr.status===201){box.querySelector('.p').textContent='完成';} 
      else{box.querySelector('.p').textContent='失败';}
      setTimeout(next,120);
    };
    xhr.onerror=function(){box.querySelector('.p').textContent='失败';setTimeout(next,120);};
    xhr.send(f);
  })();
}

function mkdir(){
  var n=prompt('新文件夹名称：');
  if(!n)return;
  api('/api/mkdir',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:CUR?CUR+'/'+n:n})}).then(function(d){
    if(!d)return; d.ok?(toast('已创建'),load(CUR)):alert(d.msg||'失败');});
}
function delf(p){
  if(!confirm('确定删除？\\n'+p))return;
  api('/api/delete?path='+encodeURIComponent(p),{method:'DELETE'}).then(function(d){
    if(!d)return; d.ok?(toast('已删除'),load(CUR)):alert(d.msg||'失败');});
}
function renf(p){
  var n=prompt('新名称：',p.split('/').pop());
  if(!n)return;
  api('/api/rename',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:p,newname:n})}).then(function(d){
    if(!d)return; d.ok?(toast('已重命名'),load(CUR)):alert(d.msg||'失败');});
}
load('');
</script></body></html>"""


# ============================================================
# 管理端：服务开关/共享目录/权限/密码/日志
# ============================================================
ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>LanShare 管理面板</title>
<style>""" + _COMMON_CSS + """
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:680px){.grid{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:6px 5px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:500}
.log{max-height:220px;overflow:auto;font-family:ui-monospace,Consolas,monospace;font-size:11px}
.log tr:hover{background:#faf9f5}
.addr{background:#faf9f5;padding:9px 11px;border-radius:8px;margin:5px 0;
  display:flex;justify-content:space-between;align-items:center;gap:8px}
.addr code{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all;flex:1}
.qr{text-align:center;padding:8px}
.qr svg{max-width:170px;height:auto}
.share-item{display:flex;justify-content:space-between;align-items:center;
  padding:8px 0;border-bottom:1px solid var(--line);gap:8px}
.share-item .p{flex:1;font-size:12px;word-break:break-all;color:var(--mut)}
.switch{display:flex;align-items:center;gap:8px}
.dot{width:9px;height:9px;border-radius:50%;background:var(--err);display:inline-block}
.dot.on{background:var(--ok)}
</style></head><body>
<div class="wrap">
  <div class="card">
    <h1>LanShare 管理面板</h1>
    <div class="sub">局域网文件共享 · 控制面板</div>
    <div class="row">
      <div><span class="dot" id="dot"></span> <b id="stTxt">检查中...</b></div>
      <button class="btn" id="btnStart" onclick="svc('start')">启动服务</button>
      <button class="btn gray" id="btnStop" onclick="svc('stop')">停止服务</button>
      <button class="btn gray" onclick="svc('restart')">重启</button>
    </div>
  </div>

  <div class="grid">
    <div>
      <div class="card">
        <h2>共享目录</h2>
        <div id="shares"></div>
        <div class="row" style="margin-top:10px">
          <input id="newPath" placeholder="输入文件夹路径，如 D:\\Media">
          <button class="btn sm" onclick="addShare()">添加</button>
        </div>
        <div class="mut" style="margin-top:6px">提示：可填任意本机文件夹路径</div>
      </div>

      <div class="card">
        <h2>访问地址</h2>
        <div id="addrs"></div>
        <div class="qr" id="qr"></div>
        <div class="row" style="margin-top:8px">
          <button class="btn gray sm" onclick="copyAddr()">复制地址</button>
          <button class="btn gray sm" onclick="openClient()">打开共享页</button>
        </div>
      </div>
    </div>

    <div>
      <div class="card">
        <h2>权限设置</h2>
        <label>其他设备拥有的权限</label>
        <select id="perm" onchange="save()">
          <option value="read">只读（浏览 + 下载）</option>
          <option value="write">可读写（+ 上传 / 新建文件夹）</option>
          <option value="full">完全控制（+ 删除 / 重命名）</option>
        </select>
        <label>端口</label>
        <input id="port" type="number" onchange="save()">
        <label>访问密码（留空 = 免密访问）</label>
        <input id="pwd" type="text" placeholder="设置后其他设备需输入密码" onchange="save()">
        <label>管理员密码（留空 = 仅本机可管理）</label>
        <input id="apwd" type="password" placeholder="留空则仅允许本机管理" onchange="save()">
        <div class="hint">安全建议：在公共网络下务必设置访问密码</div>
      </div>

      <div class="card">
        <h2>系统</h2>
        <div class="row">
          <button class="btn gray sm" onclick="fw('add')">放行防火墙</button>
          <button class="btn gray sm" onclick="fw('del')">关闭防火墙规则</button>
        </div>
        <div class="mut" id="fwMsg" style="margin-top:6px"></div>
        <div class="row" style="margin-top:10px">
          <button class="btn gray sm" onclick="setAuto()">设置开机自启</button>
          <button class="btn gray sm" onclick="openFolder()">打开程序目录</button>
        </div>
        <div class="mut" id="autoMsg" style="margin-top:6px"></div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>访问日志 <button class="btn gray sm" style="float:right" onclick="loadLog()">刷新</button>
      <button class="btn gray sm" style="float:right;margin-right:6px" onclick="clearLog()">清空</button></h2>
    <div class="log"><table><thead><tr><th>时间</th><th>来源 IP</th><th>操作</th><th>路径</th><th>大小</th><th>状态</th></tr></thead>
    <tbody id="logBody"></tbody></table></div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
var ADDRS=[];
function toast(m){var t=document.getElementById('toast');t.textContent=m;t.classList.add('show');
  setTimeout(function(){t.classList.remove('show')},1800);}
function api(u,o){return fetch(u,o||{}).then(function(r){return r.json();});}

function loadCfg(){
  api('/api/admin/config').then(function(c){
    document.getElementById('perm').value=c.permission;
    document.getElementById('port').value=c.port;
    document.getElementById('pwd').value=c.password||'';
    document.getElementById('apwd').value=c.admin_password||'';
    ADDRS=c.addresses||[];
    document.getElementById('addrs').innerHTML=ADDRS.map(function(a){
      return '<div class="addr"><code>http://'+a+':'+c.port+'</code></div>';}).join('');
    document.getElementById('qr').innerHTML=c.qr||'<div class="mut">未安装 qrcode，无法显示二维码</div>';
    renderShares(c.shares);
    loadStatus();
  });
}
function renderShares(s){
  document.getElementById('shares').innerHTML = s.length? s.map(function(x,i){
    return '<div class="share-item"><div><b>'+esc(x.name)+'</b><div class="p">'+esc(x.path)+'</div></div>'+
      '<button class="btn red sm" onclick="delShare('+i+')">移除</button></div>';}).join('')
    : '<div class="mut">尚未添加共享目录</div>';
}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}

function addShare(){
  var p=document.getElementById('newPath').value.trim();
  if(!p){alert('请输入路径');return;}
  api('/api/admin/share/add',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path:p})}).then(function(d){
    d.ok?(document.getElementById('newPath').value='',loadCfg(),toast('已添加')):alert(d.msg||'失败');});
}
function delShare(i){
  api('/api/admin/share/del',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({index:i})}).then(function(d){d.ok?(loadCfg(),toast('已移除')):alert(d.msg||'失败');});
}

function save(){
  api('/api/admin/config',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      permission:document.getElementById('perm').value,
      port:parseInt(document.getElementById('port').value)||8765,
      password:document.getElementById('pwd').value,
      admin_password:document.getElementById('apwd').value
    })}).then(function(d){d.ok?toast('已保存（重启后端口生效）'):alert(d.msg||'保存失败');});
}

function svc(a){
  api('/api/admin/service',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:a})}).then(function(d){
    d.ok?(toast(a==='stop'?'已停止':(a==='start'?'已启动':'已重启')),setTimeout(loadStatus,600)):alert(d.msg||'失败');});
}
function loadStatus(){
  api('/api/admin/status').then(function(d){
    var on=d.running;
    document.getElementById('dot').className='dot'+(on?' on':'');
    document.getElementById('stTxt').textContent=on?('运行中 · 端口 '+d.port):'已停止';
    document.getElementById('btnStart').disabled=on;
    document.getElementById('btnStop').disabled=!on;
  });
}
function fw(a){
  api('/api/admin/firewall',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:a})}).then(function(d){
    document.getElementById('fwMsg').textContent=d.msg||(d.ok?'完成':'失败');});
}
function setAuto(){
  api('/api/admin/autostart',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({enable:true})}).then(function(d){
    document.getElementById('autoMsg').textContent=d.msg||(d.ok?'已设置':'失败');});
}
function openFolder(){api('/api/admin/openfolder',{method:'POST'}).then(function(d){toast(d.msg||'');});}
function copyAddr(){var t=ADDRS.length?'http://'+ADDRS[0]+':'+document.getElementById('port').value:'';
  if(t&&navigator.clipboard)navigator.clipboard.writeText(t).then(function(){toast('已复制：'+t);});}
function openClient(){if(ADDRS.length)window.open('http://'+ADDRS[0]+':'+document.getElementById('port').value,'_blank');}

function loadLog(){
  api('/api/admin/log').then(function(d){
    document.getElementById('logBody').innerHTML=(d.logs||[]).map(function(l){
      return '<tr><td>'+esc(l.time)+'</td><td>'+esc(l.ip)+'</td><td>'+esc(l.method)+'</td>'+
        '<td>'+esc(l.path)+'</td><td>'+esc(l.size||'')+'</td><td>'+esc(l.status)+'</td></tr>';
    }).join('')||'<tr><td colspan="6" class="mut">暂无记录</td></tr>';
  });
}
function clearLog(){api('/api/admin/log',{method:'DELETE'}).then(function(){loadLog();});}
loadCfg();loadLog();setInterval(loadLog,4000);setInterval(loadStatus,5000);
</script></body></html>"""


# ============================================================
# 登录页（访问密码）
# ============================================================
LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>需要验证</title><style>""" + _COMMON_CSS + """
body{display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#fff;padding:26px;border-radius:12px;width:300px;
  border:.5px solid rgba(0,0,0,.1)}
</style></head><body>
<div class="box">
  <h1 style="margin-bottom:4px">需要验证</h1>
  <div class="sub">请输入访问密码</div>
  <form method="post" action="/__login">
    <input type="password" name="password" placeholder="访问密码" autofocus>
    <input type="hidden" name="next" value="__NEXT__">
    <button class="btn" style="width:100%;margin-top:12px">进入</button>
  </form>
  __ERR__
</div></body></html>"""
