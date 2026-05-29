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

// 2. 将高颜值的网页直接写在后端代码里输出（避免了跨域和多文件传输问题）
const htmlContent = `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>对照品目录管理系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; display: flex; justify-content: center; align-items: center; color: #333;
        }
        .card { 
            background: rgba(255, 255, 255, 0.95); padding: 40px; border-radius: 20px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.15); width: 100%; max-width: 450px; text-align: center;
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
    <script>
        function showName() {
            const input = document.getElementById('fileInput');
            const display = document.getElementById('fileNameDisplay');
            if(input.files.length > 0) {
                display.innerText = "已选择: " + input.files[0].name;
            }
        }
        async function uploadFile() {
            const input = document.getElementById('fileInput');
            const status = document.getElementById('status');
            if (input.files.length === 0) {
                status.className = "status-error"; status.innerText = "❌ 请先选择一个 Excel 文件！"; return;
            }
            const formData = new FormData();
            formData.append('excel', input.files[0]);
            status.className = "status-loading"; status.innerText = "⏳ 正在上传到 Render 云端...";
            try {
                const response = await fetch('/upload', { method: 'POST', body: formData });
                if (response.ok) {
                    status.className = "status-success";
                    status.innerHTML = "✅ 成功上传并覆盖！<br>GitHub 专用抓取直链已激活。";
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

// 3. 设置路由响应
app.get('/', (req, res) => res.send(htmlContent));

// 让公开网络能够直接下载保存的 Excel 文件
app.use(express.static(__dirname)); 

app.post('/upload', upload.single('excel'), (req, res) => {
    if (!req.file) return res.status(400).send('No file received');
    res.status(200).send('OK');
});

app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
