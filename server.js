const express = require('express');
const app = express();
const XLSX = require('xlsx'); // 用于在后台无损解析和重组真 Excel 二进制文件
const PORT = process.env.PORT || 3000;

// =================== 🔒 专属配置安全锁 ===================
const GITHUB_TOKEN = process.env.RENDER_GITHUB_TOKEN; 
// =======================================================

// 支持接收前端大文件，调高限制以防大 Excel 数据包超载
app.use(express.json({limit: '50mb'}));

const htmlContent = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
 <meta charset="UTF-8">
 <meta name="viewport" content="width=device-width, initial-scale=1.0">
 <title>对照品目录管理系统</title>
 <!-- 引入网页版 Excel 控件的核心样式与脚本 -->
 <link rel="stylesheet" href="https://unpkg.com/x-data-spreadsheet@1.1.9/dist/xspreadsheet.css">
 <script src="https://unpkg.com/x-data-spreadsheet@1.1.9/dist/xspreadsheet.js"></script>
 <style>
 * { box-sizing: border-box; margin: 0; padding: 0; }
 body, html { width: 100%; height: 100%; overflow: hidden; font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; background: #0f0c1b; }
 #meteorCanvas { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }
 
 /* 卡片基础样式：支持随选项动态拉伸变宽 */
 .card { background: rgba(255, 255, 255, 0.96); padding: 30px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 450px; text-align: center; backdrop-filter: blur(8px); z-index: 10; position: relative; transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1); }
 .card.wide-mode { max-width: 95vw; width: 1200px; }
 
 h2 { color: #4a5568; margin-bottom: 5px; font-size: 24px; font-weight: 600; }
 .subtitle { color: #718096; font-size: 14px; margin-bottom: 20px; }
 
 /* 选项卡导航栏 */
 .tabs { display: flex; background: #edf2f7; padding: 4px; border-radius: 10px; margin-bottom: 25px; }
 .tab-btn { flex: 1; border: none; background: none; padding: 10px; font-size: 14px; font-weight: 600; color: #4a5568; cursor: pointer; border-radius: 8px; transition: all 0.2s; }
 .tab-btn.active { background: white; color: #667eea; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
 
 /* 容器面板受控显示/隐藏 */
 .panel { display: none; }
 .panel.active { display: block; }
 
 /* 本地上传文件 UI 界面（完美保留） */
 .upload-area { border: 2px dashed #cbd5e0; padding: 30px 20px; border-radius: 12px; background: #f7fafc; cursor: pointer; transition: all 0.3s ease; position: relative; margin-bottom: 25px; }
 .upload-area:hover { border-color: #667eea; background: #edf2f7; }
 .upload-icon { font-size: 40px; margin-bottom: 10px; display: inline-block; }
 input[type="file"] { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
 .file-name-display { font-size: 14px; color: #667eea; margin-top: 10px; font-weight: bold; word-break: break-all; }
 
 /* 在线编辑器工作区 */
 #editorContainer { width: 100%; height: 450px; background: #fff; border: 1px solid #cbd5e0; border-radius: 8px; overflow: hidden; margin-bottom: 20px; text-align: left; }
 
 button.action-btn { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 28px; border-radius: 10px; cursor: pointer; font-size: 16px; font-weight: 600; width: 100%; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); }
 button.action-btn:hover { opacity: 0.95; }
 
 #status { margin-top: 20px; font-size: 14px; padding: 10px; border-radius: 8px; display: none; }
 .status-loading { background: #e2e8f0; color: #4a5568; display: block !important; }
 .status-success { background: #c6f6d5; color: #22543d; display: block !important; }
 .status-error { background: #fed7d7; color: #742a2a; display: block !important; }
 </style>
</head>
<body>
 <canvas id="meteorCanvas"></canvas>
 <div class="card" id="mainCard">
 <h2> 对照品目录管理中心</h2>
 <p class="subtitle">数据直接与 GitHub 仓库安全实时同步</p>
 
 <!-- 选项卡按钮组 -->
 <div class="tabs">
 <button id="btn-upload" class="tab-btn active" onclick="switchTab('upload')">📁 本地文件上传</button>
 <button id="btn-edit" class="tab-btn" onclick="switchTab('edit')">📝 在线查看编辑</button>
 </div>
 
 <!-- 面板 1：完美保留的原上传界面 -->
 <div id="uploadPanel" class="panel active">
 <div class="upload-area">
 <span class="upload-icon">📁</span>
 <p id="uploadText">点击或拖拽 Excel 文件到这里</p>
 <input type="file" id="fileInput" accept=".xlsx, .xls" onchange="showName()">
 <div id="fileNameDisplay" class="file-name-display"></div>
 </div>
 <button class="action-btn" onclick="uploadFile()">确认上传更新</button>
 </div>
 
 <!-- 面板 2：全新的在线编辑工作区 -->
 <div id="editPanel" class="panel">
 <div id="editorContainer"></div>
 <button class="action-btn" onclick="saveOnlineData()">保存并同步至 GitHub</button>
 </div>
 
 <div id="status"></div>
 </div>
 
 <script>
 // --- 完美保留的流星雨背景特效逻辑 ---
 const canvas = document.getElementById('meteorCanvas'); const ctx = canvas.getContext('2d');
 function resizeCanvas() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
 window.addEventListener('resize', resizeCanvas); resizeCanvas();
 class Meteor {
 constructor() { this.reset(); this.x = Math.random() * canvas.width; this.y = Math.random() * canvas.height; }
 reset() { this.length = Math.random() * 80 + 50; this.speedX = (Math.random() * 2 + 1.5) * (Math.random() > 0.5 ? 1 : -1); this.speedY = (Math.random() * 2 + 1.5) * (Math.random() > 0.5 ? 1 : -1); this.width = Math.random() * 2 + 1; }
 update() { this.x += this.speedX; this.y += this.speedY; if (this.x < 0 || this.x > canvas.width) this.speedX *= -1; if (this.y < 0 || this.y > canvas.height) this.speedY *= -1; }
 draw() {
 const speedObj = Math.sqrt(this.speedX * this.speedX + this.speedY * this.speedY);
 const tailX = this.x - (this.speedX / speedObj) * this.length; const tailY = this.y - (this.speedY / speedObj) * this.length;
 const gradient = ctx.createLinearGradient(this.x, this.y, tailX, tailY);
 gradient.addColorStop(0, 'rgba(255, 255, 255, 1)'); gradient.addColorStop(0.1, 'rgba(118, 75, 162, 0.8)'); gradient.addColorStop(0.6, 'rgba(102, 126, 234, 0.3)'); gradient.addColorStop(1, 'rgba(15, 12, 27, 0)');
 ctx.beginPath(); ctx.strokeStyle = gradient; ctx.lineWidth = this.width; ctx.lineCap = 'round'; ctx.moveTo(this.x, this.y); ctx.lineTo(tailX, tailY); ctx.stroke();
 }
 }
 const meteors = []; for (let i = 0; i < 15; i++) meteors.push(new Meteor());
 function animate() {
 const skyGrad = ctx.createLinearGradient(0, 0, canvas.width, canvas.height); skyGrad.addColorStop(0, '#0f0c20'); skyGrad.addColorStop(0.5, '#15102a'); skyGrad.addColorStop(1, '#06040a'); ctx.fillStyle = skyGrad; ctx.fillRect(0, 0, canvas.width, canvas.height);
 meteors.forEach(meteor => { meteor.update(); meteor.draw(); }); requestAnimationFrame(animate);
 }
 animate();
 
 // --- 完美保留的文件名展示逻辑 ---
 function showName() { 
 const input = document.getElementById('fileInput'); 
 const display = document.getElementById('fileNameDisplay'); 
 if(input.files.length > 0) display.innerText = "已选择: " + input.files[0].name; 
 }
 
 // --- 选项卡切换核心联动 ---
 let spreadsheetInstance = null; 
 function switchTab(type) {
 const card = document.getElementById('mainCard');
 const uploadPanel = document.getElementById('uploadPanel');
 const editPanel = document.getElementById('editPanel');
 const btnUpload = document.getElementById('btn-upload');
 const btnEdit = document.getElementById('btn-edit');
 const status = document.getElementById('status');
 // ✅ 修复：清除状态栏的所有类名，破除 !important 的强制显示效果
 status.className = ""; 
 status.style.display = 'none';
 
 if (type === 'upload') {
 card.classList.remove('wide-mode');
 btnUpload.classList.add('active'); btnEdit.classList.remove('active');
 uploadPanel.classList.add('active'); editPanel.classList.remove('active');
 } else {
 card.classList.add('wide-mode');
 btnUpload.classList.remove('active'); btnEdit.classList.add('active');
 uploadPanel.classList.remove('active'); editPanel.classList.add('active');
 // 切换到编辑面板时，拉取最新的 GitHub 数据进行前端表格加载
 loadGitHubDataOnline();
 }
 }
 
 // --- 功能一：完美保留的本地文件强行上传功能 ---
 async function uploadFile() {
 const input = document.getElementById('fileInput'); const status = document.getElementById('status');
 if (input.files.length === 0) { status.className = "status-error"; status.innerText = " 请先选择一个 Excel 文件！"; return; }
 status.className = "status-loading"; status.innerText = " 正在直接同步至 GitHub 仓库...";
 const file = input.files[0]; const reader = new FileReader();
 reader.onload = async function(e) {
 const base64Data = e.target.result.split(',')[1];
 try {
 const response = await fetch('/upload-to-github', {
 method: 'POST',
 headers: { 'Content-Type': 'application/json' },
 body: JSON.stringify({ fileData: base64Data })
 });
 if (response.ok) { status.className = "status-success"; status.innerHTML = " 成功直接覆盖 GitHub 仓库文件！数据已实时更新。"; } 
 else { const txt = await response.text(); status.className = "status-error"; status.innerText = " 同步失败：" + txt; }
 } catch (err) { status.className = "status-error"; status.innerText = " 网络连接失败。"; }
 };
 reader.readAsDataURL(file);
 }
 
 // --- 功能二：在线获取并加载 Excel 数据 ---
 async function loadGitHubDataOnline() {
 const status = document.getElementById('status');
 const container = document.getElementById('editorContainer');
 container.innerHTML = ""; 
 status.className = "status-loading"; status.innerText = " 正在从 ⚙️ GitHub 云端提取并解析最新对照品数据...";
 
 try {
 const response = await fetch('/get-github-excel-json');
 if (!response.ok) throw new Error(await response.text());
 const excelJsonData = await response.json();
 
 // ✅ 彻底修复：采用全局绝对安全的全局对象注册语法，确保 CDN 100% 能够实例化
 spreadsheetInstance = new x_spreadsheet('#editorContainer', {
 showToolbar: true, showGrid: true, showContextmenu: true,
 view: { height: () => 450, width: () => container.clientWidth }
 }).loadData(excelJsonData);
 
 status.style.display = 'none'; 
 } catch (err) {
 status.className = "status-error"; status.innerText = " 无法加载云端数据：" + err.message;
 }
 }
 
 // --- 功能三：在线表格改动后一键封包提交覆盖 ---
 async function saveOnlineData() {
 if (!spreadsheetInstance) return;
 const status = document.getElementById('status');
 status.className = "status-loading"; status.innerText = " 正在打包网页格数据并强行同步至 GitHub...";
 
 try {
              const response = await fetch('/upload-online-to-github', {
                 method: 'POST',
                 headers: { 'Content-Type': 'application/json' },
                 body: JSON.stringify({ gridData: spreadsheetInstance.getData() })
             });
             if (response.ok) {
                 status.className = "status-success"; status.innerHTML = " 🎉 网页端修改已完美覆写 GitHub 仓库！数据已实时变动。";
             } else {
                 status.className = "status-error"; status.innerText = " 在线同步失败：" + (await response.text());
             }
         } catch (err) {
             status.className = "status-error"; status.innerText = " 网络连接异常。";
         }
     }
 </script>
</body>
</html>
`;

app.get('/', (req, res) => res.send(htmlContent));
// 原生网络通信公用配置封装（独立安全层）
const makeGitHubRequest = (method, path, bodyData = null) => {
    return new Promise((resolve, reject) => {
        const https = require('https');
        const options = {
            hostname: 'api.github.com', // ✅ 真正修正：纯净无暇的官方专用 API 域名，绝无任何 :// 符号
            path: path,
            method: method,
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
                'Accept': 'application/vnd.github+json'
            }
        };
        const reqHttp = https.request(options, (resHttp) => {
            let data = Buffer.alloc(0);
            resHttp.on('data', chunk => data = Buffer.concat([data, chunk]));
            resHttp.on('end', () => resolve({ status: resHttp.statusCode, data: data }));
        });
        reqHttp.on('error', err => reject(err));
        if (bodyData) reqHttp.write(JSON.stringify(bodyData));
        reqHttp.end();
    });
};

// 接口 1：本地大文件 Base64 覆盖通道（路径硬编码，绝对安全锁）
app.post('/upload-to-github', async (req, res) => {
    const { fileData } = req.body;
    if (!fileData) return res.status(400).send('No file data received');
    try {
        const securePath = `/repos/haoyunlai666666/Reference-data/contents/${encodeURIComponent('现有全部对照品目录.xlsx')}`;
        const getRes = await makeGitHubRequest('GET', securePath);
        let sha = null;
        if (getRes.status === 200) sha = JSON.parse(getRes.data.toString()).sha;
        const putRes = await makeGitHubRequest('PUT', securePath, {
            message: '📊 网页端实时更新：现有全部对照品目录',
            content: fileData,
            sha: sha
        });
        return res.status(putRes.status === 200 || putRes.status === 201 ? 200 : putRes.status).send(putRes.data.toString());
    } catch (e) { return res.status(500).send(e.message); }
});

// 接口 2：获取 GitHub 上的 Excel 原始二进制并转化为前端格子 JSON （路径硬编码，绝对安全锁）
app.get('/get-github-excel-json', async (req, res) => {
    try {
        const securePath = `/repos/haoyunlai666666/Reference-data/contents/${encodeURIComponent('现有全部对照品目录.xlsx')}`;
        const getRes = await makeGitHubRequest('GET', securePath);
        if (getRes.status !== 200) return res.status(getRes.status).send("无法在仓库中找到对应的核心 Excel 文件");
        
        const fileMeta = JSON.parse(getRes.data.toString());
        const excelBuffer = Buffer.from(fileMeta.content, 'base64');
        
        const workbook = XLSX.read(excelBuffer, { type: 'buffer' });
        const resultSheets = [];
        
        workbook.SheetNames.forEach(name => {
            const sheet = workbook.Sheets[name];
            const json = XLSX.utils.sheet_to_json(sheet, { header: 1 });
            const rows = {};
            const cols = {}; // ✅ 新增：用于记录每列的最大宽度
            
            json.forEach((r, rIdx) => {
                const cells = {};
                r.forEach((c, cIdx) => {
                    // 确保内容转为字符串处理
                    const text = c !== undefined && c !== null ? String(c) : "";
                    cells[cIdx] = { text: text };
                    
                    // ✅ 计算字符大概的像素宽度（中文按两倍宽度计算）
                    const charLen = text.replace(/[\u0391-\uFFE5]/g, "aa").length;
                    // 基础宽度 100，每个字符约 8 像素，外加 16 像素边距；限制最大列宽为 500px 防止过长
                    const estimatedWidth = Math.min(Math.max(100, charLen * 8 + 16), 500);
                    
                    // 比较并记录该列的最大宽度
                    if (!cols[cIdx] || estimatedWidth > cols[cIdx].width) {
                        cols[cIdx] = { width: estimatedWidth };
                    }
                });
                rows[rIdx] = { cells };
            });
            // ✅ 将 cols 对象一并推送到前端
            resultSheets.push({ name: name, rows: rows, cols: cols });
        });
        return res.json(resultSheets.length ? resultSheets : [{ name: "Sheet1", rows: {} }]);
    } catch (e) { return res.status(500).send(e.message); }
});

// 接口 3：将在线表格改动的数据重新还原封包发送给 GitHub （路径硬编码，绝对安全锁）
app.post('/upload-online-to-github', async (req, res) => {
    const { gridData } = req.body;
    if (!gridData) return res.status(400).send('No grid data received');
    try {
        const workbook = XLSX.utils.book_new();
        
        gridData.forEach(sheetData => {
            const matrix = [];
            const rows = sheetData.rows;
            Object.keys(rows).forEach(rIdx => {
                if (rIdx === 'len') return;
                const row = [];
                const cells = rows[rIdx].cells;
                Object.keys(cells).forEach(cIdx => {
                    if (cells[cIdx] && cells[cIdx].text !== undefined) {
                        row[parseInt(cIdx)] = cells[cIdx].text;
                    }
                });
                matrix[parseInt(rIdx)] = row;
            });
            const ws = XLSX.utils.aoa_to_sheet(matrix);
            XLSX.utils.book_append_sheet(workbook, ws, sheetData.name || "Sheet1");
        });
        
        const excelBuffer = XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' });
        const base64Data = excelBuffer.toString('base64');
        const securePath = `/repos/haoyunlai666666/Reference-data/contents/${encodeURIComponent('现有全部对照品目录.xlsx')}`;
        const getRes = await makeGitHubRequest('GET', securePath);
        let sha = null;
        if (getRes.status === 200) sha = JSON.parse(getRes.data.toString()).sha;
        const putRes = await makeGitHubRequest('PUT', securePath, {
            message: '📝 网页端在线表格实时修改更新',
            content: base64Data,
            sha: sha
        });
        return res.status(putRes.status === 200 || putRes.status === 201 ? 200 : putRes.status).send(putRes.data.toString());
    } catch (e) { return res.status(500).send(e.message); }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));


