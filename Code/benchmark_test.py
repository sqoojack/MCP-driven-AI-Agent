# python Code/benchmark_test.py
import time
import os
from mcp_server import create_ppt_from_text

def run_benchmark(iterations=50):
    # 準備測試用的標準輸入內容 (必須大於 10 個字以通過防呆檢查)
    test_content = """
    人工智慧(AI) 與大型語言模型 (LLM) 正在改變現代軟體工程的架構。
    透過導入 MCP (Model Context Protocol)，我們可以將原本封閉的本機端腳本，
    轉變為標準化的 AI Agent 工具。本報告將探討 AI Agent 的自動化工作流、
    AWS S3 雲端整合，以及如何透過結構化 JSON 輸出達成動態圖表繪製。
    """
    
    print("="*50)
    print(f"執行 AI Agent 壓力測試 (共 {iterations} 次)")
    print("="*50)

    success_count = 0
    total_time = 0.0
    failed_logs = []

    for i in range(1, iterations + 1):
        print(f"▶ 正在執行第 {i}/{iterations} 次測試...", end="", flush=True)
        start_time = time.time()

        try:
            # 直接呼叫你封裝好的 MCP Tool 邏輯
            # 為了測試速度與穩定性，頁數設為 3，溫度設為 0.1
            result = create_ppt_from_text(
                topic=f"Benchmark_Test_{i}",
                content=test_content,
                source_file_paths=[],  
                num_pages=3,
                level="專家",
                language="繁體中文",
                model_name="deepseek-r1:8b", 
                temperature=0.1
            )

            elapsed_time = time.time() - start_time
            total_time += elapsed_time

            # 根據你 mcp_server.py 的回傳字串特徵來判斷成功與否
            if "生成成功" in result or "下載連結" in result:
                success_count += 1
                print(f" [成功] (耗時: {elapsed_time:.2f} 秒)")
            else:
                print(f" [失敗] (耗時: {elapsed_time:.2f} 秒)\n  >> 實際錯誤回傳: {result}")
                failed_logs.append(f"第 {i} 次失敗原因: {result.splitlines()[0]}")

        except Exception as e:
            elapsed_time = time.time() - start_time
            total_time += elapsed_time
            print(f" [系統異常崩潰] (耗時: {elapsed_time:.2f} 秒)")
            failed_logs.append(f"第 {i} 次崩潰: {str(e)}")
            
        # 讓本地 GPU 稍微喘息，避免過熱或 VRAM 釋放不及
        time.sleep(2) 

    # 計算統計數據
    success_rate = (success_count / iterations) * 100
    avg_time = (total_time / iterations) if iterations > 0 else 0

    print("\n" + "="*50)
    print("📊 AI Agent 基準測試報告 (Benchmark Report)")
    print("="*50)
    print(f"🔹 總測試次數: {iterations} 次")
    print(f"🔹 成功次數:   {success_count} 次")
    print(f"🔹 失敗次數:   {iterations - success_count} 次")
    print(f"🎯 成功率 (Reliability): {success_rate:.2f}%")
    print(f"⏱️ 總執行耗時: {total_time:.2f} 秒")
    print(f"⏱️ 平均耗時 (Avg Latency): {avg_time:.2f} 秒/次")
    print("="*50)

    if failed_logs:
        print("\n⚠️ 錯誤摘要紀錄:")
        for log in failed_logs[:5]: # 最多印出前 5 個錯誤避免洗頻
            print(f"  - {log}")
        if len(failed_logs) > 5:
            print(f"  - ...及其他 {len(failed_logs) - 5} 個錯誤")

if __name__ == "__main__":
    run_benchmark(iterations=50)