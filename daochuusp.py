import os
import time
from playwright.sync_api import sync_playwright


def download_usp_catalog_via_playwright():
    print("🚀 [GitHub Actions] 开始执行独立的 USP 官方目录下载任务...")

    with sync_playwright() as p:
        # 在 GitHub 的 Linux 无界面环境下，必须设置 headless=True
        browser = p.chromium.launch(headless=True)

        # 深度伪装：注入完美的人类 Edge/Chrome 真实环境特征
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
            accept_downloads=True,  # 极其重要：必须显式允许接收下载文件
        )

        # 抹除底层自动化机器人指纹
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            # 绕过容易卡死的主页，直接降落到目录聚合页
            print("🌐 正在直接加载目录聚合页...")
            page.goto(
                "https://usp.org",
                wait_until="domcontentloaded",
            )
            time.sleep(5)  # 给予充足的底层动态脚本渲染时间

            # 精准定位 "Download as Excel" 标签
            print("🔍 正在穿透定位 'Download as Excel' 按钮...")
            excel_btn = page.locator("a:has-text('Download as Excel')").first
            excel_btn.wait_for(state="attached", timeout=30000)

            # 捕捉并拦截下载数据流
            print(
                "⏳ 按钮已锁定！正在通过真实浏览器触发下载，请耐心等待..."
            )
            with page.expect_download(timeout=90000) as download_info:
                excel_btn.click()

            download = download_info.value

            # 重命名并保存文件
            original_filename = download.suggested_filename
            file_extension = os.path.splitext(original_filename) or ".xlsx"
            target_filename = f"Reference Standards Catalog{file_extension}"

            save_path = os.path.join(os.getcwd(), target_filename)
            download.save_as(save_path)

            print(
                f"🎉 【测试成功！】文件已顺利带回并保存至：\n➡️ {save_path}"
            )

        except Exception as e:
            print(f"❌ 运行发生异常: {e}")
            raise e

        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    download_usp_catalog_via_playwright()
