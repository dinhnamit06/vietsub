import os
from pydub import AudioSegment
from .translator import parse_srt

VOICE_MAP = {
    "Nữ CapCut (VN)": "tiktok:BV074_streaming",
    "Nam CapCut (VN)": "tiktok:BV075_streaming",
    "Nữ CapCut (US)": "tiktok:en_us_001",
    "Nam CapCut (US)": "tiktok:en_us_006"
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
    
    response = requests.post(url, headers=headers, params=params)
    if response.status_code != 200:
        raise Exception(f"HTTP Error {response.status_code}")
        
    data = response.json()
    if data.get("message") == "success":
        v_str = data["data"]["v_str"]
        with open(output_file, "wb") as f:
            f.write(base64.b64decode(v_str))
    else:
        err = data.get("message", str(data))
        if "login" in err.lower() or "session" in err.lower():
            raise Exception("TikTok Session ID không hợp lệ hoặc đã hết hạn. Vui lòng lấy lại mã mới!")
        raise Exception(f"TikTok API Error: {err}")

def _generate_audio(text, voice, output_file, speed_rate=1.0, tiktok_session_id=""):
    if voice.startswith("tiktok:"):
        voice_id = voice.replace("tiktok:", "")
        _generate_audio_tiktok(text, voice_id, output_file, tiktok_session_id)
        return
    raise Exception("Chỉ hỗ trợ giọng đọc TikTok/CapCut!")

import re

def clean_tts_text(text: str) -> str:
    """Làm sạch chuỗi, loại bỏ ký tự không in được có thể làm sập edge-tts"""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = "".join(ch for ch in text if ch.isprintable())
    return text

def generate_tts_for_srt(srt_path, voice="tiktok:BV074_streaming", output_dir="temp", overwrite=True, tiktok_session_id="", max_workers=2):
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
    subtitles = parse_srt(srt_path)
    base_name = os.path.splitext(os.path.basename(srt_path))[0]
    
    temp_files = []
    failed_segments = []
    
    # Bước 1: Chuẩn bị danh sách tác vụ
    tasks = []
    for i, sub in enumerate(subtitles):
        text = clean_tts_text(sub['text'])
        start_time_str, end_time_str = sub['timestamp'].split(' --> ')
        start_ms = parse_time_to_ms(start_time_str)
        end_ms = parse_time_to_ms(end_time_str)
        target_duration = end_ms - start_ms
        
        if not text:
            continue
            
        temp_audio_file = os.path.join(output_dir, f"{base_name}_chunk_{i}.mp3")
        
        # Yêu cầu AI đọc nhanh hơn (Native Speedup) ngay từ gốc nếu đoạn chữ quá dài
        word_count = len(text.split())
        estimated_duration_ms = (word_count / 3.5) * 1000
        speed_rate = 1.0
        
        if estimated_duration_ms > target_duration:
            speed_rate = estimated_duration_ms / target_duration
            speed_rate = min(speed_rate, 1.5) # Giới hạn ép tốc API
        
        # Cache từng câu: Nếu file đã tồn tại và đủ lớn thì bỏ qua
        if not overwrite and os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 1000:
            pass # Đã có sẵn
        else:
            tasks.append({
                'index': i,
                'text': text,
                'path': temp_audio_file,
                'speed_rate': speed_rate,
                'start_ms': start_ms
            })

    # Bước 2: Thực thi song song (Multithreading)
    if tasks:
        import concurrent.futures
        import threading
        
        completed_tasks = 0
        total_tasks = len(tasks)
        lock = threading.Lock()
        
        def process_task(task):
            nonlocal completed_tasks
            try:
                _generate_audio(task['text'], voice, task['path'], speed_rate=task['speed_rate'], tiktok_session_id=tiktok_session_id)
            except Exception as e:
                with lock:
                    failed_segments.append(task)
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
                print(f"  -> Vẫn thất bại đoạn {i} sau Retry Pass. Sẽ bỏ trống đoạn này.")

    # Bước 3: Ghép nối chính xác theo thời gian gốc (Sync khắt khe)
    print("Assembling final audio using strict time sync...")
    # Lấy tổng độ dài video từ sub cuối để làm khung nền
    if subtitles:
        last_time_str = subtitles[-1]['timestamp'].split(' --> ')[1]
        total_duration_ms = parse_time_to_ms(last_time_str) + 2000
    else:
        total_duration_ms = 0
        
    final_audio = AudioSegment.silent(duration=total_duration_ms)
    
    for i, sub in enumerate(subtitles):
        text = clean_tts_text(sub['text'])
        if not text:
            continue
            
        start_time_str, end_time_str = sub['timestamp'].split(' --> ')
        start_ms = parse_time_to_ms(start_time_str)
        end_ms = parse_time_to_ms(end_time_str)
        target_duration = end_ms - start_ms
        
        temp_audio_file = os.path.join(output_dir, f"{base_name}_chunk_{i}.mp3")
        
        if os.path.exists(temp_audio_file) and os.path.getsize(temp_audio_file) > 1000:
            segment = AudioSegment.from_file(temp_audio_file)
            temp_files.append(temp_audio_file)
            
            # Nếu audio dài hơn khung thời gian gốc, ÉP tăng tốc độ để khớp hoàn toàn
            if len(segment) > target_duration:
                ratio = len(segment) / target_duration
                if ratio > 1.05:
                    try:
                        # Thử thuật toán atempo của FFmpeg thay vì pydub speedup
                        # Atempo nén thời gian siêu mượt mà không vứt khung hình
                        fast_audio_file = temp_audio_file.replace(".mp3", "_fast.mp3")
                        atempo_filter = f"atempo={ratio:.2f}"
                        if ratio > 2.0:
                            # FFmpeg atempo max là 2.0. Nếu > 2.0 cần mix 2 bộ lọc
                            atempo_filter = f"atempo=2.0,atempo={(ratio/2.0):.2f}"
                            
                        import ffmpeg
                        ffmpeg.input(temp_audio_file).output(fast_audio_file, filter_complex=atempo_filter).run(overwrite_output=True, quiet=True)
                        segment = AudioSegment.from_file(fast_audio_file)
                        temp_files.append(fast_audio_file)
                        print(f"    [Strict Sync] Dùng FFmpeg atempo ép tốc độ mượt mà đoạn {i} lên {ratio:.2f}x để khít {target_duration}ms")
                    except Exception:
                        # Fallback: Tăng tốc bằng cách đổi Sample Rate (Giọng Chipmunk)
                        new_sample_rate = int(segment.frame_rate * ratio)
                        segment = segment._spawn(segment.raw_data, overrides={'frame_rate': new_sample_rate})
                        segment = segment.set_frame_rate(44100) # Chuẩn hoá lại để ghép
                        print(f"    [Strict Sync] Ép tăng tốc đoạn {i} lên {ratio:.2f}x (Bằng Chipmunk Effect)")
            
            # Ghép cứng vào vị trí start_ms gốc
            final_audio = final_audio.overlay(segment, position=start_ms)
    # Lưu file audio lồng tiếng hoàn chỉnh
    output_audio_path = os.path.join(output_dir, f"{base_name}_dubbed.wav")
    print(f"Exporting final audio to {output_audio_path}...")
    final_audio.export(output_audio_path, format="wav")
    
    # Xóa các file temp
    print("Cleaning up temp files...")
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
            
    print("TTS generation complete.")
    return output_audio_path

def generate_demo_voice(voice, output_dir="temp", tiktok_session_id=""):
    """
    Sinh ra file âm thanh demo "Xin chào, đây là giọng đọc thử."
    Sử dụng cơ chế cache để không gọi API lại nếu file đã tồn tại.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Tạo tên file cache dựa trên các thông số
    safe_voice = voice.replace(":", "_").replace("-", "_")
    demo_file = os.path.join(output_dir, f"demo_{safe_voice}.mp3")
    
    if os.path.exists(demo_file):
        return demo_file
        
    text = "Xin chào, đây là giọng đọc thử."
    
    try:
        if voice.startswith("tiktok:"):
            real_voice = voice.replace("tiktok:", "")
            _generate_audio_tiktok(text, real_voice, demo_file, tiktok_session_id)
        else:
            raise Exception("Chỉ hỗ trợ giọng đọc TikTok/CapCut!")
            
        return demo_file
    except Exception as e:
        print(f"Demo TTS Error: {e}")
        return None
