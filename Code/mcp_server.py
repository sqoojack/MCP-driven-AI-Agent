# Code/mcp_server.py
import os
import json
import sys
import contextlib
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from create_ppt import generate_report, generate_ppt_from_report
from ppt_draw import create_node, generate_diagram_to_ppt
from aws_utils import AWSManager

# 初始化 MCP 伺服器
mcp = FastMCP("PPT_Generator_Agent")

@mcp.tool()
def create_ppt_from_text(
    topic: str, 
    content: str, 
    num_pages: int = 5, 
    level: str = "中階者", 
    language: str = "繁體中文",
    model_name: str = "gpt-oss:20b",
    temperature: float = 0.7
) -> str:
    """
    (MCP Tool) 根據提供的主題與內容生成 PowerPoint 簡報（包含節點圖），並回傳 AWS 下載連結。
    """
    
    # 將 stdout 導向 stderr，防止底層程式碼中的 print() 污染 MCP 的 JSON-RPC 通訊
    with contextlib.redirect_stdout(sys.stderr):
        try:
            
            # 延遲初始化：將 AWS 連線移至函式內，避免啟動時因網路或權限檢測造成阻塞
            aws_handler = AWSManager()
            
            # 處理輸出的檔案路徑
            output_filename = f"{topic.replace(' ', '_')}.pptx"
            os.makedirs("Output", exist_ok=True)
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
            
            s3_key = f"generated_ppt/{output_filename}"
            is_success = aws_handler.upload_file(local_output_path, s3_key)
            
            if not is_success:
                return "錯誤：上傳 AWS S3 失敗，請檢查 .env 的金鑰與連線狀態。"
            
            download_url = aws_handler.get_download_url(s3_key)
            
            return f"簡報與圖表生成成功！\n主題: {topic}\n總頁數: {len(structure_json.get('slides', []))}\n下載連結: {download_url}\n(連結 1 小時內有效)"
            
        except Exception as e:
            return f"生成簡報時發生系統錯誤: {str(e)}"

if __name__ == "__main__":
    mcp.run()