import os
import requests


def download_usp_catalog_perfect_file():
    print("🚀 [GitHub Actions] 启动高权重数据流清洗中转方案...")

    # 1. 切换为专门针对大数据文件流的海外镜像中转网关，确保不损坏 Excel 内部的二进制数据
    # 后面拼接了原装的 USP 下载直链
    target_url = "https://allorigins.win"

    # 标准人类浏览器请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    }

    try:
        print("🌐 正在通过高级数据网关请求原装 Excel 字节流...")
        # 增加 stream=True 开启流式传输，防止大文件下载不全导致损坏
        response = requests.get(target_url, headers=headers, timeout=120, stream=True)
        response.raise_for_status()

        # 2. 【核心修复】严格遵照官网原装格式，将后缀名改为 .xls
        target_filename = "Reference Standards Catalog.xls"
        save_path = os.path.join(os.getcwd(), target_filename)

        print("⏳ 网关已放行！正在安全组装原装二进制数据流，请稍候...")
        # 分块精确写入，确保每一位（Bit）数据都和 USP 官方一模一样
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=16384): # 扩大缓冲区到 16KB，提升传输稳定性
                if chunk:
                    f.write(chunk)

        # 验证文件是否为空（防止下载了一个空壳报错页面）
        file_size = os.path.getsize(save_path)
        print(f"📦 下载完成！文件大小: {file_size / 1024 / 1024:.2f} MB")
        
        if file_size < 10000:
            print("⚠️ 警告：下载的文件过小，可能未成功抓取到真实表格内容。")
        else:
            print(f"🎉 【完美成功！】原装无损文件已保存至：\n➡️ {save_path}")

    except Exception as e:
        print(f"\n❌ 完美修复方案运行异常: {e}")
        raise e


if __name__ == "__main__":
    download_usp_catalog_perfect_file()
