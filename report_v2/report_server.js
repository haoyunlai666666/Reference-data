'use strict';

/* 对照品对账查询网页（独立服务，不改动根目录 server.js）。
 * 环境变量：
 *   RENDER_GITHUB_TOKEN  具备 contents:read 与 actions:read 的 GitHub 令牌
 *   REPORT_TOKEN         网页访问口令（不设置则拒绝服务）
 *   PORT                 默认 3001
 * 启动：node report_v2/report_server.js
 */

const express = require('express');
const https = require('https');
const crypto = require('crypto');
const AdmZip = require('adm-zip');

const PORT = process.env.PORT || 3001;
const OWNER = 'haoyunlai666666';
const REPO = 'Reference-data';
const GH_TOKEN = process.env.RENDER_GITHUB_TOKEN || '';
const REPORT_TOKEN = process.env.REPORT_TOKEN || '';
const REPORT_JSON_PATH = 'report_v2/output/report.json';

const app = express();
app.disable('x-powered-by');

const serverLogs = [];
function log(level, message) {
  const entry = {
    time: new Date().toISOString(),
    level: level,
    message: String(message).slice(0, 500)
  };
  serverLogs.push(entry);
  if (serverLogs.length > 60) serverLogs.shift();
  console.log('[' + entry.time + '] ' + level + ' ' + entry.message);
}

function authValue() {
  return crypto.createHash('sha256').update('report_v2|' + REPORT_TOKEN).digest('hex');
}

function isAuthed(req) {
  if (!REPORT_TOKEN) return false;
  const cookies = (req.headers.cookie || '').split(';');
  return cookies.some(function (c) { return c.trim() === 'report_auth=' + authValue(); });
}

function ghRequest(method, path) {
  return new Promise(function (resolve, reject) {
    const options = {
      hostname: 'api.github.com',
      path: path,
      method: method,
      headers: {
        'Authorization': 'Bearer ' + GH_TOKEN,
        'User-Agent': 'reference-report-v2',
        'Accept': 'application/vnd.github+json'
      }
    };
    const req = https.request(options, function (res) {
      const chunks = [];
      res.on('data', function (c) { chunks.push(c); });
      res.on('end', function () {
        resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) });
      });
    });
    req.on('error', reject);
    req.setTimeout(30000, function () { req.destroy(new Error('GitHub API timeout')); });
    req.end();
  });
}

function httpsGetBuffer(urlString) {
  return new Promise(function (resolve, reject) {
    const target = new URL(urlString);
    const req = https.get({
      hostname: target.hostname,
      path: target.pathname + target.search,
      headers: { 'User-Agent': 'reference-report-v2' }
    }, function (res) {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        httpsGetBuffer(res.headers.location).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        res.resume();
        reject(new Error('构件下载返回 HTTP ' + res.statusCode));
        return;
      }
      const chunks = [];
      res.on('data', function (c) { chunks.push(c); });
      res.on('end', function () { resolve(Buffer.concat(chunks)); });
    });
    req.on('error', reject);
    req.setTimeout(60000, function () { req.destroy(new Error('artifact download timeout')); });
  });
}

async function loadReport() {
  const encoded = REPORT_JSON_PATH.split('/').map(encodeURIComponent).join('/');
  const res = await ghRequest('GET', '/repos/' + OWNER + '/' + REPO + '/contents/' + encoded);
  if (res.status !== 200) {
    throw new Error('读取 report.json 失败，HTTP ' + res.status + '：' + res.body.toString().slice(0, 200));
  }
  const meta = JSON.parse(res.body.toString('utf8'));
  return JSON.parse(Buffer.from(meta.content, 'base64').toString('utf8'));
}

function htmlPage() {
  return `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>对照品对账查询</title><style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,"Microsoft YaHei",sans-serif;background:#f5f7fa;color:#1f2937}
.wrap{max-width:1080px;margin:0 auto;padding:24px}h1{font-size:22px;margin:0 0 4px}
.sub{color:#6b7280;font-size:13px;margin-bottom:20px}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px}
.badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:500}
.ok{background:#e8f5e9;color:#1b5e20}.warn{background:#fff4e5;color:#8a5000}.err{background:#fdecea;color:#a32020}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-top:14px}
.kv{background:#f9fafb;border-radius:8px;padding:12px}.kv b{display:block;font-size:20px;margin-top:4px}
.kv span{font-size:12px;color:#6b7280}
.tabs{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.tab{border:1px solid #d1d5db;background:#fff;border-radius:8px;padding:8px 16px;cursor:pointer;font-size:14px}
.tab.active{background:#2563eb;color:#fff;border-color:#2563eb}
input[type=text]{width:100%;padding:10px;border:1px solid #d1d5db;border-radius:8px;font-size:14px;margin-bottom:12px}
.btn{display:inline-block;background:#2563eb;color:#fff;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:14px;margin-right:8px;margin-top:8px}
.btn.gray{background:#6b7280}ul{margin:8px 0;padding-left:20px}li{margin:4px 0;font-size:14px}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto;font-size:12px;max-height:260px}
.muted{color:#6b7280;font-size:13px}
</style></head><body><div class="wrap">
<h1>对照品对账查询</h1><div class="sub" id="meta">正在加载…</div>
<div class="card"><div id="summary">加载中…</div><div class="grid" id="stats"></div></div>
<div class="card"><div class="tabs" id="tabs"></div>
<input type="text" id="search" placeholder="输入品名或批号筛选当前库的未匹配清单">
<div id="downloads"></div><div id="list"></div></div>
<div class="card"><h3 style="margin-top:0;font-size:16px">运行状态与日志</h3><div id="status" class="muted">加载中…</div></div>
</div><script>
var DATA=null,ACTIVE="chp",KEYS=["chp","edqm","usp"];
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c]})}
function badge(st){var m={ok:["ok","全部一致"],warning:["warn","发现未匹配"],error:["err","部分任务失败"]};var v=m[st]||["err",st];return "<span class=\\"badge "+v[0]+"\\">"+v[1]+"</span>"}
function renderSummary(){document.getElementById("meta").textContent="生成时间："+(DATA.generated_at||"-")+" · 数据日期："+(DATA.date||"-");
document.getElementById("summary").innerHTML="<h3 style=\\"margin:0;font-size:16px\\">对账结论 "+badge(DATA.status)+"</h3>";
var s=DATA.summary||{};
document.getElementById("stats").innerHTML=
"<div class=\\"kv\\"><span>未匹配合计</span><b>"+(s.missing_total||0)+"</b></div>"+
"<div class=\\"kv\\"><span>单库失败</span><b>"+(s.error_total||0)+"</b></div>"+
"<div class=\\"kv\\"><span>成功比对库</span><b>"+(KEYS.length-(s.error_total||0))+"</b></div>"+
"<div class=\\"kv\\"><span>日志错误</span><b>"+(s.log_error_total||0)+"</b></div>"+
"<div class=\\"kv\\"><span>原始文件</span><b>"+((DATA.files||[]).length)+"</b></div>"}
function renderTabs(){var h="";KEYS.forEach(function(k){var d=DATA.sources[k]||{};h+="<button class=\\"tab "+(k===ACTIVE?"active":"")+"\\" data-k=\\""+k+"\\">"+esc(d.label||k)+"</button>"});
document.getElementById("tabs").innerHTML=h;
Array.prototype.forEach.call(document.querySelectorAll(".tab"),function(b){b.onclick=function(){ACTIVE=b.getAttribute("data-k");renderTabs();renderList()}})}
function renderDownloads(){var h="";(DATA.files||[]).forEach(function(f){h+="<a class=\\"btn\\" href=\\"/api/report/download/"+f.key+"\\">下载 "+esc(f.label)+" 原始 Excel</a>"});
if(!h){h="<span class=\\"muted\\">本次运行未生成原始 Excel 文件。</span>"}document.getElementById("downloads").innerHTML=h}
function renderList(){var d=DATA.sources[ACTIVE]||{},q=document.getElementById("search").value.trim().toUpperCase();
var h="";if(!d.ok){h+="<p style=\\"color:#a32020\\">该库未比对（官方目录抓取或读取失败）："+esc(d.error||"未知错误")+"</p>"}
else if(d.skipped){h+="<p style=\\"color:#8a5000\\">"+esc(d.note||"基准表无数据，未执行比对")+"</p>"}
else if(!(d.missing||[]).length){h+="<p class=\\"muted\\">"+(d.note?esc(d.note)+"（核对 "+(d.checked||0)+" 条，未匹配 0 条）":"该库未发现未匹配品种。")+"</p>"}
else{
var items=d.missing.filter(function(x){return !q||x.toUpperCase().indexOf(q)>=0});h+="<p class=\\"muted\\">未匹配 "+(d.missing.length)+" 条，当前显示 "+items.length+" 条</p><ul>";
items.forEach(function(x){h+="<li>"+esc(x)+"</li>"});h+="</ul>"}document.getElementById("list").innerHTML=h}
function renderStatus(){fetch("/api/report/status").then(function(r){return r.json()}).then(function(s){
var h="<p>服务端错误记录 "+((s.serverLogs||[]).length)+" 条</p>";
var errs=(DATA.log_errors||[]).concat(s.serverLogs||[]);
if(!errs.length){h+="<p class=\\"muted\\">未发现运行错误。</p>"}else{h+="<pre>";errs.slice(-30).forEach(function(e){h+=esc((e.file?e.file+":"+e.line+" ":"")+(e.text||e.message||""))+"\\n"});h+="</pre>"}
document.getElementById("status").innerHTML=h}).catch(function(e){document.getElementById("status").textContent="状态读取失败："+e.message})}
function loadReport(tryNo){
fetch("/api/report/data").then(function(r){if(!r.ok){throw new Error("HTTP "+r.status)}return r.json()}).then(function(d){DATA=d;
renderSummary();renderTabs();renderDownloads();renderList();renderStatus()}).catch(function(e){
if(tryNo<10){
document.getElementById("meta").textContent="服务可能正在唤醒（Render 免费实例冷启动约 1 分钟），第 "+tryNo+"/10 次重试中…（"+e.message+"）";
setTimeout(function(){loadReport(tryNo+1)},8000);
}else{
document.getElementById("summary").innerHTML="<span style=\\"color:#a32020\\">报告加载失败："+esc(e.message)+"</span>";
document.getElementById("meta").textContent="已重试多次仍失败：请检查 Render 服务是否在线、工作流是否已运行且 report.json 已提交到仓库"}});}
loadReport(1);
document.getElementById("search").addEventListener("input",function(){if(DATA){renderList()}});
</script></body></html>`;
}

app.get('/health', function (req, res) {
  res.json({ ok: true, tokenConfigured: Boolean(REPORT_TOKEN), githubTokenConfigured: Boolean(GH_TOKEN) });
});

app.get('/', function (req, res) { res.redirect('/report'); });

app.get('/report', function (req, res) {
  if (!REPORT_TOKEN) {
    return res.status(503).send('未配置 REPORT_TOKEN，服务拒绝提供报告页。请先在环境变量中设置访问口令。');
  }
  if (req.query.key && req.query.key === REPORT_TOKEN) {
    res.setHeader('Set-Cookie', 'report_auth=' + authValue() + '; HttpOnly; SameSite=Lax; Path=/; Max-Age=2592000');
    return res.redirect('/report');
  }
  if (!isAuthed(req)) {
    return res.status(401).send('<meta charset="utf-8"><p>需要访问口令。请在链接后加上 ?key=你的口令 后打开。</p>');
  }
  res.type('html').send(htmlPage());
});

app.get('/api/report/data', async function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  try {
    res.json(await loadReport());
  } catch (err) {
    log('error', 'loadReport: ' + err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/report/status', function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  res.json({ serverLogs: serverLogs });
});

app.get('/api/report/download/:key', async function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  const key = req.params.key;
  if (['chp', 'edqm', 'usp'].indexOf(key) === -1) {
    return res.status(400).json({ error: 'unknown source key' });
  }
  try {
    const report = await loadReport();
    if (!report.run_id) {
      return res.status(400).json({ error: '报告中缺少 run_id，无法定位构件' });
    }
    const listRes = await ghRequest(
      'GET', '/repos/' + OWNER + '/' + REPO + '/actions/runs/' + report.run_id + '/artifacts'
    );
    if (listRes.status !== 200) {
      throw new Error('构件列表读取失败，HTTP ' + listRes.status);
    }
    const list = JSON.parse(listRes.body.toString('utf8'));
    const artifact = (list.artifacts || []).find(function (a) {
      return a.name === (report.artifact_name || 'reference-excels') && !a.expired;
    });
    if (!artifact) {
      return res.status(410).json({ error: '原始 Excel 已超过 7 天保留期或构件尚未上传' });
    }
    const zipRes = await ghRequest(
      'GET', '/repos/' + OWNER + '/' + REPO + '/actions/artifacts/' + artifact.id + '/zip'
    );
    if (zipRes.status !== 302 || !zipRes.headers.location) {
      throw new Error('构件下载未返回重定向地址，HTTP ' + zipRes.status);
    }
    const buffer = await httpsGetBuffer(zipRes.headers.location);
    const zip = new AdmZip(buffer);
    const entry = zip.getEntries().find(function (e) {
      if (e.isDirectory) return false;
      return e.entryName.split('/').pop().indexOf(key + '_') === 0;
    });
    if (!entry) {
      throw new Error('构件内未找到以 ' + key + '_ 开头的原始文件');
    }
    const name = entry.entryName.split('/').pop();
    res.setHeader('Content-Type', name.endsWith('.xls') ? 'application/vnd.ms-excel' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', "attachment; filename*=UTF-8''" + encodeURIComponent(name));
    log('info', 'download ' + name + ' (' + entry.header.size + ' bytes)');
    res.send(entry.getData());
  } catch (err) {
    log('error', 'download ' + key + ': ' + err.message);
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, function () {
  log('info', 'report server listening on ' + PORT);
  if (!REPORT_TOKEN) log('warn', 'REPORT_TOKEN 未配置，报告页将返回 503');
  if (!GH_TOKEN) log('warn', 'RENDER_GITHUB_TOKEN 未配置，无法读取报告数据');
});
