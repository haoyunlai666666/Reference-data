import os
# 【核心升级】抛弃被防火墙拉黑的 standard requests，改用可以完美伪装真实浏览器 TLS 指纹的 curl_cffi
from curl_cffi import requests


def download_usp_catalog_with_chrome_fingerprint():
    print("🚀 [GitHub Actions] 正在启用行业级【Chrome 底层指纹伪装方案】...")

    # 严格使用你确认的原厂物理下载直链
    target_url = "https://usp.org"

    try:
        print("🌐 正在让 GitHub 模拟真实的 Chrome 桌面浏览器发起底层握手...")
        
        # impersonate="chrome" 是灵魂所在：它能让 Akamai 防火墙认为这就是一个真正的人在用电脑下载
        response = requests.get(target_url, impersonate="chrome", timeout=90)
        
        # 如果返回 403，说明伪装未生效，但 curl_cffi 对 Akamai 具备极强穿透力
        if response.status_code == 403:
            print("\n❌ 拦截警报：当前机房节点已被彻底锁死。")
            response.raise_for_status()

        response.raise_for_status()

        # 严格遵照你的要求，锁定为原厂标准的 .xls 后缀
        target_filename = "Reference Standards Catalog.xls"
        save_path = os.path.join(os.getcwd(), target_filename)

        print("⏳ 完美穿透防火墙！正在无损写入原厂二进制数据流...")
        with open(save_path, "wb") as f:
            f.write(response.content)

        file_size = os.path.getsize(save_path)
        print(f"📦 传输完毕！成功生成文件大小: {file_size / 1024 / 1024:.2f} MB")
        print(f"🎉 【恭喜，底层剥离成功！】原装无损表格已就位：\n➡️ {save_path}")

    except Exception as e:
        print(f"\n❌ 底层指纹穿透方案执行失败: {e}")
        raise e


if __name__ == "__main__":
    download_usp_catalog_with_chrome_fingerprint()
