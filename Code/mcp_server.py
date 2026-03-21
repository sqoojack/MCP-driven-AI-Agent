# Code/mcp_server.py
from mcp.server.fastmcp import FastMCP
import os
# 載入你原有的生成邏輯模組
# 假設你的 create_ppt.py 中有一個主函數 generate_presentation(data)
from create_ppt import generate_presentation 
from aws_utils import AWSManager

# 初始化 MCP 伺服器
mcp = FastMCP("PPT_Generator_Agent")

# AWS S3 儲存桶名稱 (需替換為你實際的 Bucket)
AWS_BUCKET = "your-ppt-agent-bucket"
aws_manager = AWSManager(bucket_name=AWS_BUCKET)

@mcp.tool()
def create_ppt_from_text(topic: str, content: str, template_type: str = "default") -> str:
    """
    (MCP Tool) 根據提供的主題與內容生成 PowerPoint 簡報，並回傳下載連結
    
    Args:
        topic: 簡報主題
        content: 簡報大綱與詳細內容
        template_type: 佈景主題風格
    """
    try:
        # 1. 呼叫你原有的程式碼邏輯生成 PPT
        # 這裡需對應你 create_ppt.py 實際的 API 呼叫方式
        output_filename = f"{topic.replace(' ', '_')}.pptx"
        local_output_path = os.path.join("Output", output_filename)
        
        # 假設 generate_presentation 是你的核心生成函數
        generate_presentation(topic=topic, content=content, template=template_type, output_path=local_output_path)
        
        # 2. 將產生的 PPT 上傳至 AWS S3
        aws_manager.upload_file(local_output_path, output_filename)
        
        # 3. 取得下載連結
        download_url = aws_manager.generate_presigned_url(output_filename)
        
        return f"簡報生成成功！\n主題: {topic}\n下載連結: {download_url} (連結 1 小時內有效)"
        
    except Exception as e:
        return f"生成簡報時發生錯誤: {str(e)}"

if __name__ == "__main__":
    # 啟動 MCP 標準輸入輸出伺服器，讓外部 Agent 可以連接
    mcp.run_stdio_async()