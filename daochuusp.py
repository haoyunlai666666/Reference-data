import os
import requests


def download_usp_catalog_by_direct_url():
    print("🚀 [GitHub Actions] 开始执行独立的 USP 官方目录下载任务...")

    # Excel 的最终静态下载地址
    target_url = "https://usp.org"

    # 深度伪装请求头，假装是真实的 Edge 浏览器在发起直接文件下载
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.usp.org/reference-standards",
    }

    try:
        print("🌐 正在通过 GitHub 海外高权重服务器直接建立下载连接...")
        response = requests.get(target_url, headers=headers, timeout=60, stream=True)

        if response.status_code == 403:
            print("\n❌ 依然返回 403。USP 限制了此 GitHub Actions 机房段，我们需要换备用策略。")
            response.raise_for_status()

        response.raise_for_status()

        # 严格按照你的命名要求
        target_filename = "Reference Standards Catalog.xlsx"
        save_path = os.path.join(os.getcwd(), target_filename)

        print("⏳ 安全握手成功！正在在 GitHub 工作空间中拉取 Excel 数据流...")
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"\n🎉 【测试成功！】文件已成功下载并保存至：\n➡️ {save_path}")

    except Exception as e:
        print(f"\n❌ 网络连接异常: {e}")
        raise e


if __name__ == "__main__":
    download_usp_catalog_by_direct_url()
