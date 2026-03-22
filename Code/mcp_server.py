# Code/mcp_server.py
import os
import json
import sys
import contextlib
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# 初始化 MCP 伺服器
mcp = FastMCP("PPT_Generator_Agent")

@mcp.tool()
def create_ppt_from_text(
    topic: str, 
    content: str, 
    source_file_paths: list[str] = None,  # 補回缺失的參數，供 benchmark 與真實檔案上傳使用
    num_pages: int = 5, 
    level: str = "中階者", 
    language: str = "繁體中文",
    model_name: str = "gpt-oss:20b",
    temperature: float = 0.7
) -> str:
    """
    (MCP Tool) 根據提供的主題與內容生成 PowerPoint 簡報（包含節點圖），並將原始檔案與簡報皆上傳至 AWS。
    """
    if source_file_paths is None:
        source_file_paths = []
    
    with contextlib.redirect_stdout(sys.stderr):
        try:
            from create_ppt import generate_report, generate_ppt_from_report
            from ppt_draw import create_node, generate_diagram_to_ppt
            from aws_utils import AWSManager
            
            aws_handler = AWSManager()
            os.makedirs("Output", exist_ok=True)
            
            safe_topic = topic.replace(' ', '_')
            backup_info_list = []
            
            for file_path in source_file_paths:
                if file_path and os.path.exists(file_path):
                    file_name = os.path.basename(file_path)
                    s3_source_key = f"uploads/{file_name}"
                    
                    # 執行上傳
                    is_source_success = aws_handler.upload_file(file_path, s3_source_key)
                    if not is_source_success:
                        return f"錯誤：上傳原始參考文件 {file_name} 至 AWS S3 失敗，請檢查金鑰與連線。"
                    
                    backup_info_list.append(s3_source_key)
            backup_info = ""
            if backup_info_list:
                backup_info = f"\n原始檔案備份路徑:\n - " + "\n - ".join(backup_info_list)

            # 2. 開始生成簡報
            output_filename = f"{safe_topic}.pptx"
            local_output_path = os.path.join("Output", output_filename)
            
            structure_json = generate_report(
                all_texts=[content],
                st_status=None,  
                num_pages=num_pages,
                level=level,
                language=language,
                model=model_name,
                temperature=temperature
            )
            
            generate_ppt_from_report(structure_json, local_output_path)
            
            nodes = create_node(
                json.dumps(structure_json, ensure_ascii=False),
                model=model_name, 
                temperature=0.7
            )
            generate_diagram_to_ppt(local_output_path, None, nodes)
            
            # 3. 將生成的 PPT 上傳至 S3
            s3_ppt_key = f"generated_ppt/{output_filename}"
            is_ppt_success = aws_handler.upload_file(local_output_path, s3_ppt_key)
            
            if not is_ppt_success:
                return "錯誤：上傳生成的 PPT 至 AWS S3 失敗。"
            
            download_url = aws_handler.get_download_url(s3_ppt_key)
            
            return f"簡報與圖表生成成功！\n主題: {topic}\n總頁數: {len(structure_json.get('slides', []))}{backup_info}\n簡報下載連結: {download_url}\n(連結 1 小時內有效)"
            
        except Exception as e:
            return f"生成簡報時發生系統錯誤: {str(e)}"

if __name__ == "__main__":
    mcp.run()