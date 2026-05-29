const express = require('express');
const multer = require('multer');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// 1. 配置存储：无论别人上传什么名字，云端永远存为 “现有全部对照品目录.xlsx”
const storage = multer.diskStorage({
    destination: function (req, file, cb) {
        cb(null, __dirname); 
    },
    filename: function (req, file, cb) {
        cb(null, '现有全部对照品目录.xlsx'); 
    }
});
const upload = multer({ storage: storage });

// 2. 将高颜值、带流星反弹特效的网页写在后端代码里输出
const htmlContent = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>对照品目录管理系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body, html { 
            width: 100%;
            height: 100%;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            background: #0f0c1b; 
        }
        
        /* 动态背景画布 */
        #meteorCanvas {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }

        /* 中间白色卡片，不受背景影响 */
        .card { 
            background: rgba(255, 255, 255, 0.96); 
            padding: 40px; 
            border-radius: 20px; 
            box-shadow: 0 15px 35px rgba(0,0,0,0.3); 
            width: 100%; 
            max-width: 450px; 
            text-align: center;
            backdrop-filter: blur(8px);
            z-index: 10; 
            position: relative;
        }
        
        h2 { color: #4a5568; margin-bottom: 10px; font-size: 24px; font-weight: 600; }
        .subtitle { color: #718096; font-size: 14px; margin-bottom: 30px; }
        
        .upload-area {
            border: 2px dashed #cbd5e0; padding: 30px 20px; border-radius: 12px;
            background: #f7fafc; cursor: pointer; transition: all 0.3s ease; position: relative; margin-bottom: 25px;
        }
        .upload-area:hover { border-color: #667eea; background: #edf2f7; }
        .upload-icon { font-size: 40px; margin-bottom: 10px; display: inline-block; }
        input[type="file"] { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
        .file-name-display { font-size: 14px; color: #667eea; margin-top: 10px; font-weight: bold; word-break: break-all; }
        
        button { 
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
            color: white; border: none; padding: 14px 28px; border-radius: 10px; cursor: pointer; 
            font-size: 16px; font-weight: 600; width: 100%; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        button:hover { opacity: 0.95; }
        #status { margin-top: 20px; font-size: 14px; padding: 10px; border-radius: 8px; display: none; }
        .status-loading { background: #e2e8f0; color: #4a5568; display: block !important; }
        .status-success { background: #c6f6d5; color: #22543d; display: block !important; }
        .status-error { background: #fed7d7; color: #742a2a; display: block !important; }
    </style>
</head>
<body>

    <!-- 炫酷反弹流星画布 -->
    <canvas id="meteorCanvas"></canvas>

    <!-- 中央控制面板 -->
    <div class="card">
        <h2>📊 对照品目录管理中心</h2>
        <p class="subtitle">任何人上传的文件，云端都将自动覆盖并固定保存</p>
        <div class="upload-area">
            <span class="upload-icon">📂</span>
            <p id="uploadText">点击或拖拽 Excel 文件到这里</p>
            <input type="file" id="fileInput" accept=".xlsx, .xls" onchange="showName()">
            <div id="fileNameDisplay" class="file-name-display"></div>
        </div>
        <button onclick="uploadFile()">确认上传更新</button>
        <div id="status"></div>
    </div>

    <!-- 流星碰撞反弹物理引擎脚本 -->
    <script>
        const canvas = document.getElementById('meteorCanvas');
        const ctx = canvas.getContext('2d');

        function resizeCanvas() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();

        class Meteor {
            constructor() {
                this.reset();
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
            }

            reset() {
                this.length = Math.random() * 80 + 50; 
                this.speedX = (Math.random() * 2 + 1.5) * (Math.random() > 0.5 ? 1 : -1); 
                this.speedY = (Math.random() * 2 + 1.5) * (Math.random() > 0.5 ? 1 : -1); 
                this.width = Math.random() * 2 + 1; 
            }

            update() {
                this.x += this.speedX;
                this.y += this.speedY;

                // 边界碰撞反弹算法
                if (this.x < 0 || this.x > canvas.width) {
                    this.speedX *= -1; 
                }
                if (this.y < 0 || this.y > canvas.height) {
                    this.speedY *= -1; 
                }
            }

            draw() {
                const speedObj = Math.sqrt(this.speedX * this.speedX + this.speedY * this.speedY);
                const tailX = this.x - (this.speedX / speedObj) * this.length;
                const tailY = this.y - (this.speedY / speedObj) * this.length;

                const gradient = ctx.createLinearGradient(this.x, this.y, tailX, tailY);
                gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');       
                gradient.addColorStop(0.1, 'rgba(118, 75, 162, 0.8)');   
                gradient.addColorStop(0.6, 'rgba(102, 126, 234, 0.3)');   
                gradient.addColorStop(1, 'rgba(15, 12, 27, 0)');          

                ctx.beginPath();
                ctx.strokeStyle = gradient;
                ctx.lineWidth = this.width;
                ctx.lineCap = 'round';
                ctx.moveTo(this.x, this.y);
                ctx.lineTo(tailX, tailY);
                ctx.stroke();
            }
        }

        const meteors = [];
        for (let i = 0; i < 15; i++) {
            meteors.push(new Meteor());
        }

        function animate() {
            const skyGrad = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
            skyGrad.addColorStop(0, '#0f0c20');
            skyGrad.addColorStop(0.5, '#15102a');
            skyGrad.addColorStop(1, '#06040a');
            ctx.fillStyle = skyGrad;
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            meteors.forEach(meteor => {
                meteor.update();
                meteor.draw();
            });

            requestAnimationFrame(animate);
        }
        animate();

        function showName() {
            const input = document.getElementById('fileInput');
            const display = document.getElementById('fileNameDisplay');
            if(input.files.length > 0) { display.innerText = "已选择: " + input.files[0].name; }
        }
        async function uploadFile() {
            const input = document.getElementById('fileInput');
            const status = document.getElementById('status');
            if (input.files.length === 0) { status.className = "status-error"; status.innerText = "❌ 请先选择一个 Excel 文件！"; return; }
            const formData = new FormData();
            formData.append('excel', input.files[0]);
            status.className = "status-loading"; status.innerText = "⏳ 正在上传到 Render 云端...";
            try {
                const response = await fetch('/upload', { method: 'POST', body: formData });
                if (response.ok) {
                    status.className = "status-success"; status.innerHTML = "✅ 成功上传并覆盖！<br>GitHub 专用抓取直链已激活。";
                } else {
                    status.className = "status-error"; status.innerText = "❌ 上传失败，服务器错误。";
                }
            } catch (e) {
                status.className = "status-error"; status.innerText = "❌ 网络连接失败。";
            }
        }
    </script>
</body>
</html>
`;

// 3. 设置路由响应与下载端点
app.get('/', (req, res) => res.send(htmlContent));
// 新增的保护开关：如果有人来下载 Excel 却发现根本没有文件，直接报错 404 告诉 GitHub，不要吐出网页源码
app.get('/%E7%8E%B0%E6%9C%89%E5%85%A8%E9%83%A8%E5%AF%B9%E7%85%A7%E5%93%81%E7%9B%AE%E5%BD%95.xlsx', (req, res, next) => {
    const fs = require('fs');
    const filePath = path.join(__dirname, '现有全部对照品目录.xlsx');
    if (!fs.existsSync(filePath)) {
        return res.status(404).send('File not uploaded yet');
    }
    next();
});


// 托管当前目录下的所有静态文件（允许直接下载生成的 Excel）
app.use(express.static(__dirname)); 

app.post('/upload', upload.single('excel'), (req, res) => {
    if (!req.file) return res.status(400).send('No file received');
    res.status(200).send('OK');
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
