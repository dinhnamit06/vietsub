import os
import re
import time

def parse_srt(srt_path):
    """Đọc file SRT và trả về danh sách các dict chứa index, timestamp, và text."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chuẩn hoá ký tự xuống dòng trên Windows
    content = content.replace('\r\n', '\n')
    blocks = re.split(r'\n{2,}', content.strip())
    subtitles = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2:
            index = lines[0].strip()
            ts_line = lines[1].strip()
            
            ts_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3})', ts_line)
            if ts_match:
                timestamp = ts_match.group(1)
                extra_text = ts_line[ts_match.end():].strip()
                
                text_parts = []
                if extra_text:
                    text_parts.append(extra_text)
                if len(lines) > 2:
                    text_parts.append(" ".join(lines[2:]).strip())
                    
                text = " ".join(text_parts).strip()
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

def _translate_batch_google_free(texts, target_lang="vi"):
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source='auto', target=target_lang)
    # Gộp lại để dịch 1 lần tránh bị Google block IP do gửi quá nhiều request
    joined_text = " \n ".join(texts)
    
    try:
        if len(joined_text) < 4500:
            res = translator.translate(joined_text)
            if res:
                lines = res.split('\n')
                # Google đôi khi tự động gộp dòng, nếu số dòng khớp thì dùng luôn
                if len(lines) == len(texts):
                    return [l.strip() for l in lines]
    except Exception as e:
        print(f"Lỗi dịch gộp Google Free: {e}")
        
    # Nếu dịch gộp thất bại hoặc số lượng dòng bị sai lệch, dịch từng dòng cẩn thận
    translated_texts = []
    for text in texts:
        try:
            if not text.strip():
                translated_texts.append("")
                continue
            res = translator.translate(text)
            translated_texts.append(res if res else "")
            time.sleep(0.2) # Nghỉ chút để tránh bị Google block
        except Exception as e:
            print(f"Lỗi dịch Google Free từng dòng: {e}")
            translated_texts.append(text) # Giữ nguyên văn bản gốc nếu lỗi
            time.sleep(1) # Nghỉ dài hơn nếu bị chặn
            
    return translated_texts

def _translate_batch_gemini(texts, api_keys, prompt_style, target_lang="Tiếng Việt", iso_lang="vi", model_type="gemini", tts_speed=1.2):
    if isinstance(api_keys, str):
        api_keys = [api_keys]
    try:
        from google import genai
        clients = [genai.Client(api_key=k) for k in api_keys if k]
        if not clients:
            raise Exception("No API keys provided")
        current_client_idx = 0
        client = clients[current_client_idx]
        
        prompt = f"""Bạn là một chuyên gia dịch thuật sang {target_lang}.
Hãy dịch danh sách {len(texts)} câu phụ đề dưới đây sang {target_lang}.
Phong cách yêu cầu: {prompt_style}

QUAN TRỌNG NHẤT:
1. KHÔNG in ra bản gốc. KHÔNG in ra lời chào hay suy luận (VD: tuyệt đối không dùng "Okay", "Here is...").
2. KẾT QUẢ PHẢI LÀ ĐÚNG {len(texts)} DÒNG TEXT. Mỗi dòng tương ứng với một câu dịch.
3. Tuyệt đối không giải thích thêm, không gộp dòng.
4. NẾU CÓ TÊN RIÊNG, HỌ NGƯỜI, ĐỊA DANH TIẾNG TRUNG: BẮT BUỘC phải dịch sang âm Hán Việt (Ví dụ: 薛 -> Tiết).
5. LỆNH CẤM: TUYỆT ĐỐI KHÔNG để sót lại bất kỳ ký tự Tiếng Trung/Hán tự nào trong bản dịch. Nếu không biết dịch tên riêng, hãy phiên âm sang chữ cái Latinh của Tiếng Việt. TOÀN BỘ KẾT QUẢ PHẢI LÀ {target_lang.upper()}.
6. BẮT BUỘC GIỮ NGUYÊN SỐ THỨ TỰ Ở ĐẦU MỖI DÒNG (VD: 1. [Bản dịch], 2. [Bản dịch]). KHÔNG ĐƯỢC BỎ QUA hay GỘP CHUNG BẤT KỲ CÂU NÀO DÙ CÂU ĐÓ RẤT NGẮN.
7. YÊU CẦU ĐỘ DÀI LỒNG TIẾNG (TỐI ĐA {tts_speed}x): Để khớp với thời gian trên màn hình, độ dài bản dịch tiếng Việt TỐI ĐA KHÔNG ĐƯỢC VƯỢT QUÁ {int(tts_speed*100)}% số lượng từ/âm tiết so với bản gốc. Hãy ưu tiên dịch súc tích, gãy gọn, đúng ngữ cảnh nhưng không được phép dông dài lê thê vượt quá giới hạn này.
8. DỮ LIỆU GỐC LÀ TỪ STT (Nhận diện giọng nói): Chắc chắn sẽ có lỗi chính tả, sai từ đồng âm hoặc mất chữ. BẠN PHẢI TỰ ĐỘNG HIỂU NGỮ CẢNH, sửa lại các lỗi sai đó và dịch ra một câu {target_lang} hoàn chỉnh.
9. CHỐNG LẶP TỪ & TRỘN DÒNG (RẤT QUAN TRỌNG): Mỗi dòng phải được dịch TÁCH BIỆT theo đúng ý nghĩa của dòng đó. TUYỆT ĐỐI KHÔNG lấy ý nghĩa hoặc chữ của dòng dưới để đắp lên dòng trên. Ví dụ: Dòng 1 là "Nhưng mà", dòng 2 là "anh ấy rất giỏi" -> Dịch đúng: D1="Nhưng mà", D2="anh ấy rất giỏi". Dịch SAI: D1="Nhưng mà anh ấy rất giỏi", D2="anh ấy rất giỏi". Lỗi dịch lặp từ này sẽ phá hỏng toàn bộ video!

Dữ liệu gốc:
"""
        for i, t in enumerate(texts):
            prompt += f"{i+1}. {t}\n"
            
        max_retries = 8
        for attempt in range(max_retries):
            try:
                try:
                    if model_type == "gemini_lite":
                        model_name = "gemini-2.0-flash-lite"
                    else:
                        model_name = "gemini-2.0-flash"
                        
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                except Exception:
                    # Fallback về bản 2.5 mới nhất nếu Google bảo trì bản 2.0
                    if model_type == "gemini_lite":
                        model_name = "gemini-2.5-flash"
                    else:
                        model_name = "gemini-2.5-pro"
                        
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    
                translated_lines = response.text.strip().split('\n')
                
                clean_lines = []
                for line in translated_lines:
                    line = re.sub(r'^\d+\.\s*', '', line).strip()
                    # Lọc sạch chữ Hán lọt lưới
                    line = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', line).strip()
                    
                    # Lọc ảo giác âm nhạc (Whisper hallucinations)
                    hallucinations = ["sáng tác lời", "sáng tác nhạc", "âm nhạc", "lời bài hát", "nhạc nền", "nhạc phim", "bản nhạc", "nhạc cụ", "🎵", "♪", "[", "]"]
                    lower_line = line.lower()
                    if any(h in lower_line for h in hallucinations) and len(line.split()) < 30:
                        line = "" # AI hay lặp lại cụm từ rác rất dài, nên nâng limit lên 30
                        
                    if line:
                        clean_lines.append(line)
                    else:
                        clean_lines.append(" ") # Bắt buộc phải giữ dòng để không bị sai số lượng
                        
                if len(clean_lines) == len(texts):
                    return clean_lines
                else:
                    print(f"Gemini returned {len(clean_lines)} lines, expected {len(texts)}. Lần thử: {attempt+1}/{max_retries}")
                    time.sleep(2)
                    continue # Thử lại
            except Exception as e:
                err_str = str(e)
                print(f"Gemini API Error: {err_str[:200]}...") # In một phần lỗi cho gọn
                
                if "429" in err_str or "quota" in err_str.lower():
                    if len(clients) > 1:
                        current_client_idx = (current_client_idx + 1) % len(clients)
                        client = clients[current_client_idx]
                        print("Switched to backup Gemini API key...")
                        
                        if current_client_idx == 0:
                            wait_time = 15
                            match = re.search(r'retry in ([\d\.]+)s', err_str)
                            if match:
                                wait_time = float(match.group(1)) + 1
                            print(f"Tất cả Key đều hết hạn ngạch. Đợi {wait_time:.1f} giây...")
                            time.sleep(wait_time)
                        else:
                            time.sleep(1)
                    else:
                        wait_time = 15
                        match = re.search(r'retry in ([\d\.]+)s', err_str)
                        if match:
                            wait_time = float(match.group(1)) + 1
                        print(f"Key hết hạn ngạch. Đợi {wait_time:.1f} giây...")
                        time.sleep(wait_time)
                elif "503" in err_str or "unavailable" in err_str.lower():
                    if attempt >= 2:
                        print("Máy chủ Gemini liên tục quá tải. Bỏ qua để chuyển sang API dự phòng...")
                        break
                    wait_time = 3 + attempt * 2
                    print(f"Máy chủ Gemini đang quá tải. Đợi {wait_time} giây...")
                    time.sleep(wait_time)
                else:
                    time.sleep(2)
                continue
                
    except Exception as outer_e:
        print(f"Gemini Setup Error: {outer_e}")
        
    # Báo lỗi nếu dịch thiếu dòng hoặc API sập hoàn toàn sau mọi nỗ lực
    raise Exception("Gemini translation failed or returned incorrect line count.")

def _translate_batch_groq(texts, api_key, prompt_style, target_lang="Tiếng Việt", iso_lang="vi", model="llama-3.3-70b-versatile", tts_speed=1.2):
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
5. LỆNH CẤM: TUYỆT ĐỐI KHÔNG để sót lại bất kỳ ký tự Tiếng Trung/Hán tự nào trong bản dịch. Nếu không biết dịch tên riêng, hãy phiên âm sang chữ cái Latinh của Tiếng Việt. TOÀN BỘ KẾT QUẢ PHẢI LÀ {target_lang.upper()}.
6. BẮT BUỘC GIỮ NGUYÊN SỐ THỨ TỰ Ở ĐẦU MỖI DÒNG (VD: 1. [Bản dịch], 2. [Bản dịch]). KHÔNG ĐƯỢC BỎ QUA hay GỘP CHUNG BẤT KỲ CÂU NÀO DÙ CÂU ĐÓ RẤT NGẮN.
7. YÊU CẦU ĐỘ DÀI LỒNG TIẾNG (TỐI ĐA {tts_speed}x): Để khớp với thời gian trên màn hình, độ dài bản dịch tiếng Việt TỐI ĐA KHÔNG ĐƯỢC VƯỢT QUÁ {int(tts_speed*100)}% số lượng từ/âm tiết so với bản gốc. Hãy ưu tiên dịch súc tích, gãy gọn, đúng ngữ cảnh nhưng không được phép dông dài lê thê vượt quá giới hạn này.
8. DỮ LIỆU GỐC LÀ TỪ STT (Nhận diện giọng nói): Chắc chắn sẽ có lỗi chính tả, sai từ đồng âm hoặc mất chữ. BẠN PHẢI TỰ ĐỘNG HIỂU NGỮ CẢNH, sửa lại các lỗi sai đó và dịch ra một câu {target_lang} hoàn chỉnh, có nghĩa, đúng ngữ pháp và tự nhiên nhất. KHÔNG dịch word-by-word một cách vô nghĩa.

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
                        # Lọc sạch chữ Hán lọt lưới
                        line = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', line).strip()
                        
                        # Lọc ảo giác âm nhạc (Whisper hallucinations)
                        hallucinations = ["sáng tác lời", "sáng tác nhạc", "âm nhạc", "lời bài hát", "nhạc nền", "nhạc phim", "bản nhạc", "nhạc cụ", "🎵", "♪", "[", "]"]
                        lower_line = line.lower()
                        if any(h in lower_line for h in hallucinations) and len(line.split()) < 10:
                            line = ""
                            
                        if line:
                            clean_lines.append(line)
                        else:
                            clean_lines.append(" ") # Bắt buộc phải giữ dòng để không bị sai số lượng
                            
                    if len(clean_lines) == len(texts):
                        return clean_lines
                    else:
                        print(f"Groq returned {len(clean_lines)} lines, expected {len(texts)}. Lần thử: {attempt+1}/{max_retries}")
                        time.sleep(2)
                        continue # Lỗi format, cho phép retry thay vì break
                elif response.status_code == 429:
                    err_text = response.text
                    print(f"Groq Rate Limit (429) hit! Lần thử: {attempt+1}/{max_retries}")
                    if attempt >= 2:
                        print("Groq liên tục giới hạn Rate Limit. Bỏ qua để chuyển sang API dự phòng (Google Free)...")
                        break
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

def translate_srt(srt_path, target_lang='vi', output_dir="temp", overwrite=True, translation_model="google", gemini_api_key="", gemini_prompt="", groq_api_key="", gemini_api_key_backup="", tts_speed=1.2):
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
    google_success = False

    if translation_model == "google_free":
        try:
            print("Using Google Translate (Free) for translation...")
            batch_size = 60
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                translated_texts = _translate_batch_google_free(texts, target_lang=iso_lang)
                for j, t in enumerate(translated_texts):
                    subtitles[i+j]['text'] = t
                print(f"Translated {min(i+batch_size, len(subtitles))}/{len(subtitles)} lines with Google Free...")
                time.sleep(1) # Tránh rate limit của Google Translate
            google_success = True
        except Exception as e:
            raise Exception(f"Lỗi dịch Google Translate Free: {str(e)}")

    if translation_model in ["gemini", "gemini_lite"] and gemini_api_key and not google_success:
        try:
            print(f"Using {translation_model.upper()} API for context-aware translation...")
            batch_size = 60
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                keys = [gemini_api_key]
                if gemini_api_key_backup: keys.append(gemini_api_key_backup)
                translated_texts = _translate_batch_gemini(texts, keys, gemini_prompt, target_lang, iso_lang, model_type=translation_model, tts_speed=tts_speed)
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
            batch_size = 60
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                translated_texts = _translate_batch_groq(texts, groq_api_key, gemini_prompt, target_lang, iso_lang, model=model_id, tts_speed=tts_speed)
                for j, t in enumerate(translated_texts):
                    subtitles[i+j]['text'] = t
                print(f"Translated {min(i+batch_size, len(subtitles))}/{len(subtitles)} lines with Groq...")
                time.sleep(2)
            groq_success = True
        except Exception as e:
            print(f"Lỗi dịch thuật Groq: {str(e)}")
            
    if not gemini_success and not groq_success and not google_success:
        try:
            print("[FALLBACK CUỐI CÙNG] Tất cả API (Gemini/Groq) đều thất bại hoặc quá tải! Tự động chuyển sang Google Translate (Miễn phí)...")
            subtitles = parse_srt(srt_path) # Khôi phục văn bản gốc
            batch_size = 60
            for i in range(0, len(subtitles), batch_size):
                batch = subtitles[i:i+batch_size]
                texts = [sub['text'] for sub in batch]
                translated_texts = _translate_batch_google_free(texts, target_lang=iso_lang)
                for j, t in enumerate(translated_texts):
                    subtitles[i+j]['text'] = t
                print(f"Translated {min(i+batch_size, len(subtitles))}/{len(subtitles)} lines with Google Free...")
                time.sleep(1)
            print("Google Free Translation complete.")
        except Exception as e:
            raise Exception(f"Lỗi dịch thuật nghiêm trọng: {str(e)}")
            
    with open(out_srt, "w", encoding="utf-8-sig") as f:
        for sub in subtitles:
            f.write(f"{sub['index']}\n")
            f.write(f"{sub['timestamp']}\n")
            f.write(f"{sub['text']}\n\n")
            
    print("Translation complete.")
    return out_srt
