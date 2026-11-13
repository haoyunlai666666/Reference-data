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
const zlib = require('zlib');
const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');

const PORT = process.env.PORT || 3001;
const OWNER = 'haoyunlai666666';
const REPO = 'Reference-data';
const GH_TOKEN = process.env.RENDER_GITHUB_TOKEN || '';
const REPORT_TOKEN = process.env.REPORT_TOKEN || '';
const REPORT_JSON_PATH = 'report_v2/output/report.json';
const CATALOG_DIR = 'report_v2/output/catalog';
const PAGE_FILE = path.join(__dirname, 'report.html');

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

function ghRequest(method, ghPath) {
  return new Promise(function (resolve, reject) {
    const options = {
      hostname: 'api.github.com',
      path: ghPath,
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

/* 官方目录检索索引：仓库里的 gzip JSON，内存缓存 30 分钟，避免每次请求都打 GitHub API。 */
const CATALOG_TTL = 30 * 60 * 1000;
const catalogCache = new Map();   // key -> { at, data }
async function loadCatalog(key) {
  if (['chp', 'edqm', 'usp'].indexOf(key) === -1) {
    throw new Error('未知目录：' + key);
  }
  const cached = catalogCache.get(key);
  if (cached && Date.now() - cached.at < CATALOG_TTL) return cached.data;

  const encoded = (CATALOG_DIR + '/' + key + '.json.gz').split('/').map(encodeURIComponent).join('/');
  const res = await ghRequest('GET', '/repos/' + OWNER + '/' + REPO + '/contents/' + encoded);
  if (res.status !== 200) {
    throw new Error('读取官方目录索引失败（HTTP ' + res.status + '）。索引由每日对账工作流生成，请确认工作流已成功运行。');
  }
  const meta = JSON.parse(res.body.toString('utf8'));
  let payload;
  if (meta.content && meta.encoding === 'base64') {
    payload = Buffer.from(meta.content, 'base64');
  } else {
    // 大于 1MB 时 GitHub 不返回 content，改走 blob API
    const blob = await ghRequest('GET', '/repos/' + OWNER + '/' + REPO + '/git/blobs/' + meta.sha);
    if (blob.status !== 200) throw new Error('读取目录索引 blob 失败，HTTP ' + blob.status);
    payload = Buffer.from(JSON.parse(blob.body.toString('utf8')).content, 'base64');
  }
  const data = JSON.parse(zlib.gunzipSync(payload).toString('utf8'));
  catalogCache.set(key, { at: Date.now(), data: data });
  return data;
}

function catalogMeta() {
  const result = {};
  ['chp', 'edqm', 'usp'].forEach(function (key) {
    const hit = catalogCache.get(key);
    result[key] = hit
      ? { total: hit.data.total, generated_at: hit.data.generated_at, label: hit.data.label, short: hit.data.short }
      : null;
  });
  return result;
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
  if (!fs.existsSync(PAGE_FILE)) {
    return res.status(500).send('页面文件缺失：report_v2/report.html');
  }
  res.type('html').send(fs.readFileSync(PAGE_FILE, 'utf8'));
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

/* 只把 error/warn 归为错误；info 级日志单独返回，前端不再误报。 */
app.get('/api/report/status', function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  const errors = serverLogs.filter(function (e) { return e.level === 'error' || e.level === 'warn'; });
  res.json({
    errors: errors,
    logs: serverLogs,
    errorCount: errors.length,
    startedAt: serverLogs.length ? serverLogs[0].time : null
  });
});

app.get('/api/catalog/meta', async function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  try {
    for (const key of ['chp', 'edqm', 'usp']) await loadCatalog(key);
    res.json({ ok: true, sources: catalogMeta() });
  } catch (err) {
    log('warn', 'catalog meta: ' + err.message);
    res.json({ ok: false, sources: catalogMeta(), error: err.message });
  }
});

app.get('/api/catalog/search', async function (req, res) {
  if (!isAuthed(req)) return res.status(401).json({ error: 'unauthorized' });
  const q = String(req.query.q || '').trim().toUpperCase();
  const nameQ = String(req.query.name || '').trim().toUpperCase();
  const lotQ = String(req.query.lot || '').trim().toUpperCase();
  const source = ['chp', 'edqm', 'usp'].indexOf(req.query.source) >= 0 ? req.query.source : 'all';
  let limit = parseInt(req.query.limit, 10) || 100;
  limit = Math.max(1, Math.min(limit, 200));
  let page = parseInt(req.query.page, 10) || 1;
  page = Math.max(1, page);
  if (!q && !nameQ && !lotQ) {
    return res.json({ total: 0, items: [], returned: 0, page: 1, pages: 0, limit: limit, counts: {} });
  }

  const terms = q ? q.split(/\s+/).filter(Boolean) : [];
  const keys = source === 'all' ? ['chp', 'edqm', 'usp'] : [source];
  const items = [];
  const counts = {};
  let total = 0;
  const skip = (page - 1) * limit;
  try {
    for (const key of keys) {
      const cat = await loadCatalog(key);
      let matched = 0;
      for (const row of cat.rows) {
        const nameVal = String(row[cat.name_col] || '').toUpperCase();
        const lotVal = String(row[cat.lot_col] || '').toUpperCase();
        if (nameQ && nameVal.indexOf(nameQ) < 0) continue;
        if (lotQ && lotVal.indexOf(lotQ) < 0) continue;
        let hit = true;
        if (terms.length) {
          const haystack = row.join(' ').toUpperCase();
          for (const term of terms) {
            if (haystack.indexOf(term) < 0) { hit = false; break; }
          }
        }
        if (!hit) continue;
        matched++;
        if (matched > skip && items.length < limit) {
          items.push({
            source: key,
            short: cat.short,
            label: cat.label,
            columns: cat.columns,
            name_col: cat.name_col,
            lot_col: cat.lot_col,
            cells: row
          });
        }
      }
      counts[key] = { total: cat.total, matched: matched };
      total += matched;
    }
    const first = catalogCache.get(keys[0]);
    res.json({
      total: total,
      returned: items.length,
      page: page,
      pages: Math.ceil(total / limit),
      limit: limit,
      query: q,
      name: nameQ,
      lot: lotQ,
      source: source,
      counts: counts,
      items: items,
      generated_at: first ? first.data.generated_at : ''
    });
  } catch (err) {
    log('error', 'catalog search: ' + err.message);
    res.status(500).json({ error: err.message });
  }
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
