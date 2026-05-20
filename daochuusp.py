import os
import requests


def download_usp_catalog_only():
    print("🚀 [GitHub Actions] 开始执行独立的 USP 官方目录下载任务...")

    # Excel 的最终静态下载地址
    target_url = "https://usp.org"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://usp.org",
    }

    try:
        print("🌐 正在通过 GitHub 海外服务器连接 USP...")
        response = requests.get(target_url, headers=headers, timeout=90, stream=True)
        response.raise_for_status()

        target_filename = "Reference Standards Catalog.xlsx"

        print("⏳ 正在拉取大容量数据并写入工作空间...")
        with open(target_filename, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(
            f"🎉 成功生成文件：{target_filename}，大小约为几兆，准备通过邮件发送..."
        )

    except Exception as e:
        print(f"❌ 下载失败，错误信息: {e}")
        raise e


if __name__ == "__main__":
    download_usp_catalog_only()
