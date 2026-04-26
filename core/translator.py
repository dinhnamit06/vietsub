import os
import re
import time

def parse_srt(srt_path):
    """Đọc file SRT và trả về danh sách các dict chứa index, timestamp, và text."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chuẩn hoá ký tự xuống dòng trên Windows
    content = content.replace('\r\n', '\n')
    blocks = content.strip().split('\n\n')
    subtitles = []
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            index = lines[0].strip()
            timestamp = lines[1].strip()
            # Ghép text và xoá khoảng trắng thừa
            text = " ".join(lines[2:]).strip()
            text = re.sub(r"\s+", " ", text)
            subtitles.append({
                'index': index,
                'timestamp': timestamp,
                'text': text
            })
    return subtitles

def clean_tts_text(text: str) -> str:
    """Làm sạch chuỗi trước khi gửi qua TTS để tránh lỗi NoAudioReceived"""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    return text

def _translate_batch_gemini(texts, api_key, prompt_style, target_lang="Tiếng Việt", iso_lang="vi"):
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        prompt = f"""Bạn là một chuyên gia dịch thuật sang {target_lang}.
Hãy dịch danh sách {len(texts)} câu phụ đề dưới đây sang {target_lang}.
Phong cách yêu cầu: {prompt_style}

QUAN TRỌNG NHẤT:
1. KHÔNG in ra bản gốc. KHÔNG in ra lời chào hay suy luận (VD: tuyệt đối không dùng "Okay", "Here is...").
2. KẾT QUẢ PHẢI LÀ ĐÚNG {len(texts)} DÒNG TEXT. Mỗi dòng tương ứng với một câu dịch.
3. Tuyệt đối không giải thích thêm, không gộp dòng.
4. NẾU CÓ TÊN RIÊNG, HỌ NGƯỜI, ĐỊA DANH TIẾNG TRUNG: BẮT BUỘC phải dịch sang âm Hán Việt (Ví dụ: 薛 -> Tiết).
5. LỆNH CẤM: TUYỆT ĐỐI KHÔNG để sót lại bất kỳ ký tự Tiếng Trung/Hán tự nào trong bản dịch. Nếu không biết dịch tên riêng, hãy phiên âm sang chữ cái Latinh của Tiếng Việt. TOÀN BỘ KẾT QUẢ PHẢI LÀ TIẾNG VIỆT.
6. BẮT BUỘC GIỮ NGUYÊN SỐ THỨ TỰ Ở ĐẦU MỖI DÒNG (VD: 1. [Bản dịch], 2. [Bản dịch]). KHÔNG ĐƯỢC BỎ QUA hay GỘP CHUNG BẤT KỲ CÂU NÀO DÙ CÂU ĐÓ RẤT NGẮN.

Dữ liệu gốc:
"""
        for i, t in enumerate(texts):
            prompt += f"{i+1}. {t}\n"
            
        max_retries = 8
        for attempt in range(max_retries):
            try:
                try:
                    model_name = "gemini-2.5-flash"
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                except Exception:
                    model_name = "gemini-2.0-flash"
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    
                translated_lines = response.text.strip().split('\n')
                
                clean_lines = []
                for line in translated_lines:
                    line = re.sub(r'^\d+\.\s*', '', line).strip()
                    if line:
                        clean_lines.append(line)
                        
                if len(clean_lines) == len(texts):
                    return clean_lines
                else:
                    print(f"Gemini returned {len(clean_lines)} lines, expected {len(texts)}. Lần thử: {attempt+1}/{max_retries}")
                    time.sleep(2)
                    continue # Thử lại
            except Exception as e:
                print(f"Gemini API Error: {e}")
                time.sleep(2)
                continue
                
    except Exception as outer_e:
        print(f"Gemini Setup Error: {outer_e}")
        
    # Báo lỗi nếu dịch thiếu dòng hoặc API sập hoàn toàn sau mọi nỗ lực
    raise Exception("Gemini translation failed or returned incorrect line count.")

def _translate_batch_groq(texts, api_key, prompt_style, target_lang="Tiếng Việt", iso_lang="vi", model="llama-3.3-70b-versatile"):
    import requests
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""Bạn là một chuyên gia dịch thuật sang {target_lang}.
Hãy dịch danh sách {len(texts)} câu phụ đề dưới đây sang {target_lang}.
Phong cách yêu cầu: {prompt_style}

QUAN TRỌNG NHẤT:
1. KHÔNG in ra bản gốc. KHÔNG in ra lời chào hay suy luận (VD: tuyệt đối không dùng "Okay", "Here is...").
2. KẾT QUẢ PHẢI LÀ ĐÚNG {len(texts)} DÒNG TEXT. Mỗi dòng tương ứng với một câu dịch.
3. Tuyệt đối không giải thích thêm, không gộp dòng.
4. NẾU CÓ TÊN RIÊNG, HỌ NGƯỜI, ĐỊA DANH TIẾNG TRUNG: BẮT BUỘC phải dịch sang âm Hán Việt (Ví dụ: 薛 -> Tiết).
5. LỆNH CẤM: TUYỆT ĐỐI KHÔNG để sót lại bất kỳ ký tự Tiếng Trung/Hán tự nào trong bản dịch. Nếu không biết dịch tên riêng, hãy phiên âm sang chữ cái Latinh của Tiếng Việt. TOÀN BỘ KẾT QUẢ PHẢI LÀ TIẾNG VIỆT.
6. BẮT BUỘC GIỮ NGUYÊN SỐ THỨ TỰ Ở ĐẦU MỖI DÒNG (VD: 1. [Bản dịch], 2. [Bản dịch]). KHÔNG ĐƯỢC BỎ QUA hay GỘP CHUNG BẤT KỲ CÂU NÀO DÙ CÂU ĐÓ RẤT NGẮN.

Dữ liệu gốc:
"""
        for i, text in enumerate(texts):
            prompt += f"{i+1}. {text}\n"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }

        max_retries = 8
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    # Lọc bỏ thẻ <think> của dòng họ DeepSeek R1
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                    
                    translated_lines = content.strip().split('\n')
                    clean_lines = []
                    for line in translated_lines:
                        line = re.sub(r'^\d+\.\s*', '', line).strip()
                        if line:
                            clean_lines.append(line)
                            
                    if len(clean_lines) == len(texts):
                        return clean_lines
                    else:
                        print(f"Groq returned {len(clean_lines)} lines, expected {len(texts)}. Lần thử: {attempt+1}/{max_retries}")
                        time.sleep(2)
                        continue # Lỗi format, cho phép retry thay vì break
                elif response.status_code == 429:
                    err_text = response.text
                    print(f"Groq Rate Limit (429) hit! Lần thử: {attempt+1}/{max_retries}")
                    wait_time = 12 # Đợi mặc định 12s
                    match = re.search(r'in ([\d\.]+)s', err_text)
                    if match:
                        wait_time = float(match.group(1)) + 1
                    
                    print(f"Đang đợi {wait_time:.1f} giây trước khi thử lại...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Groq API Error: {response.status_code} - {response.text}")
                    time.sleep(2)
                    continue
            except Exception as e:
                print(f"Groq Exception: {e}")
                time.sleep(2)
                continue
        
    except Exception as outer_e:
        print(f"Groq Setup Exception: {outer_e}")
        
    raise Exception("Groq translation failed or returned incorrect line count.")

def translate_srt(srt_path, target_lang='vi', output_dir="temp", overwrite=True, translation_model="google", gemini_api_key="", gemini_prompt="", groq_api_key=""):
    """
    Dịch file SRT sang ngôn ngữ đích.
    Hỗ trợ translation_model: 'google', 'gemini', hoặc 'groq'.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    out_srt = os.path.join(output_dir, f"{base_name}_{target_lang}.srt")
    
    if not overwrite and os.path.exists(out_srt):
        print(f"Cache hit: {out_srt}")
        return out_srt
        
    print(f"Translating {srt_path} using {translation_model.upper()} into {target_lang}...")
    subtitles = parse_srt(srt_path)
    
    # Chuẩn hoá ngôn ngữ cho Google Translate
    lang_map = {
        "Tiếng Việt": "vi",
        "Tiếng Anh": "en",
        "Tiếng Trung": "zh-CN",
        "Tiếng Hàn": "ko",
        "Tiếng Nhật": "ja",
        "Tiếng Thái": "th"
    }
    iso_lang = lang_map.get(target_lang, "vi")
    
    gemini_success = False
    groq_success = False

    if translation_model == "gemini" and gemini_api_key:
        try:
            print("Using Gemini API for context-aware translation...")
            batch_size = 30
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                translated_texts = _translate_batch_gemini(texts, gemini_api_key, gemini_prompt, target_lang, iso_lang)
                for j, t in enumerate(translated_texts):
                    subtitles[i+j]['text'] = t
                print(f"Translated {min(i+batch_size, len(subtitles))}/{len(subtitles)} lines with Gemini...")
                time.sleep(2) # Tránh rate limit
            gemini_success = True
        except Exception as e:
            print(f"[FALLBACK] Lỗi dịch Gemini: {str(e)}. Chuyển sang dùng Groq...")
            subtitles = parse_srt(srt_path) # Khôi phục văn bản gốc
            translation_model = "groq"
            
    if translation_model.startswith("groq") and groq_api_key and not gemini_success:
        try:
            model_id = "qwen/qwen3-32b" if "qwen" in translation_model else "llama-3.3-70b-versatile"
            print(f"Using Groq API ({model_id}) for super-fast translation...")
            batch_size = 20
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                translated_texts = _translate_batch_groq(texts, groq_api_key, gemini_prompt, target_lang, iso_lang, model=model_id)
                for j, t in enumerate(translated_texts):
                    subtitles[i+j]['text'] = t
                print(f"Translated {min(i+batch_size, len(subtitles))}/{len(subtitles)} lines with Groq...")
                time.sleep(2)
            groq_success = True
        except Exception as e:
            raise Exception(f"Lỗi dịch thuật nghiêm trọng: {str(e)}")
            
    with open(out_srt, "w", encoding="utf-8-sig") as f:
        for sub in subtitles:
            f.write(f"{sub['index']}\n")
            f.write(f"{sub['timestamp']}\n")
            f.write(f"{sub['text']}\n\n")
            
    print("Translation complete.")
    return out_srt
