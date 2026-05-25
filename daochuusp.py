import os
import time
from curl_cffi import requests


def download_real_usp_catalog():
    print("🚀 [GitHub Actions] 正在启动 13MB 原厂真实目录数据流抓取...")

    # 【核心修正】切换为原厂核心静态数据仓直链，直奔 usprefstd.xls
    target_url = "http://static.usp.org/doc/referenceStandards/usprefstd.xls"

    # 严格遵照你提供的主机原厂命名：usprefstd.xls
    target_filename = "usprefstd.xls"
    save_path = os.path.join(os.getcwd(), target_filename)

    max_retries = 3  # 最大重试次数
    retry_delay = 10  # 失败后等待多少秒重试

    for attempt in range(1, max_retries + 1):
        try:
            print("🌐 正在使用 Chrome 底层网络特征建立加密套件握手...")
            # impersonate="chrome" 100% 伪装成真实的桌面谷歌浏览器，让 Akamai 防火墙无条件放行
            # 开启 stream=True 启用流式下载，并将单次超时适当调整为 300 秒
            response = requests.get(
                target_url, impersonate="chrome", timeout=300, stream=True
            )
            response.raise_for_status()

            print("⏳ 穿透成功！正在写入真实的 13MB 二进制 Excel 物质目录...")

            # 以流式分块写入文件
            with open(save_path, "wb") as f:
                # 每次读取 128 KB (131072 bytes)
                for chunk in response.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)

            # 增加大小硬性防错核对，确保这次绝对不是几 KB 的说明网页
            file_size = os.path.getsize(save_path)
            print(
                f"📦 传输完毕！GitHub 本地生成文件大小: {file_size / 1024 / 1024:.2f} MB"
            )

            if file_size < 5000000:  # 如果小于 5MB，说明依然被截断或下错了网页
                raise ValueError(
                    f"抓取到的数据量（{file_size / 1024:.2f} KB）不符合 13MB 真实目录特征，请检查链接！"
                )
            else:
                print(
                    f"🎉 【原厂物质目录剥离成功！】真实 {target_filename} 已经安全就位。"
                )

            # 成功后跳出重试循环
            break

        except Exception as e:
            print(f"\n⚠️ 第 {attempt} 次下载尝试失败，原因: {e}")
            if attempt < max_retries:
                print(f"等待 {retry_delay} 秒后进行下一次重试...\n")
                time.sleep(retry_delay)
            else:
                print(f"\n❌ 真实目录下载方案执行失败: {e}")
                raise e


if __name__ == "__main__":
    download_real_usp_catalog()
