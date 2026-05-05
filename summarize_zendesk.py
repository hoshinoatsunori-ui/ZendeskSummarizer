import os
import time
import sys
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google import genai

# Windowsコンソールでの日本語文字化け・エンコードエラー対策
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# --- 1. 環境設定の読み込み ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
TARGET_DIR = os.getenv("TARGET_DIR")
MODEL_ID = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not API_KEY or not TARGET_DIR:
    raise ValueError("GEMINI_API_KEY または TARGET_DIR が .env に設定されていません。")

# クライアント初期化
client = genai.Client(api_key=API_KEY)

# 流量制御用：15秒に1回（1分間に最大4リクエストの安全圏）
REQUEST_INTERVAL = 15 

def extract_zendesk_content(file_path):
    """Zendesk HTMLから本文を抽出（UTF-8固定）"""
    try:
        # errors='ignore' または 'replace' で不正な文字による停止を防ぐ
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            soup = BeautifulSoup(f, 'html.parser')
            
            # スタイルやスクリプトなどのノイズを削除
            for element in soup(["script", "style", "meta", "link", "noscript"]):
                element.extract()
            
            content_parts = []
            
            # タイトルから件名を取得[cite: 4]
            title_tag = soup.find('title')
            if title_tag:
                content_parts.append(f"Subject: {title_tag.get_text(strip=True)}")
            
            # 本文が含まれる可能性の高いクラスを抽出[cite: 1, 2, 4]
            main_body = soup.find_all(['div', 'article'], 
                                   class_=['ck-content', 'hjkkBUi48PQ20mlsqeQtBQzu9Uioa_BY', 'zd-comment'])
            
            if main_body:
                for section in main_body:
                    text = section.get_text(separator='\n', strip=True)
                    if text:
                        content_parts.append(text)
            else:
                # 構造が異なる場合のフォールバック
                body = soup.find('body')
                if body:
                    content_parts.append(body.get_text(separator='\n', strip=True))
            
            return "\n\n".join(content_parts)
    except Exception as e:
        # エラー出力自体で落ちないように str() をラップ
        print(f"  [Warning] ファイル読み込み失敗: {file_path} (Error: {repr(e)})")
        return ""

def ask_gemini_with_strict_quota(combined_text, file_list):
    """リトライとエンコード対策を施したAPI呼び出し"""
    prompt = f"""
    Zendeskの技術サポート履歴を分析し、Markdown形式でレポートを作成してください。
    
    # 案件要約
    ## 1. 議論していた内容
    - 技術的課題（モジュールの挙動、エラー、設定等）の具体的な内容
    ## 2. 結論
    - 解決策、回避策、または現在のステータス
    ## 3. 要約
    - エンジニアが状況を即座に把握できるよう300文字程度で。
    ## 4. 最も参照すべき根拠ファイル
    - ファイル名: {file_list} から1つ選択
    - 理由: なぜそのファイルが重要か
    
    ---
    やり取りのデータ：
    {combined_text[:30000]}
    """

    max_retries = 5
    base_delay = 30 

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            return response.text
        except Exception as e:
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                delay = base_delay * (2 ** attempt)
                print(f"  !! Rate Limit発生。{delay}秒待機してリトライします... ({attempt+1}/{max_retries})")
                time.sleep(delay)
            elif "503" in err_msg or "UNAVAILABLE" in err_msg:
                delay = base_delay * (2 ** attempt)
                print(f"  !! サーバー混雑(503)。{delay}秒待機してリトライします... ({attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                # エラーメッセージに非ASCII文字が含まれても print で落ちないように repr() を使用
                print(f"  !! APIエラー: {repr(e)}")
                return None
    return None

def run_process():
    if not os.path.exists(TARGET_DIR):
        print(f"エラー: パスが存在しません: {TARGET_DIR}")
        return

    print(f"処理開始: {TARGET_DIR}")
    last_request_time = 0

    for root, _, files in os.walk(TARGET_DIR):
        if "summary.md" in files:
            continue

        html_files = [f for f in files if f.lower().endswith('.html')]
        if not html_files:
            continue
            
        combined_text = ""
        for html_file in html_files:
            text = extract_zendesk_content(os.path.join(root, html_file))
            if text:
                combined_text += f"\n--- FILE: {html_file} ---\n{text}\n"

        if not combined_text.strip():
            continue

        # スロットリング：前回の実行から15秒経過するまで待機
        elapsed = time.time() - last_request_time
        if elapsed < REQUEST_INTERVAL:
            time.sleep(REQUEST_INTERVAL - elapsed)

        # rootパスに日本語が含まれる場合を考慮して表示
        print(f"解析中: {os.path.basename(root)}")
        
        summary_md = ask_gemini_with_strict_quota(combined_text, html_files)
        last_request_time = time.time()

        if summary_md:
            output_path = os.path.join(root, "summary.md")
            # 書き込み時も明示的に UTF-8 を指定
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(summary_md)
            print(f"  -> [成功] summary.md を保存しました")
        else:
            print(f"  -> [失敗] スキップしました")

if __name__ == "__main__":
    run_process()
    print("\n完了しました。")