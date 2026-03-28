# python -m streamlit run Code/main.py
import boto3
from botocore.exceptions import ClientError
from utils import st, os, json
from config import save_path
from create_ppt import generate_ppt_from_report, generate_report
from ppt_draw import create_node, generate_diagram_to_ppt
from uploaded_file import process_uploaded_files
from aws_utils import AWSManager

def main():
    aws_handler = AWSManager()
    st.title("MCP-driven AI Agent - PPT Generator")

    uploaded_files = st.file_uploader(
        "**Upload Files (Supported: PDF, PPT, Word, Images, MP3, MP4)**",
        type=["py", "txt", "pdf", "jpg", "jpeg", "png", "docx", "doc", "pptx", "ppt", "mp3", "mp4"],
        accept_multiple_files=True
    )
    
    if not uploaded_files:
        st.info("Please upload files to proceed.")
        return
    
    with st.expander("⚙️ **PPT Settings & Model Configuration**", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🤖 Model Parameters")
            text_model_options = [    
                "deepseek-r1:8b",
                "qwen3:14b",
                "qwen2.5:7b",
                "gemma3:27b",
                "deepseek-r1:32b",
                "llava:7b",
                "llava-llama3:8b",
                "llama4:16x17b",
                "gpt-oss:20b",
            ]
            selected_text_model = st.selectbox("**Select Text Model**", text_model_options, index=0)
            
            img_model_options = [    
                "qwen3-vl:8b",
                "gemma3:27b",
                "llava:7b",
                "llava-llama3:8b",
                "llama4:16x17b"
            ]
            selected_img_model = st.selectbox("**Select Image Recognition Model**", img_model_options, index=0)
            
            temperature = st.slider("**Temperature**", min_value=0.0, max_value=1.0, value=0.7, step=0.01)

        with col2:
            st.markdown("### 📊 Content Structure")
            ppt_pages = st.slider("**Number of PPT Pages**", min_value=1, max_value=20, value=5)    
            font_size = st.slider("**Font Size**", min_value=12, max_value=32, value=18)
            level = st.radio(
                "**Target Audience Level**", 
                ["Beginner", "Novice", "Intermediate", "Advanced", "Expert"], 
                index=0
            )
            language = st.radio(
                "**Output Language**", 
                ["English", "Traditional Chinese", "Japanese", "Korean"], 
                index=0
            )

    # 加上 type="primary" 突顯主按鈕
    if st.button("📥 Generate PPT", type="primary"):
        
        with st.status("Backing up original files to cloud...") as s3_status:
            for uploaded_file in uploaded_files:
                temp_dir = "temp_uploads"
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                object_name = f"uploads/{uploaded_file.name}"
                if aws_handler.upload_file(temp_path, object_name):
                    st.write(f"Backed up: {uploaded_file.name}")
            s3_status.update(label="Original files backup completed", state="complete")
            
        with st.spinner("Analyzing files and generating report..."):
            all_texts = [t for t in process_uploaded_files(uploaded_files, selected_img_model) if t and t.strip()]
            status = st.empty()
            
            structure = generate_report(
                all_texts, 
                st_status=status, 
                num_pages=ppt_pages, 
                level=level, 
                language=language,
                model=selected_text_model,
                temperature=temperature
            )

            st.json(structure)

            generate_ppt_from_report(structure, save_path, font_size=font_size)

            nodes = create_node(
                json.dumps(structure, ensure_ascii=False),
                model=selected_text_model, 
                temperature=temperature
            )
            st.markdown("**Generated Nodes:**")
            st.json(nodes)
            generate_diagram_to_ppt(save_path, status, nodes)
            
        with st.spinner("Uploading generated PPT to cloud..."):
            file_name = os.path.basename(save_path)
            success = aws_handler.upload_file(save_path, f"generated_ppt/{file_name}")
        
        if success:
            s3_url = aws_handler.get_download_url(f"generated_ppt/{file_name}")
            st.success("AWS Cloud Backup Successful ✅")
            st.markdown(f"### [🔗 Download PPT from AWS]({s3_url})")

        
if __name__ == "__main__":
    main()