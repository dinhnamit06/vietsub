import os
from pydub import AudioSegment
from .translator import parse_srt

VOICE_MAP = {
    "Nữ CapCut (VN)": "tiktok:BV074_streaming",
    "Nam CapCut (VN)": "tiktok:BV075_streaming",
    "Nữ CapCut (US)": "tiktok:en_us_001",
    "Nam CapCut (US)": "tiktok:en_us_006",
    "Microsoft Hoài My (Nữ VN)": "edge:vi-VN-HoaiMyNeural",
    "Microsoft Nam Minh (Nam VN)": "edge:vi-VN-NamMinhNeural",
    "Microsoft Jenny (Nữ US)": "edge:en-US-JennyNeural",
    "Chị Google (VN)": "gtts:vi"
}

def parse_time_to_ms(time_str):
    """Chuyển đổi định dạng thời gian SRT (HH:MM:SS,mmm) sang milliseconds"""
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)

import requests
import json
import base64


def _generate_audio_tiktok(text, voice_id, output_file, session_id):
    if not session_id:
        raise Exception("Vui lòng cung cấp TikTok Session ID trong thanh cài đặt bên trái!")
        
    url = "https://api16-normal-v6.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 7.1.2; en_US; SM-G988N; Build/NRD90M;tt-ok/3.12.13.1)",
        "Cookie": f"sessionid={session_id}"
    }
    params = {
        "req_text": text,
        "speaker_map_type": 0,
        "aid": 1180,
        "text_speaker": voice_id
    }
    
    response = requests.post(url, headers=headers, params=params, timeout=10)
    if response.status_code != 200:
        raise Exception(f"HTTP Error {response.status_code}")
        
    data = response.json()
    if data.get("message") == "success":
        v_str = data["data"]["v_str"]
        if output_file.endswith(".wav"):
            temp_mp3 = output_file.replace(".wav", ".mp3")
            with open(temp_mp3, "wb") as f:
                f.write(base64.b64decode(v_str))
            from pydub import AudioSegment
            AudioSegment.from_file(temp_mp3).export(output_file, format="wav")
        else:
            with open(output_file, "wb") as f:
                f.write(base64.b64decode(v_str))
    else:
        err = data.get("message", str(data))
        if "login" in err.lower() or "session" in err.lower():
            raise Exception("TikTok Session ID không hợp lệ hoặc đã hết hạn. Vui lòng lấy lại mã mới!")
        raise Exception(f"TikTok API Error: {err}")

def _generate_audio_edge(text, voice_id, output_file):
    import subprocess
    temp_mp3 = output_file.replace(".wav", ".mp3")
    result = subprocess.run(["edge-tts", "-v", voice_id, "-t", text, "--write-media", temp_mp3], capture_output=True, text=True)
    if result.returncode != 0:
        err_msg = result.stderr
        if "NoAudioReceived" in err_msg:
            raise Exception("Edge TTS từ chối đọc vì văn bản chứa ký tự lạ hoặc trống.")
        raise Exception(f"Edge TTS Error: {err_msg[:200]}...")
    AudioSegment.from_file(temp_mp3).export(output_file, format="wav")
    os.remove(temp_mp3)

def _generate_audio_gtts(text, lang, output_file):
    from gtts import gTTS
    tts = gTTS(text=text, lang=lang)
    temp_mp3 = output_file.replace(".wav", ".mp3")
    tts.save(temp_mp3)
    AudioSegment.from_file(temp_mp3).export(output_file, format="wav")
    os.remove(temp_mp3)

def _generate_audio(text, voice, output_file, speed_rate=1.0, tiktok_session_id=""):
    if voice.startswith("tiktok:"):
        voice_id = voice.replace("tiktok:", "")
        try:
            _generate_audio_tiktok(text, voice_id, output_file, tiktok_session_id)
        except Exception as e:
            print(f"[Fallback] TikTok API lỗi ({e}). Đang chuyển sang Edge-TTS...")
            fallback_voice = "en-US-JennyNeural" if "en" in voice_id.lower() else "vi-VN-HoaiMyNeural"
            _generate_audio_edge(text, fallback_voice, output_file)
    elif voice.startswith("edge:"):
        voice_id = voice.replace("edge:", "")
        _generate_audio_edge(text, voice_id, output_file)
    elif voice.startswith("gtts:"):
        lang = voice.replace("gtts:", "")
        _generate_audio_gtts(text, lang, output_file)
    else:
        raise Exception("Chỉ hỗ trợ giọng đọc TikTok/CapCut/EdgeTTS/gTTS!")
        
    # Áp dụng tua nhanh bằng FFmpeg atempo nếu có yêu cầu
    if speed_rate != 1.0 and os.path.exists(output_file):
        import subprocess
        base_ext = ".wav" if output_file.endswith(".wav") else ".mp3"
        temp_speed_file = output_file.replace(base_ext, f"_speed{base_ext}")
        res = subprocess.run(["ffmpeg", "-y", "-i", output_file, "-filter:a", f"atempo={speed_rate}", temp_speed_file], capture_output=True)
        if res.returncode == 0 and os.path.exists(temp_speed_file):
            os.remove(output_file)
            os.rename(temp_speed_file, output_file)

import re

def clean_tts_text(text: str) -> str:
    """Làm sạch chuỗi, loại bỏ ký tự không in được và emoji có thể làm sập TikTok API"""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Bỏ chú thích trong ngoặc
    text = re.sub(r'\[.*?\]|\(.*?\)|\*.*?\*', '', text)
    # Loại bỏ hoàn toàn chữ Hán (Trung/Nhật/Hàn) do AI dịch sót
    text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', text)
    # Bỏ Emoji và ký tự lạ, giữ lại chữ, số, và dấu câu cơ bản
    text = re.sub(r'[^\w\s.,?!;:\'\"\-]', '', text)
    # TikTok API giới hạn độ dài
    if len(text) > 290:
        text = text[:290]
    return text.strip()

def generate_tts_for_srt(srt_path, voice="tiktok:BV074_streaming", output_dir="temp", overwrite=True, tiktok_session_id="", max_workers=2, tts_speed=1.2, max_tts_speed=1.35):
    """
    Tạo file audio tổng hợp (lồng tiếng) khớp với thời gian trong SRT.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    output_audio_path = os.path.join(output_dir, f"{base_name}_dubbed.wav")
    
    if not overwrite and os.path.exists(output_audio_path):
        print(f"Cache hit: {output_audio_path}")
        return output_audio_path
        
    print(f"Generating TTS for {srt_path} using voice {voice} with {max_workers} threads...")
    original_subtitles = parse_srt(srt_path)
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    
    import copy
    audio_subtitles = copy.deepcopy(original_subtitles)
    
    # --- AUTO-MERGE THÔNG MINH (CHỈ ÁP DỤNG CHO AUDIO) ---
    # Tự động gộp các dòng phụ đề quá ngắn có nguy cơ bị đè giọng
    merge_count = 0
    i = 0
    while i < len(audio_subtitles) - 1:
        sub = audio_subtitles[i]
        next_sub = audio_subtitles[i+1]
        
        try:
            start_ms = parse_time_to_ms(sub['timestamp'].split(' --> ')[0].strip())
            end_ms = parse_time_to_ms(sub['timestamp'].split(' --> ')[1].strip())
            next_start_ms = parse_time_to_ms(next_sub['timestamp'].split(' --> ')[0].strip())
            next_end_ms = parse_time_to_ms(next_sub['timestamp'].split(' --> ')[1].strip())
            
            available_ms = next_start_ms - start_ms
            gap_ms = next_start_ms - end_ms
            
            words = len(clean_tts_text(sub['text']).split())
            min_req_ms = words * 260 # Tốc độ đọc rất nhanh (khoảng ~4 từ/giây)
            
            # GIỚI HẠN: Chống hiệu ứng "Hòn tuyết lăn" (Snowball effect)
            # Nếu cụm gộp đã quá dài (> 25 từ), dừng gộp ngay lập tức để tránh tràn API TTS dẫn đến mất tiếng
            if words > 25:
                i += 1
                continue
            
            # Nếu thời gian đọc tổi thiểu vượt quá cả thời gian cho phép sau khi tua kịch kim
            # VÀ khoảng lặng giữa 2 câu < 800ms (để không gộp 2 cảnh phim cách xa nhau)
            if min_req_ms > available_ms * max_tts_speed and gap_ms < 800:
                print(f"[Auto-Merge] Phát hiện dòng {sub['index']} quá ngắn! Gộp AUDIO với dòng {next_sub['index']}...")
                sub['text'] = sub['text'].strip() + " " + next_sub['text'].strip()
                sub['timestamp'] = f"{sub['timestamp'].split(' --> ')[0].strip()} --> {next_sub['timestamp'].split(' --> ')[1].strip()}"
                audio_subtitles.pop(i + 1)
                merge_count += 1
                # KHÔNG tăng i để tiếp tục kiểm tra dòng vừa gộp xem có cần gộp tiếp không
            else:
                i += 1
        except Exception:
            i += 1
            
    if merge_count > 0:
        print(f"Đã gộp thành công {merge_count} dòng phụ đề cho âm thanh (Giữ nguyên hiển thị gốc)!")
        # Đánh lại số thứ tự (index) cho chuẩn
        for idx, sub in enumerate(audio_subtitles):
            sub['index'] = idx + 1
    # ----------------------------
    
    temp_files = []
    failed_segments = []
    
    # Bước 1: Chuẩn bị danh sách tác vụ
    tasks = []
    for i, sub in enumerate(audio_subtitles):
        text = clean_tts_text(sub['text'])
        
        if not text:
            continue
            
        temp_audio_file = os.path.join(output_dir, f"{base_name}_chunk_{i}.mp3")
        
        # Yêu cầu AI đọc ở tốc độ chuẩn (1.0x) để giữ nguyên độ tự nhiên
        speed_rate = 1.0
        
        # Cache từng câu: Nếu file đã tồn tại và đủ lớn thì bỏ qua
        if not overwrite and os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 200:
            pass # Đã có sẵn
        else:
            try:
                start_ms = parse_time_to_ms(sub['timestamp'].split(' --> ')[0].strip())
            except:
                start_ms = 0
                
            tasks.append({
                'index': i,
                'text': text,
                'path': temp_audio_file,
                'speed_rate': speed_rate,
                'start_ms': start_ms
            })
            
    # Tạo TTS song song bằng ThreadPoolExecutor
    total_tasks = len(tasks)
    if total_tasks > 0:
        import concurrent.futures
        import threading
        
        completed_tasks = 0
        lock = threading.Lock()
        
        def process_task(task_info):
            nonlocal completed_tasks
            try:
                _generate_audio(task_info['text'], voice, task_info['path'], tiktok_session_id=tiktok_session_id)
            except Exception as e:
                with lock:
                    failed_segments.append(task_info)
            finally:
                with lock:
                    completed_tasks += 1
                    print(f"\rTTS đang tổng hợp: {completed_tasks}/{total_tasks} dòng (Đa luồng)...", end="", flush=True)
                    
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(process_task, tasks)
        print() # Newline sau khi progress bar kết thúc
            
    # Bước 2: Xử lý lại các file bị lỗi (Retry Pass)
    if failed_segments:
        print(f"\n[Retry Pass] Có {len(failed_segments)} câu bị lỗi. Đang tiến hành thử lại...")
        import time
        for seg in failed_segments:
            i = seg['index']
            text = seg['text']
            temp_audio_file = seg['path']
            
            print(f"  -> Thử lại đoạn {i}: {text[:30]}...")
            time.sleep(2) # Nghỉ một chút để tránh spam API
            try:
                _generate_audio(text, voice, temp_audio_file, tiktok_session_id=tiktok_session_id) # Retry có thể dùng speed_rate mặc định hoặc truyền vào thêm. Tạm thời pass mặc định.
                print(f"  -> Thành công đoạn {i}!")
            except Exception as e:
                print(f"  -> Vẫn thất bại đoạn {i} ({str(e)}). Sẽ bỏ trống đoạn này.")

    # Bước 3: Ghép nối chính xác theo thời gian gốc (Sync khắt khe)
    print("Assembling final audio using strict time sync...")
    # Lấy tổng độ dài video từ sub cuối để làm khung nền
    if audio_subtitles:
        last_time_str = audio_subtitles[-1]['timestamp'].split(' --> ')[1]
        total_duration_ms = parse_time_to_ms(last_time_str) + 2000
    else:
        total_duration_ms = 0
        
    final_audio = AudioSegment.silent(duration=total_duration_ms)
    
    current_time_ms = 0
    for i, sub in enumerate(audio_subtitles):
        text = clean_tts_text(sub['text'])
        if not text:
            continue
            
        try:
            start_time_str, end_time_str = sub['timestamp'].split(' --> ')
            start_ms = parse_time_to_ms(start_time_str.strip())
            end_ms = parse_time_to_ms(end_time_str.strip())
        except Exception:
            continue
        target_duration = end_ms - start_ms
        
        # Tìm giới hạn không gian tối đa (đến khi câu tiếp theo CÓ TEXT bắt đầu) để tránh đè giọng
        next_start_ms = total_duration_ms
        for j in range(i + 1, len(audio_subtitles)):
            if clean_tts_text(audio_subtitles[j]['text']):
                try:
                    next_start_str = audio_subtitles[j]['timestamp'].split(' --> ')[0]
                    next_start_ms = parse_time_to_ms(next_start_str.strip())
                    break
                except:
                    pass
        
        max_allowed_duration = next_start_ms - start_ms
        if max_allowed_duration <= 0: max_allowed_duration = target_duration
        
        # Ý TƯỞNG ĐỘT PHÁ: Tận dụng khoảng lặng (gap) giữa các câu để AI đọc thong thả hơn.
        # Chúng ta cho phép giọng AI trườn ra khỏi sub gốc, chiếm dụng khoảng lặng, nhưng chừa lại 100ms nghỉ.
        usable_duration = max_allowed_duration - 100
        if usable_duration < target_duration:
            usable_duration = target_duration # Đảm bảo tối thiểu bằng đúng sub gốc
        
        temp_audio_file = os.path.join(output_dir, f"{base_name}_chunk_{i}.mp3")
        
        if os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 200:
            segment = AudioSegment.from_file(temp_audio_file)
            segment_duration = len(segment)
            temp_files.append(temp_audio_file)
            
            # --- TUA NHANH ĐỘNG (DYNAMIC SPEEDUP) ---
            # Nếu AI đọc dài hơn khoảng trống TỐI ĐA cho phép (đã tính cả khoảng lặng)
            if segment_duration > usable_duration + 50:
                required_speed = segment_duration / usable_duration
                
                # An toàn cho chất lượng giọng nói: chỉ cho phép speedup đến mức max_tts_speed
                max_safe_speed = max(tts_speed, max_tts_speed)
                actual_speed = min(required_speed, max_safe_speed)
                
                if actual_speed > 1.05:
                    import subprocess
                    speed_file = temp_audio_file.replace(".mp3", "_speed.mp3")
                    res = subprocess.run(["ffmpeg", "-y", "-i", temp_audio_file, "-filter:a", f"atempo={actual_speed:.2f}", speed_file], capture_output=True)
                    if res.returncode == 0 and os.path.exists(speed_file):
                        segment = AudioSegment.from_file(speed_file)
                        segment_duration = len(segment)
                        temp_files.append(speed_file)
                        print(f"  -> [Đồng bộ] Đoạn {i+1} mượn khoảng lặng nhưng vẫn quá dài, tự tua nhanh {actual_speed:.2f}x (Giới hạn: {max_safe_speed}x)")
                    else:
                        print(f"  -> [Lỗi] Không thể tua nhanh đoạn {i+1} bằng FFmpeg!")
                else:
                    print(f"  -> [Hoàn hảo] Đoạn {i+1} mượn khoảng lặng vừa đủ, giữ nguyên tốc độ tự nhiên.")
            else:
                if segment_duration > target_duration + 50:
                    print(f"  -> [Tuyệt vời] Đoạn {i+1} dài hơn sub gốc nhưng đã mượn được khoảng lặng để khỏi bị tua nhanh!")
                else:
                    print(f"  -> [Vừa vặn] Đoạn {i+1} ngắn gọn lọt thỏm trong sub gốc, giữ nguyên tốc độ.")
            
            # Cho phép âm thanh dài hơn thời lượng gốc trườn qua câu tiếp theo một cách tự nhiên
            # thay vì cắt cụt đuôi làm mất chữ.
            
            # Ghép cứng vào đúng vị trí gốc của SRT (KHÔNG thay đổi thời gian sub để đảm bảo khớp hình)
            final_audio = final_audio.overlay(segment, position=start_ms)
    # Lưu file audio lồng tiếng hoàn chỉnh
    output_audio_path = os.path.join(output_dir, f"{base_name}_dubbed.wav")
    print(f"Exporting final audio to {output_audio_path}...")
    final_audio.export(output_audio_path, format="wav")
    
    # Ghi đè lại file SRT để lọc bỏ ký tự tiếng Trung (giữ nguyên timestamp gốc)
    print("Cleaning up Chinese chars from perfectly synced SRT file...")
    with open(srt_path, "w", encoding="utf-8-sig") as f:
        for sub in original_subtitles:
            # Lọc vét chữ Hán lần cuối phòng trường hợp SRT cũ chưa được lọc ở bước 1
            final_text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', sub['text']).strip()
            f.write(f"{sub['index']}\n")
            f.write(f"{sub['timestamp']}\n")
            f.write(f"{final_text}\n\n")
    
    # Xóa các file temp
    print("Cleaning up temp files...")
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
            
    print("TTS generation complete.")
    return output_audio_path

def generate_demo_voice(voice, speed_rate=1.0, output_dir="temp", tiktok_session_id=""):
    """
    Sinh ra file âm thanh demo "Xin chào, đây là giọng đọc thử."
    Sử dụng cơ chế cache để không gọi API lại nếu file đã tồn tại.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Tạo tên file cache dựa trên các thông số
    safe_voice = voice.replace(":", "_").replace("-", "_")
    demo_file = os.path.join(output_dir, f"demo_{safe_voice}_{speed_rate:.1f}.wav")
    
    if os.path.exists(demo_file):
        return demo_file
        
    text = f"Xin chào, đây là giọng đọc thử ở tốc độ {speed_rate}." if speed_rate != 1.0 else "Xin chào, đây là giọng đọc thử."
    
    try:
        _generate_audio(text, voice, demo_file, speed_rate=speed_rate, tiktok_session_id=tiktok_session_id)
        return demo_file
    except Exception as e:
        print(f"Demo TTS Error: {e}")
        return None
