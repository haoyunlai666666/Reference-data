import time
import random
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from openpyxl.utils import get_column_letter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ================= 严格定义所有网址，绝不精简 =================
# 目录抓取部分
REFERER_URL = "http://aoc.nifdc.org.cn/sell/home/search.html"
API_URL = "http://aoc.nifdc.org.cn/sell/sgoodsQuerywaiw.do?formAction=queryZongList"

# 停用通知公告部分
NOTICE_INDEX_URL = "https://www.nifdc.org.cn/nifdc/bshff/bzhwzh/index.html"
# ================= ============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Origin": "http://aoc.nifdc.org.cn/sell/home/search.html",
    "Referer": REFERER_URL,
    "Content-Type": "application/x-www-form-urlencoded"
}

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=15),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True
)
def fetch_page_html(page_num):
    payload = {
        "formAction": "queryZongList",
        "curPage": str(page_num),
        "toPage": str(page_num),
        "sgoodsno": "",
        "sgoodsname": ""
    }
    response = requests.post(API_URL, headers=HEADERS, data=payload, timeout=20)
    response.encoding = 'gbk'
    if response.status_code != 200:
        print(f"[警告] 遭遇状态码 {response.status_code} 反爬拦截或异常，正在启动指数避让重试...")
        response.raise_for_status()
    return response.text

def parse_table_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    rows = soup.find_all("tr")
    page_data = []
    for row in rows:
        inputs = row.find_all("input")
        if len(inputs) >= 5:
            row_dict = {inp.get("name"): inp.get("value", "").strip() for inp in inputs if inp.get("name")}
            if row_dict.get("sgoods_no"):
                item = {
                    "标准品编号": row_dict.get("sgoods_no", ""),
                    "品名": row_dict.get("sgoods_name", ""),
                    "批号": row_dict.get("xsBatch_no", row_dict.get("batch_no", "")).strip(),
                    "规格": row_dict.get("standard", ""),
                    "用途": row_dict.get("used", ""),
                    "保存条件": row_dict.get("save_condition", ""),
                    "停用日期": "",       
                    "有效使用期限": ""    
                }
                page_data.append(item)
    return page_data

def scrape_all_stop_notices():
    """全量清洗停用通知公告以及供应新情况中的表格数据"""
    stop_dict = {}       
    expiry_dict = {}     
    
    print(f"\n 正在调用浏览器模块，切入公告主页：{NOTICE_INDEX_URL}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"], viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(NOTICE_INDEX_URL, timeout=40000)
        page.wait_for_timeout(3000)
        page_idx = 1
        while True:
            print(f" 正在扫描通知公告列表第 {page_idx} 页...")
            soup = BeautifulSoup(page.content(), "html.parser")
            
            stop_urls = []    
            supply_urls = []  
            
            for l in soup.find_all("a"):
                title = l.get_text(strip=True)
                href = l.get("href", "")
                if not href: continue
                
                if "化学对照品停用通知" in title:
                    abs_url = urljoin(NOTICE_INDEX_URL, href)
                    if abs_url not in stop_urls: stop_urls.append(abs_url)
                elif "国家药品标准物质供应新情况" in title:
                    abs_url = urljoin(NOTICE_INDEX_URL, href)
                    if abs_url not in supply_urls: supply_urls.append(abs_url)
                    
            print(f" [分析完成] 本页发现 {len(stop_urls)} 个停用链接，{len(supply_urls)} 个供应新情况链接...")
            
            # --- 模块 A：顺序解析【停用通知】 ---
            for url in stop_urls:
                try:
                    detail_page = context.new_page()
                    detail_page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    detail_page.wait_for_timeout(2000)
                    detail_soup = BeautifulSoup(detail_page.content(), "html.parser")
                    full_page_text = detail_soup.get_text()
                    date_match = re.search(r"发布时间\s*[:：]\s*(\d{4}[-/]\d{2}[-/]\d{2})", full_page_text)
                    publish_date = date_match.group(1).replace("/", "-") if date_match else ""
                    if not publish_date:
                        date_match_backup = re.search(r"(\d{4}-\d{2}-\d{2})", full_page_text)
                        publish_date = date_match_backup.group(1) if date_match_backup else ""
                    text_block = detail_soup.find(class_="text")
                    raw_html_str = str(text_block) if text_block else str(detail_soup)
                    clean_html_str = re.sub(r"</?(span|font|o:p|a|strong|b|i)[^>]*>", "", raw_html_str)
                    clean_soup = BeautifulSoup(clean_html_str, "html.parser")
                    lines = [line.strip() for line in clean_soup.get_text(separator="\n").split("\n") if line.strip()]
                    
                    pending_batch = None 
                    
                    for line in lines:
                        nums = re.findall(r"\d+", line)
                        
                        if len(nums) == 0 and pending_batch:
                            name_clean = line.strip(" \t\n\r,，.。.、:：;； ")
                            if name_clean in ["特此通知", "现予以公布", "关于发布", "请各单位", "通知"] or not name_clean:
                                pending_batch = None
                                continue
                            pure_digits = pending_batch
                            stop_dict[pure_digits] = publish_date
                            print(f" [ 跨行锁定成功 ] 品名 : {name_clean} | 纯数字批号 : {pure_digits} | 停用日期: {publish_date}")
                            pending_batch = None
                            continue
                        
                        if len(nums) < 2: continue
                        part1, part2 = nums[0], nums[1]
                        
                        # 👈【彻底消除语法错误】：放弃 in 关键字，改用万无一失的显式等于判断，完全封死接口格式化漏洞
                        if (len(part1) == 4 or len(part1) == 6) and (len(part2) == 4 or len(part2) == 6):
                            start_pos = line.find(str(part1))
                            end_pos = line.find(str(part2), start_pos + len(str(part1))) + len(str(part2))
                            if start_pos == -1 or end_pos <= start_pos: continue
                            
                            batch_raw = line[start_pos:end_pos]
                            pure_digits = str(part1) + str(part2)
                            
                            txt_before = line[:start_pos].strip(" \t\n\r,，.。.、:：;； ")
                            txt_after = line[end_pos:].strip(" \t\n\r,，.。.、:：;； ")
                            
                            if not txt_before and not txt_after:
                                pending_batch = pure_digits  
                                continue
                            
                            noise_words = ["现停止使用", "现决定停用", "各有关单位", "特此通知", "关于发布", "通知", "发布时间"]
                            if any(w in txt_before for w in noise_words) or not txt_before:
                                name_clean = txt_after
                            else:
                                name_clean = txt_before
                            if name_clean in noise_words or name_clean.lower() == "reserved" or not name_clean:
                                continue
                            for noise in ["特此通知", "现予以公布", "关于发布", "请各单位"]:
                                if noise in name_clean:
                                    name_clean = name_clean.split(noise).strip(" \t\n\r,，.。.、:：;； ")
                            stop_dict[pure_digits] = publish_date
                            print(f" [ 同行锁定成功 ] 品名 : {name_clean} | 纯数字批号 : {pure_digits} | 停用日期: {publish_date}")
                            pending_batch = None  
                    detail_page.close()
                    time.sleep(random.uniform(1.2, 2.2))
                except Exception as e:
                    print(f" 读取通知详情页失败 {url}: {e}")
                    try: detail_page.close()
                    except: pass
                    
            # --- 模块 B：顺序解析【供应新情况】详情页中的表格 ---
            for url in supply_urls:
                try:
                    detail_page = context.new_page()
                    detail_page.goto(url, timeout=45000, wait_until="domcontentloaded")
                    detail_page.wait_for_timeout(2000)
                    detail_soup = BeautifulSoup(detail_page.content(), "html.parser")
                    
                    tables = detail_soup.find_all("table")
                    for table in tables:
                        rows = table.find_all("tr")
                        if not rows: continue
                        
                        header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["td", "th"])]
                        
                        # 定义可能出现的表头别名，增强对不同页面格式的鲁棒性
                        name_keywords = ["品种名称", "名称"]
                        batch_keywords = ["批号"]
                        expiry_keywords = ["有效使用期限", "有效至"]

                        name_idx, batch_idx, expiry_idx = -1, -1, -1

                        # 动态遍历当前表头，检索并锁定各列的准确索引
                        for idx, cell_text in enumerate(header_cells):
                             if any(kw in cell_text for kw in name_keywords) and name_idx == -1:
                                  name_idx = idx
                             elif any(kw in cell_text for kw in batch_keywords) and batch_idx == -1:
                                  batch_idx = idx
                             elif any(kw in cell_text for kw in expiry_keywords) and expiry_idx == -1:
                                  expiry_idx = idx

                        # 只有当“名称”、“批号”、“有效截止日期”三列索引全部成功锁定后，才执行数据提取
                        if name_idx != -1 and batch_idx != -1 and expiry_idx != -1:
                             for data_row in rows[1:]:

                            
                  
                                cells = [td.get_text(strip=True) for td in data_row.find_all(["td", "th"])]
                                if len(cells) <= max(name_idx, batch_idx, expiry_idx): continue
                                
                                row_name = cells[name_idx]
                                row_batch = cells[batch_idx]
                                row_expiry = cells[expiry_idx]
                                
                                pure_batch_digits = re.sub(r"[^0-9]", "", row_batch)
                                if len(pure_batch_digits) < 8 or not row_expiry: continue
                                
                                expiry_dict[pure_batch_digits] = row_expiry
                                print(f" [ 供应情况锁定 ] 品名: {row_name} | 纯数字批号: {pure_batch_digits} | 有效期限: {row_expiry}")
                                
                    detail_page.close()
                    time.sleep(random.uniform(1.2, 2.2))
                except Exception as e:
                    print(f" 读取供应情况详情页失败 {url}: {e}")
                    try: detail_page.close()
                    except: pass
                    
            next_btn = page.locator("text='下一页'").first
            if next_btn and next_btn.is_visible() and next_btn.is_enabled():
                next_btn.click(force=True)
                page_idx += 1
                page.wait_for_timeout(4000)  
            else:
                print(" 已经成功安全扫描完公告系统中的所有分页。")
                break
        browser.close()
        return stop_dict, expiry_dict  

def main():
    all_items = []
    print(f" 正在基于底层直链执行全量目录冲刷，环境参照页：{REFERER_URL}")
    
    current_page = 1
    total_pages = 9999  
    
    while current_page <= total_pages:
        try:
            print(f"-> 正在向服务器请求第 {current_page} 页的原始数据...")
            html_content = fetch_page_html(current_page)
            
            if current_page == 1:
                soup = BeautifulSoup(html_content, "html.parser")
                to_page_input = soup.find("input", {"name": "toPage"})
                if to_page_input and to_page_input.get("value"):
                    try:
                        total_pages = int(to_page_input.get("value"))
                        print(f" 成功嗅探到在售物质目录系统当前总页数为：{total_pages} 页")
                    except ValueError:
                        pass
                        
            page_data = parse_table_html(html_content)
            if not page_data: 
                print(f" 监测到第 {current_page} 页无有效标准品数据，自动安全熔断。")
                break
                
            all_items.extend(page_data)
            current_page += 1
            time.sleep(random.uniform(3.5, 5.5))  
        except Exception as e:
            print(f" [请求中断] 发生错误: {e}")
            break
            
    df = pd.DataFrame(all_items)
    stop_data_map, expiry_data_map = scrape_all_stop_notices()
    
    print("\n 正在进行 [品名 + 批号] 双数据源字段联动核对，自动填入停用日期与有效使用期限...")
    stop_match_count = 0
    expiry_match_count = 0
    
    for idx, row in df.iterrows():
        batch_key = row["批号"].strip()
        catalog_pure_digits = re.sub(r"[^0-9]", "", batch_key)
        
        if catalog_pure_digits in stop_data_map:
            df.at[idx, "停用日期"] = stop_data_map[catalog_pure_digits]
            stop_match_count += 1
            
        if catalog_pure_digits in expiry_data_map:
            df.at[idx, "有效使用期限"] = expiry_data_map[catalog_pure_digits]
            expiry_match_count += 1
            
    print(f" 比对完成！在全量在售目录数据中，共成功匹配并更新了 {stop_match_count} 项停用日期，{expiry_match_count} 项有效使用期限。")
    
    output_file = "国家药品标准物质目录_全量在售.xlsx"
    print(f"\n 正在将全量数据无损写入：{output_file}")
    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="全量标准物质")
            worksheet = writer.sheets["全量标准物质"]
            for col_idx, col in enumerate(worksheet.columns, start=1):
                max_len = 0
                col_letter = get_column_letter(col_idx)
                for cell in col:
                    if cell.value is not None:
                        val_str = str(cell.value)
                        cell_len = sum(2 if ord(ch) > 127 else 1 for ch in val_str)
                        if cell_len > max_len: max_len = cell_len
                worksheet.column_dimensions[col_letter].width = max(max_len + 4, 12)
        print(f"\n 运行结束！已成功生成全量在售标准物质及有效期限匹配总表。")
    except PermissionError:
        print(f"\n 错误：无法写入文件！请务必关闭正在被 Excel 或 WPS 打开的 '{output_file}'，然后重新运行脚本！")

if __name__ == "__main__":
    main()
