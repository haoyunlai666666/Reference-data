const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

// =================== 🛠️ 请填写你的专属配置 ===================
const GITHUB_TOKEN = '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'; 
const REPO_OWNER = 'haoyunlai666666'; // 你的GitHub用户名
const REPO_NAME = 'Reference-data';    // 你的仓库名称
const FILE_PATH = '现有全部对照品目录.xlsx'; // 仓库里保存的严格中文名
// ============================================================

// 支持接收前端大文件
app.use(express.json({limit: '50mb'}));

const htmlContent = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>对照品目录管理系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body, html { width: 100%; height: 100%; overflow: hidden; font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; background: #0f0c1b; }
        #meteorCanvas { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: 1; }
        .card { background: rgba(255, 255, 255, 0.96); padding: 40px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); width: 100%; max-width: 450px; text-align: center; backdrop-filter: blur(8px); z-index: 10; position: relative; }
        h2 { color: #4a5568; margin-bottom: 10px; font-size: 24px; font-weight: 600; }
        .subtitle { color: #718096; font-size: 14px; margin-bottom: 30px; }
        .upload-area { border: 2px dashed #cbd5e0; padding: 30px 20px; border-radius: 12px; background: #f7fafc; cursor: pointer; transition: all 0.3s ease; position: relative; margin-bottom: 25px; }
        .upload-area:hover { border-color: #667eea; background: #edf2f7; }
        .upload-icon { font-size: 40px; margin-bottom: 10px; display: inline-block; }
        input[type="file"] { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
        .file-name-display { font-size: 14px; color: #667eea; margin-top: 10px; font-weight: bold; word-break: break-all; }
        button { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 14px 28px; border-radius: 10px; cursor: pointer; font-size: 16px; font-weight: 600; width: 100%; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); }
        button:hover { opacity: 0.95; }
        #status { margin-top: 20px; font-size: 14px; padding: 10px; border-radius: 8px; display: none; }
        .status-loading { background: #e2e8f0; color: #4a5568; display: block !important; }
        .status-success { background: #c6f6d5; color: #22543d; display: block !important; }
        .status-error { background: #fed7d7; color: #742a2a; display: block !important; }
    </style>
</head>
<body>
    <canvas id="meteorCanvas"></canvas>
    <div class="card">
        <h2>📊 对照品目录管理中心</h2>
        <p class="subtitle">上传后文件将直接安全同步至 GitHub 仓库</p>
        <div class="upload-area">
            <span class="upload-icon">📂</span>
            <p id="uploadText">点击或拖拽 Excel 文件到这里</p>
            <input type="file" id="fileInput" accept=".xlsx, .xls" onchange="showName()">
            <div id="fileNameDisplay" class="file-name-display"></div>
        </div>
        <button onclick="uploadFile()">确认上传更新</button>
        <div id="status"></div>
    </div>
    <script>
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
        function showName() { const input = document.getElementById('fileInput'); const display = document.getElementById('fileNameDisplay'); if(input.files.length > 0) display.innerText = "已选择: " + input.files[0].name; }
        
        async function uploadFile() {
            const input = document.getElementById('fileInput'); const status = document.getElementById('status');
            if (input.files.length === 0) { status.className = "status-error"; status.innerText = "❌ 请先选择一个 Excel 文件！"; return; }
            status.className = "status-loading"; status.innerText = "⏳ 正在直接同步至 GitHub 仓库...";
            
            const file = input.files[0];
            const reader = new FileReader();
            reader.onload = async function(e) {
                const base64Data = e.target.result.split(',')[1];
                try {
                    const response = await fetch('/upload-to-github', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ fileData: base64Data })
                    });
                    if (response.ok) {
                        status.className = "status-success"; status.innerHTML = "✅ 成功直接覆盖 GitHub 仓库文件！数据已实时更新。";
                    } else {
                        const txt = await response.text();
                        status.className = "status-error"; status.innerText = "❌ 同步失败：" + txt;
                    }
                } catch (err) {
                    status.className = "status-error"; status.innerText = "❌ 网络连接失败。";
                }
            };
            reader.readAsDataURL(file);
        }
    </script>
</body>
</html>
`;

app.get('/', (req, res) => res.send(htmlContent));

// 后端直接安全调用 GitHub API 进行强行存盘覆盖
app.post('/upload-to-github', async (req, res) => {
    const { fileData } = req.body;
    if (!fileData) return res.status(400).send('No file data received');

    try {
        const fetch = (...args) => import('node-fetch').then(({default: fetch}) => fetch(...args));
        const url = `https://github.com{REPO_OWNER}/${REPO_NAME}/contents/${encodeURIComponent(FILE_PATH)}`;
        
        // 1. 先去查一下 GitHub 上现有文件的 sha 标识（Git覆盖必须要带sha）
        const getRes = await fetch(url, {
            headers: { 'Authorization': `token ${GITHUB_TOKEN}`, 'User-Agent': 'Render-App' }
        });
        
        let sha = null;
        if (getRes.ok) {
            const getJson = await getRes.json();
            sha = getJson.sha;
        }

        // 2. 直接强行向 GitHub 发起 Commit 覆盖
        const putRes = await fetch(url, {
            method: 'PUT',
            headers: {
                'Authorization': `token ${GITHUB_TOKEN}`,
                'Content-Type': 'application/json',
                'User-Agent': 'Render-App'
            },
            body: JSON.stringify({
                message: '📊 网页端实时更新：现有全部对照品目录',
                content: fileData,
                sha: sha
            })
        });

        if (putRes.ok) {
            return res.status(200).send('OK');
        } else {
            const errText = await putRes.text();
            return res.status(putRes.status).send(errText);
        }
    } catch (error) {
        return res.status(500).send(error.message);
    }
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
