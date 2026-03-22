# PPT-Agent: Cloud-Native Multi-Modal Presentation AI Agent

This project transforms a standalone Web-based PPT generation tool into a scalable **Cloud Microservice** and a standardized **AI Agent Tool**. By integrating **AWS S3** for persistent storage and the **Model Context Protocol (MCP)** for standardized communication, this agent can be invoked by external AI environments like **Cursor** or **Claude Desktop**, in addition to its native Streamlit interface.

## Key Features

* **Multi-File PPT Generation**: Automatically parse multiple uploaded files to generate structured PowerPoint presentations.
* **AWS S3 Integration**: Securely store user-uploaded files and generated PPTs in the cloud, providing temporary download links.
* **MCP Standardization**: Encapsulates the core logic into an **MCP Server**, allowing any MCP-compatible Agent to call the PPT generation tool via JSON-RPC.
* **Dynamic Model Switching**: Support for various LLMs (e.g., `deepseek-r1:8b`) with adjustable parameters like temperature and slide count directly through UI or Agent prompts.

## Tech Stack

* **Frontend**: Streamlit
* **Storage**: Amazon S3 (Boto3)
* **Protocol**: Model Context Protocol (MCP)
* **Language**: Python 3.x
* **Agent Environments**: Cursor / Claude Desktop

## Project Structure

```text
Create_PPT_Project/
├── Code/
│   ├── main.py            # Streamlit UI 
│   ├── mcp_server.py      # MCP Server 
│   ├── aws_utils.py       # AWS S3 Storage 
│   └── ...                # Core Logic Modules
├── .env                   # AWS Keys
└── requirements.txt       # Project Dependencies
```

## Setup & Installation

### 1. Prerequisites
Install the required Python packages:
```bash
pip install boto3 mcp streamlit
```

### 2. AWS Configuration
Create a `.env` file in the root directory and provide your AWS credentials:
```env
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
S3_BUCKET_NAME=your_bucket_name
```
*Note: Ensure the IAM user has `S3:PutObject` and `S3:GetObject` permissions.*

### 3. MCP Server Configuration (for Cursor)
To use the Agent within Cursor:
1.  **Open Cursor Settings**: `Cmd + Shift + J`
2.  **Navigate to MCP**: Features -> MCP -> **+ Add New MCP Server**
3.  **Enter Settings**:
    * **Name**: `PPT-Agent`
    * **Type**: `command`
    * **Command**: 
        ```bash
        # Replace with your actual python and script paths
        /path/to/anaconda/bin/python /path/to/project/Code/mcp_server.py
        ```

## 📖 Usage

### Mode 1: Streamlit UI
Run the web interface to manually upload files and generate PPTs:
```bash
python -m streamlit run Code/main.py
```

### Mode 2: MCP Agent (Cursor/Claude)
Interact with the Agent using natural language. 

**Prompt Example:**
> "Use the `create_ppt_from_text` tool to convert my uploaded files into a PPT. Set the language to English, length to 8 slides. Use the `deepseek-r1:8b` model with a temperature of 0.1. Provide the S3 download link once finished."

---

**Would you like me to help you draft the `aws_utils.py` file or define the specific tool schemas for the `mcp_server.py`?**