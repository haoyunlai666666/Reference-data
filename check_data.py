import os
import re
import pandas as pd

def clean_string(series):
    """去除字符串中所有的空格、换行符等，转换为大写，并转为字符串类型"""
    return series.astype(str).str.replace(r'\s+', '', regex=True).str.strip().str.upper()

def check_datasets():
    # -----------------------------------------------------------------
    # 1. 定义文件路径
    # -----------------------------------------------------------------
    base_file = "现有全部对照品目录.xlsx"
    chp_file  = "国家药品标准物质目录_全量在售.xlsx"
    edqm_file = "EDQM_Catalog_Output.xlsx"
    usp_file  = "usprefstd.xls"
    
    # 初始化缺失数据列表
    missing_chp = []
    missing_edqm = []
    missing_usp = []
    
    # -----------------------------------------------------------------
    # 2. 读取并比对：ChP 中文对照品比对 (duibi.py)
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(chp_file):
        try:
            df_base = pd.read_excel(base_file)
            df_chp  = pd.read_excel(chp_file)
            
            # 清理本地对照品数据 (提取中文名和中文批号，并去除空格)
            df_base_chp = df_base[['对照品中文名称', '对照品中文批号Chp']].dropna(subset=['对照品中文名称']).copy()
            df_base_chp['clean_name'] = clean_string(df_base_chp['对照品中文名称'])
            df_base_chp['clean_lot']  = clean_string(df_base_chp['对照品中文批号Chp'])
            
            # 清理新生成的 ChP 数据
            df_chp_clean = df_chp[['品名', '批号']].dropna(subset=['品名']).copy()
            df_chp_clean['clean_name'] = clean_string(df_chp_clean['品名'])
            df_chp_clean['clean_lot']  = clean_string(df_chp_clean['批号'])
            
            # 创建线上已有的 (品名+批号) 集合，用于秒级匹配
            chp_existing_set = set(zip(df_chp_clean['clean_name'], df_chp_clean['clean_lot']))
            
            # 逐行核对本地数据是否在其中
            for _, row in df_base_chp.iterrows():
                if (row['clean_name'], row['clean_lot']) not in chp_existing_set:
                    # 只要有一列或两列对不上，就记录
                    missing_chp.append(f"{row['对照品中文名称']} (批号: {row['对照品中文批号Chp']})")
        except Exception as e:
            print(f"ChP 比对执行出错: {e}")
    else:
        print("未找到 现有全部对照品目录.xlsx 或 国家药品标准物质目录_全量在售.xlsx，跳过 ChP 比对。")

    # -----------------------------------------------------------------
    # 3. 读取并比对：EDQM 英文对照品比对 (zhuaqu.py)
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(edqm_file):
        try:
            df_base = pd.read_excel(base_file)
            df_edqm = pd.read_excel(edqm_file)
            
            # 清理本地对照品数据 (提取英文名和英文批号，并去除空格)
            df_base_eng = df_base[['对照品英文名称', '对照品英文批号EP-USP']].dropna(subset=['对照品英文名称']).copy()
            df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称'])
            df_base_eng['clean_lot']  = clean_string(df_base_eng['对照品英文批号EP-USP'])
            
            # 清理新生成的 EDQM 数据 (注意包含空格的列名 'Batc h n°')
            df_edqm_clean = df_edqm[['Reference Standard', 'Batc h n°']].dropna(subset=['Reference Standard']).copy()
            df_edqm_clean['clean_name'] = clean_string(df_edqm_clean['Reference Standard'])
            df_edqm_clean['clean_lot']  = clean_string(df_edqm_clean['Batc h n°'])
            
            edqm_existing_set = set(zip(df_edqm_clean['clean_name'], df_edqm_clean['clean_lot']))
            
            for _, row in df_base_eng.iterrows():
                if (row['clean_name'], row['clean_lot']) not in edqm_existing_set:
                    missing_edqm.append(f"{row['对照品英文名称']} (批号: {row['对照品英文批号EP-USP']})")
        except Exception as e:
            print(f"EDQM 比对执行出错: {e}")

    # -----------------------------------------------------------------
    # 4. 读取并比对：USP 英文对照品比对 (daochuusp.py)
    # -----------------------------------------------------------------
    if os.path.exists(base_file) and os.path.exists(usp_file):
        try:
            df_base = pd.read_excel(base_file)
            # 使用 xlrd/openpyxl 自动兼容旧版 xls
            df_usp  = pd.read_excel(usp_file)
            
            df_base_eng = df_base[['对照品英文名称', '对照品英文批号EP-USP']].dropna(subset=['对照品英文名称']).copy()
            df_base_eng['clean_name'] = clean_string(df_base_eng['对照品英文名称'])
            df_base_eng['clean_lot']  = clean_string(df_base_eng['对照品英文批号EP-USP'])
            
            # 清理新生成的 USP 数据
            df_usp_clean = df_usp[['Product Name', 'Current Lot']].dropna(subset=['Product Name']).copy()
            df_usp_clean['clean_name'] = clean_string(df_usp_clean['Product Name'])
            df_usp_clean['clean_lot']  = clean_string(df_usp_clean['Current Lot'])
            
            usp_existing_set = set(zip(df_usp_clean['clean_name'], df_usp_clean['clean_lot']))
            
            for _, row in df_base_eng.iterrows():
                if (row['clean_name'], row['clean_lot']) not in usp_existing_set:
                    missing_usp.append(f"{row['对照品英文名称']} (批号: {row['对照品英文批号EP-USP']})")
        except Exception as e:
            print(f"USP 比对执行出错: {e}")

    # -----------------------------------------------------------------
    # 5. 生成 HTML 邮件正文
    # -----------------------------------------------------------------
    # 获取原本保存在本地或预设的标准文本（这里是之前你 yml 里的默认文本结构）
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.6; color: #333333; }
            .warning-block { background-color: #FFF9E6; border-left: 5px solid #FFCC00; padding: 15px; margin: 15px 0; }
            .highlight { background-color: yellow; font-weight: bold; padding: 2px 5px; }
            ul { padding-left: 20px; }
            li { margin-bottom: 5px; }
        </style>
    </head>
    <body>
        <p>您好：</p>
        <p>附件为今日自动运行 Python 脚本爬取并生成的对照品数据报表，请查收。</p>
    """
    
    # 判断是否存在缺失
    has_missing = len(missing_chp) > 0 or len(missing_edqm) > 0 or len(missing_usp) > 0
    
    if has_missing:
        html_content += '<div class="warning-block">'
        html_content += '<p><span class="highlight">⚠️ 警告：本地目录中的以下对照品在今日最新爬取的数据中未找到，请及时核对：</span></p>'
        
        if missing_chp:
            html_content += '<strong>【国家药品标准物质目录 (ChP)】缺失：</strong>'
            html_content += '<ul>'
            for item in missing_chp:
                html_content += f'<li>{item}</li>'
            html_content += '</ul>'
            
        if missing_edqm:
            html_content += '<strong>【EDQM 欧洲药典对照品目录】缺失：</strong>'
            html_content += '<ul>'
            for item in missing_edqm:
                html_content += f'<li>{item}</li>'
            html_content += '</ul>'
            
        if missing_usp:
            html_content += '<strong>【USP 美国药典对照品目录】缺失：</strong>'
            html_content += '<ul>'
            for item in missing_usp:
                html_content += f'<li>{item}</li>'
            html_content += '</ul>'
            
        html_content += '</div>'
    else:
        html_content += '<p style="color: green; font-weight: bold;">✓ 经比对，本地基准文件中的所有对照品在今日爬取的数据中完全存在，无异常。</p>'
        
    html_content += """
        <br>
        <p>祝好，<br>自动化对账系统</p>
    </body>
    </html>
    """
    
    # 将拼接好的 HTML 正文写入临时文件，供 GitHub Actions 读取
    with open("mail_body.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("对账完成，mail_body.html 生成成功！")

if __name__ == "__main__":
    check_datasets()
