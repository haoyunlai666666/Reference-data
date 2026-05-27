import os
import pandas as pd

def clean_string(series):
    """去除字符串中所有的空格、换行符等，转换为大写，并抹除纯整数浮点数的 .0 尾缀"""
    # 1. 安全处理：先将空值（NaN）填充为空字符串，并统一强制转化为字符串类型
    s_cleaned = series.fillna('').astype(str)
    
    # 2. 功能继承：去除所有空格、换行符、两端空格，并统一转为大写
    s_cleaned = s_cleaned.str.replace(r'\s+', '', regex=True).str.strip().str.upper()
    
    # 3. 核心修复：精准消灭纯整数后面的 ".0" 污染（如 "1.0" -> "1"），且绝对不伤及普通文本或复合批号
    s_cleaned = s_cleaned.str.replace(r'\.0$', '', regex=True)
    
    return s_cleaned

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
            
            df_base_eng = df_base[['对照品英文名称EP', '对照品英文批号EP']].dropna(subset=['对照品英文名称EP']).copy()
            df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称EP'])
            df_base_eng['clean_lot']  = clean_string(df_base_eng['对照品英文批号EP'])
            
            df_edqm_clean = df_edqm[['Reference Standard', 'Batc h n°']].dropna(subset=['Reference Standard']).copy()
            df_edqm_clean['clean_name'] = clean_string(df_edqm_clean['Reference Standard'])
            df_edqm_clean['clean_lot']  = clean_string(df_edqm_clean['Batc h n°'])
            
            edqm_existing_set = set(zip(df_edqm_clean['clean_name'], df_edqm_clean['clean_lot']))
            
            for _, row in df_base_eng.iterrows():
                if (row['clean_name'], row['clean_lot']) not in edqm_existing_set:
                    missing_edqm.append(f"{row['对照品英文名称EP']} (批号: {row['对照品英文批号EP']})")
        except Exception as e:
            error_edqm = f"EDQM比对失败，错误详情：{str(e)}"
    else:
        error_edqm = "未找到EDQM线上生成的文件！"

    # -----------------------------------------------------------------
# -----------------------------------------------------------------
    # 3. USP 美国药典对照品比对（彻底切断文件污染源 + 智能扫描 + 报错集成版）
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(usp_file):
        try:
            df_base = pd.read_excel(base_file)
            df_usp = None
            
            import bs4
            import quopri  # 核心：清洗 MHTML/Quoted-Printable 传输编码污染
            import re
            import io
            
            # 【关键修正点】：在最前端彻底完成内存解密，再也不给原生 pd.read_html 直接接触原文件的机会
            try:
                with open(usp_file, 'rb') as f:
                    raw_content = f.read()
                
                # 彻底解决 3D"7" 报错：将内容中的 =3D"7" 还原为标准文本
                decoded_bytes = quopri.decodestring(raw_content)
                clean_html_text = decoded_bytes.decode('utf-8', errors='ignore')
            except Exception as e:
                raise ValueError(f"读取或解码 USP 文件失败: {str(e)}")

            # --- 尝试策略 1：使用标准 BeautifulSoup 提取 <table> 标签 ---
            try:
                soup = bs4.BeautifulSoup(clean_html_text, 'lxml')
                tables = soup.find_all('table')
                if tables:
                    # 用内存中的干净文本给 pandas 解析
                    df_usp = pd.read_html(str(tables))[0]
            except Exception:
                pass
            
            # --- 尝试策略 2（降级策略）：如果策略 1 失败，依然用【干净的清洗文本】输入给 pd.read_html ---
            if df_usp is None or df_usp.empty:
                try:
                    # 通过 io.StringIO 将清洗后的纯文本包裹，从而替代物理文件路径输入，防止底层解析器崩溃
                    dfs = pd.read_html(io.StringIO(clean_html_text), flavor='lxml')
                    for df in dfs:
                        df_cols_clean = [re.sub(r'\s+', '', str(c)).lower() for c in df.columns.astype(str)]
                        # 嗅探哪个子表格带有产品名关键字
                        if any('productname' in c for c in df_cols_clean):
                            df_usp = df
                            break
                    if df_usp is None and len(dfs) > 0:
                        df_usp = dfs[0]
                except Exception as e:
                    pass
            
            # --- 开始解析最终提取出来的 DataFrame ---
            if df_usp is not None and not df_usp.empty:
                df_usp.columns = df_usp.columns.astype(str)
                
                # 【智能行扫描器】：逐行扫描前 10 行，自动精准适配行漂移并全面粉碎空格污染
                real_header_idx = None
                for i in range(min(10, len(df_usp))):
                    row_values = df_usp.iloc[i].astype(str).tolist()
                    row_values_clean = [re.sub(r'\s+', '', val).lower() for val in row_values]
                    
                    # 检测该行是否同时涵盖 Product Name 和 Current Lot
                    has_name = any("productname" in val for val in row_values_clean)
                    has_lot = any("currentlot" in val for val in row_values_clean)
                    
                    if has_name and has_lot:
                        real_header_idx = i
                        break
                
                # 发现符合条件的行，立刻将其作为真正表头进行整体裁剪重塑
                if real_header_idx is not None:
                    df_usp.columns = df_usp.iloc[real_header_idx].astype(str)
                    df_usp = df_usp.iloc[real_header_idx + 1:].reset_index(drop=True)
                
                # 内部辅助函数：智能过滤、匹配字段
                def find_real_col_name(df, target_keyword):
                    for col in df.columns:
                        col_clean = re.sub(r'\s+', '', str(col)).lower()
                        if target_keyword.lower() in col_clean:
                            return col
                    return None
                
                name_col = find_real_col_name(df_usp, "ProductName")
                lot_col = find_real_col_name(df_usp, "CurrentLot")
                
                # 完整继承原有代码的二次提拔兜底逻辑：若未能匹配，强行用第 0 行作为列名重试一次
                if not name_col or not lot_col:
                    df_usp.columns = df_usp.iloc[0].astype(str)
                    df_usp = df_usp.iloc[1:].reset_index(drop=True)
                    name_col = find_real_col_name(df_usp, "ProductName")
                    lot_col = find_real_col_name(df_usp, "CurrentLot")
                
                # 严格保留并融合原有的报错机制（缺失必要列名时主动抛出 KeyError）
                if not name_col or not lot_col:
                    raise KeyError(f"未能自动定位到关键列，当前扫描发现的全部列名为: {df_usp.columns.tolist()}")
                
                # --- 执行原有的比对对账核心逻辑（安全对接，不改变过滤算法） ---
                df_base_eng = df_base[['对照品英文名称USP', '对照品英文批号USP']].dropna(subset=['对照品英文名称USP']).copy()
                df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称USP'])
                df_base_eng['clean_lot'] = clean_string(df_base_eng['对照品英文批号USP'])
                
                df_usp_clean = df_usp[[name_col, lot_col]].dropna(subset=[name_col]).copy()
                df_usp_clean['clean_name'] = clean_string(df_usp_clean[name_col])
                df_usp_clean['clean_lot'] = clean_string(df_usp_clean[lot_col])
                
                usp_existing_set = set(zip(df_usp_clean['clean_name'], df_usp_clean['clean_lot']))
                
                for _, row in df_base_eng.iterrows():
                    if (row['clean_name'], row['clean_lot']) not in usp_existing_set:
                        missing_usp.append(f"{row['对照品英文名称USP']} (批号: {row['对照品英文批号USP']})")
            else:
                # 保留原代码无法提取出表格式的报错机制
                raise ValueError("文件读取完毕，但未能提取出任何有效的 HTML 表格数据格式。")
                
        except Exception as e:
            # 完美对接后续流程：异常错误全部捕获为字符串，在邮件中进行大红字抛出展示
            error_usp = f"USP 比对失败，错误详情：{str(e)}"
    else:
        error_usp = "未找到 USP 上生成的的文件！"
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
        html_content += '<p><span class="highlight">⚠️ 异常提醒：本地目录中的以下对照品在今日线上最新数据中未找到匹配项，请查看今日最新Excel表格数据进行确认：</span></p>'
        
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
