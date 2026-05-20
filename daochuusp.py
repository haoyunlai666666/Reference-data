import os
import requests


def download_usp_catalog_strict_xls():
    print("🚀 [GitHub Actions] 启动原厂 .xls 数据流底层剥离方案...")

    # 1. 严格使用你确认的原厂 .xls 真实下载直链
    target_url = "https://usp.org"

    # 注入全套高权重真实浏览器请求头，最大化模拟真实用户直接下载文件的网络行为
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        print("🌐 正在通过会话机制建立与 USP 原厂服务器的无损连接...")
        session = requests.Session()
        # 增加 stream=True 开启流式传输，防止大文件在机房网络下被截断导致文件损坏
        response = session.get(
            target_url, headers=headers, timeout=120, stream=True
        )
        response.raise_for_status()

        # 2. 【核心修改】严格锁定为 .xls 后缀，确保与原厂格式百分之百匹配
        target_filename = "Reference Standards Catalog.xls"
        save_path = os.path.join(os.getcwd(), target_filename)

        print("⏳ 通道已打通！正在以无损二进制模式分块写入 .xls 数据...")
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=32768):  # 32KB 分块精确写入
                if chunk:
                    f.write(chunk)

        # 3. 增加文件内容与大小的硬性防错核对机制
        file_size = os.path.getsize(save_path)
        print(
            f"📦 传输完毕！本地生成文件大小: {file_size / 1024 / 1024:.2f} MB"
        )

        # 如果被防火墙拦截返回了报错网页文本，文件大小通常只有几 KB 或十几 KB
        if file_size < 100000:
            print(
                "❌ 警告：下载的数据量过小，抓取到的可能仍是 Akamai 防火墙的报错页文本。"
            )
            with open(save_path, "r", encoding="utf-8", errors="ignore") as f:
                preview = f.read(150)
                if "<html" in preview.lower() or "<!doctype" in preview.lower():
                    raise ValueError(
                        "服务器拒绝了机房请求，返回了网页 HTML 拦截文本，而非真实的 Excel 数据。"
                    )
        else:
            print(
                f"🎉 【原厂数据剥离成功！】真实无损 .xls 表格已就位：\n➡️ {save_path}"
            )

    except Exception as e:
        print(f"\n❌ 底层下载方案执行失败: {e}")
        raise e


if __name__ == "__main__":
    download_usp_catalog_strict_xls()
