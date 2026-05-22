import os
import pandas as pd

def clean_string(series):
    """去除字符串中所有的空格、换行符等，转换为大写"""
    return series.astype(str).str.replace(r'\s+', '', regex=True).str.strip().str.upper()

def main():
    base_file = "现有全部对照品目录.xlsx"
    chp_file  = "国家药品标准物质目录_全量在售.xlsx"
    edqm_file = "EDQM_Catalog_Output.xlsx"
    usp_file  = "usprefstd.xls"
    
    missing_chp, missing_edqm, missing_usp = [], [], []
    error_chp, error_edqm, error_usp = "", "", ""
    
    # -----------------------------------------------------------------
    # 1. ChP 中文对照品比对（精确列名 + 表头防空格污染）
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(chp_file):
        try:
            df_base = pd.read_excel(base_file)
            df_chp  = pd.read_excel(chp_file)
            
            # 【核心优化】：将线上生成的 ChP 表头所有的空格强制全部删掉，让“幽灵空格”无处遁形！
            df_chp.columns = df_chp.columns.astype(str).str.replace(r'\s+', '', regex=True)
            
            # 明确指定需要比对的列名
            name_col = '品名'
            lot_col = '批号'
            
            # 二次校验，如果去除了空格还是找不到，说明爬取的数据有结构性变动
            if name_col not in df_chp.columns or lot_col not in df_chp.columns:
                raise KeyError(f"清理空格后仍找不到'{name_col}'或'{lot_col}'。当前实际列名有: {df_chp.columns.tolist()}")
            
            df_base_chp = df_base[['对照品中文名称', '对照品中文批号Chp']].dropna(subset=['对照品中文名称']).copy()
            df_base_chp['clean_name'] = clean_string(df_base_chp['对照品中文名称'])
            df_base_chp['clean_lot']  = clean_string(df_base_chp['对照品中文批号Chp'])
            
            df_chp_clean = df_chp[[name_col, lot_col]].dropna(subset=[name_col]).copy()
            df_chp_clean['clean_name'] = clean_string(df_chp_clean[name_col])
            df_chp_clean['clean_lot']  = clean_string(df_chp_clean[lot_col])
            
            chp_existing_set = set(zip(df_chp_clean['clean_name'], df_chp_clean['clean_lot']))
            
            for _, row in df_base_chp.iterrows():
                if (row['clean_name'], row['clean_lot']) not in chp_existing_set:
                    missing_chp.append(f"{row['对照品中文名称']} (批号: {row['对照品中文批号Chp']})")
        except Exception as e:
            error_chp = f"ChP比对失败，错误详情：{str(e)}"
    else:
        error_chp = "未找到ChP线上生成的文件或本地基准文件！"

    # -----------------------------------------------------------------
    # 2. EDQM 欧洲药典对照品比对
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(edqm_file):
        try:
            df_base = pd.read_excel(base_file)
            df_edqm = pd.read_excel(edqm_file)
            
            df_base_eng = df_base[['对照品英文名称', '对照品英文批号EP-USP']].dropna(subset=['对照品英文名称']).copy()
            df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称'])
            df_base_eng['clean_lot']  = clean_string(df_base_eng['对照品英文批号EP-USP'])
            
            df_edqm_clean = df_edqm[['Reference Standard', 'Batc h n°']].dropna(subset=['Reference Standard']).copy()
            df_edqm_clean['clean_name'] = clean_string(df_edqm_clean['Reference Standard'])
            df_edqm_clean['clean_lot']  = clean_string(df_edqm_clean['Batc h n°'])
            
            edqm_existing_set = set(zip(df_edqm_clean['clean_name'], df_edqm_clean['clean_lot']))
            
            for _, row in df_base_eng.iterrows():
                if (row['clean_name'], row['clean_lot']) not in edqm_existing_set:
                    missing_edqm.append(f"{row['对照品英文名称']} (批号: {row['对照品英文批号EP-USP']})")
        except Exception as e:
            error_edqm = f"EDQM比对失败，错误详情：{str(e)}"
    else:
        error_edqm = "未找到EDQM线上生成的文件！"

    # -----------------------------------------------------------------
# -----------------------------------------------------------------
# -----------------------------------------------------------------
# -----------------------------------------------------------------
    # 3. USP 美国药典对照品比对（针对“邮件头污染”文件的终极清洗）
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(usp_file):
        try:
            df_base = pd.read_excel(base_file)
            df_usp = None
            
            # 使用 bs4 (BeautifulSoup) 辅助解析，无视那些混乱的邮件头，直接从 HTML 结构中提取 table
            import bs4
            
            try:
                # 以二进制模式读取文件内容，跳过所有的乱码和协议头
                with open(usp_file, 'rb') as f:
                    content = f.read().decode('utf-8', errors='ignore')
                
                # 直接通过 BeautifulSoup 找到第一个 <table> 标签
                soup = bs4.BeautifulSoup(content, 'lxml')
                tables = soup.find_all('table')
                
                if tables:
                    # 将第一个找到的 table 转换为 DataFrame
                    df_usp = pd.read_html(str(tables[0]))[0]
            except Exception as e:
                # 如果 BeautifulSoup 没抓到，降级使用旧的逻辑
                pass

            # 确保成功获取到了数据表 (如果上面没抓到，再尝试 Pandas 原生解析)
            if df_usp is None or df_usp.empty:
                 # 降级尝试：直接使用 pd.read_html 并指定 header，强制它重新判断表头
                 dfs = pd.read_html(usp_file, flavor='lxml', header=0)
                 # 尝试从所有解析出的表格中找到含有关键列的那个
                 for df in dfs:
                     if 'Product Name' in df.columns.astype(str) or 'ProductName' in df.columns.astype(str):
                         df_usp = df
                         break
            
            if df_usp is not None and not df_usp.empty:
                # --- 动态列名嗅探器（保留你的 10 行扫描逻辑，防止表头位置漂移） ---
                df_usp.columns = df_usp.columns.astype(str)
                
                def find_real_col_name(df, target_keyword):
                    import re
                    for col in df.columns:
                        col_clean = re.sub(r'\s+', '', col).lower()
                        if target_keyword.lower() in col_clean:
                            return col
                    return None
                
                name_col = find_real_col_name(df_usp, "ProductName")
                lot_col = find_real_col_name(df_usp, "CurrentLot")
                
                # 如果列名提取失败，尝试提拔第 0 行作为表头
                if not name_col or not lot_col:
                    df_usp.columns = df_usp.iloc[0]
                    df_usp = df_usp.iloc[1:].reset_index(drop=True)
                    name_col = find_real_col_name(df_usp, "ProductName")
                    lot_col = find_real_col_name(df_usp, "CurrentLot")

                if not name_col or not lot_col:
                    raise KeyError(f"未能自动定位到列，当前发现列名: {df_usp.columns.tolist()}")

                # --- 执行原有的比对逻辑 ---
                df_base_eng = df_base[['对照品英文名称', '对照品英文批号EP-USP']].dropna(subset=['对照品英文名称']).copy()
                df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称'])
                df_base_eng['clean_lot']  = clean_string(df_base_eng['对照品英文批号EP-USP'])
                
                df_usp_clean = df_usp[[name_col, lot_col]].dropna(subset=[name_col]).copy()
                df_usp_clean['clean_name'] = clean_string(df_usp_clean[name_col])
                df_usp_clean['clean_lot']  = clean_string(df_usp_clean[lot_col])
                
                usp_existing_set = set(zip(df_usp_clean['clean_name'], df_usp_clean['clean_lot']))
                
                for _, row in df_base_eng.iterrows():
                    if (row['clean_name'], row['clean_lot']) not in usp_existing_set:
                        missing_usp.append(f"{row['对照品英文名称']} (批号: {row['对照品英文批号EP-USP']})")
            else:
                raise ValueError("文件读取成功，但未能解析出任何有效的表格数据结构。")
                
        except Exception as e:
            error_usp = f"USP比对失败，错误详情：{str(e)}"
    else:
        error_usp = "未找到USP线上生成的文件！"

    # -----------------------------------------------------------------
    # 4. 生成带样式的高亮/报错 HTML 邮件正文
    # -----------------------------------------------------------------
    has_missing = missing_chp or missing_edqm or missing_usp
    has_error = error_chp or error_edqm or error_usp
    
    html_content = """
    <html>
    <head>
    <style>
        body { font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.6; color: #333; }
        .error-block { background-color: #FFF0F0; border-left: 5px solid #FF4D4D; padding: 15px; margin-bottom: 20px; color: #CC0000; }
        .warning-block { background-color: #FFFDEB; border-left: 5px solid #FFC107; padding: 15px; margin-bottom: 20px; }
        .highlight { background-color: yellow; font-weight: bold; padding: 2px 5px; }
        ul { margin-top: 5px; padding-left: 20px; }
        li { margin-bottom: 5px; }
    </style>
    </head>
    <body>
    <p>您好：</p>
    <p>以下是今日自动运行的药品对照品数据核对报告，请查收：</p>
    """
    
    # 场景 A：一旦有系统报错，大红字最醒目提示！
    if has_error:
        html_content += '<div class="error-block"><h3>🚨 严重警告：部分比对任务未能成功执行！</h3>'
        if error_chp: html_content += f'<p><b>【ChP 报错】</b> {error_chp}</p>'
        if error_edqm: html_content += f'<p><b>【EDQM 报错】</b> {error_edqm}</p>'
        if error_usp: html_content += f'<p><b>【USP 报错】</b> {error_usp}</p>'
        html_content += '<p><i>*请及时检查爬虫脚本是否失败，或目标网站表结构是否发生改变。</i></p></div>'
        
    # 场景 B：出现品种不匹配，黄底高亮警告！
    if has_missing:
        html_content += '<div class="warning-block">'
        html_content += '<p><span class="highlight">⚠️ 异常提醒：本地目录中的以下对照品在今日线上最新数据中未找到匹配项：</span></p>'
        
        if missing_chp:
            html_content += '<strong>【国家药品标准物质目录 (ChP)】未匹配：</strong>'
            html_content += '<ul>' + ''.join([f'<li>{item}</li>' for item in missing_chp]) + '</ul>'
        if missing_edqm:
            html_content += '<strong>【EDQM 欧洲药典】未匹配：</strong>'
            html_content += '<ul>' + ''.join([f'<li>{item}</li>' for item in missing_edqm]) + '</ul>'
        if missing_usp:
            html_content += '<strong>【USP 美国药典】未匹配：</strong>'
            html_content += '<ul>' + ''.join([f'<li>{item}</li>' for item in missing_usp]) + '</ul>'
        html_content += '</div>'
        
    # 场景 C：完美对账无异常
    if not has_missing and not has_error:
        html_content += '<p style="color: green; font-weight: bold; font-size: 16px;">✅ 今日核对结果：本地清单中的所有对照品信息（品名/批号）与三大药典最新官网数据均完全一致，未发现失效或下架品种。</p>'
        
    html_content += "<br><p>祝好，<br>自动化对账监控系统</p></body></html>"
    
    with open("mail_body.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("对账执行完毕，mail_body.html 报告生成成功！")

if __name__ == "__main__":
    main()
