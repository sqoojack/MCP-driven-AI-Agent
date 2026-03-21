
# python -m streamlit run Code/main.py
from utils import st, os, json
from config import save_path  # 移除 img_model, 改由 UI 動態取得
from create_ppt import generate_ppt_from_report, generate_report
from ppt_draw import create_node, generate_diagram_to_ppt
from uploaded_file import process_uploaded_files

def main():
    st.title("AI Agent -- 簡報自動生成器")

    uploaded_files = st.file_uploader("**請上傳檔案 (支援pdf, ppt, word, 圖檔, mp3, mp4)**",
                                    type=["py", "txt", "pdf", "jpg", "jpeg", "png", "docx", "doc", "pptx", "ppt", "mp3", "mp4"],
                                    accept_multiple_files=True)
    
    if not uploaded_files:
        return
    
    with st.expander("⚙️ **PPT相關設定與模型選擇**", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # 新增：模型與參數設定
            st.markdown("### 🤖 模型參數設定")
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
            selected_text_model = st.selectbox("**請選擇使用模型**", text_model_options, index=0)
            
            img_model_options = [    
                "qwen3-vl:8b",
                "gemma3:27b",
                "llava:7b",
                "llava-llama3:8b",
                "llama4:16x17b"
            ]
            selected_img_model = st.selectbox("**請選擇影像辨識模型**", img_model_options, index=0)
            
            temperature = st.slider("**設定模型的Temperature**", min_value=0.0, max_value=1.0, value=0.7, step=0.01)

        with col2:
            # 原有：PPT 內容設定
            st.markdown("### 📊 內容架構設定")
            ppt_pages = st.slider("**請選擇要產出的 PPT 頁數**", min_value=1, max_value=20, value=5)    
            font_size = st.slider("**請選擇PPT字體大小**", min_value=12, max_value=32, value=18)
            level = st.radio("**請選擇PPT的知識層級**", ["入門者", "初學者", "中階者", "高階者", "專家"], index=0)
            language = st.radio("**請選擇語言**", ["繁體中文", "English", "Japanese", "Korean"], index=0)
            
        if st.button("✅ 儲存設定"):
            st.success("已儲存設定!")

    if st.button("📥 產出簡報 PPT"):
        with st.spinner("正在分析並產生報告..."):
            # 將 UI 選定的影像模型傳入
            all_texts = [t for t in process_uploaded_files(uploaded_files, selected_img_model) if t and t.strip()]
            status = st.empty()
            
            # 將 UI 選定的文本模型與 Temperature 傳入
            structure = generate_report(
                all_texts, 
                st_status=status, 
                num_pages=ppt_pages, 
                level=level, 
                language=language,
                model=selected_text_model,    # 新增傳遞的參數
                temperature=temperature       # 新增傳遞的參數
            )

            st.json(structure)

            generate_ppt_from_report(structure, save_path, font_size=font_size)

            nodes = create_node(
                json.dumps(structure, ensure_ascii=False), # 將 dict 轉回字串傳遞給 prompt
                model=selected_text_model, 
                temperature=temperature
            )
            st.markdown("**以下是 nodes 部分**")
            st.json(nodes)
            generate_diagram_to_ppt(save_path, status, nodes)

        st.success(f"✅ 報表已儲存至：`{save_path}`")
        with open(save_path, "rb") as f:
            st.download_button("📥 下載PPT", f, file_name=os.path.basename(save_path))
        
if __name__ == "__main__":
    main()