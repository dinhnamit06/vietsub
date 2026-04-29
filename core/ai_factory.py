import os
import random
import time
import subprocess
from core.translator import _translate_batch_gemini

def spin_script(original_text, gemini_api_key, prompt_style="Hấp dẫn, kịch tính, chốt sale"):
    """
    Sử dụng Gemini để viết lại (spin) kịch bản bán hàng.
    """
    if not gemini_api_key:
        raise ValueError("Vui lòng cung cấp Gemini API Key để xào kịch bản.")
        
    import re
    from google import genai
    client = genai.Client(api_key=gemini_api_key)
    
    prompt = f"""Bạn là một copywriter chuyên nghiệp trên TikTok/Shorts.
Nhiệm vụ: Viết lại kịch bản dưới đây thành một phiên bản hoàn toàn mới nhưng giữ nguyên thông điệp cốt lõi.
Phong cách yêu cầu: {prompt_style}

QUAN TRỌNG:
1. Độ dài của kịch bản mới phải TƯƠNG ĐƯƠNG với kịch bản cũ (không được dài hơn quá 10%).
2. Không dùng những từ ngữ bị cấm trên TikTok.
3. Trả về trực tiếp nội dung kịch bản, không giải thích, không in lời chào.

Kịch bản gốc:
{original_text}
"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                wait_time = 15
                match = re.search(r'retry in ([\d\.]+)s', err_str)
                if match:
                    wait_time = float(match.group(1)) + 1
                if attempt < max_retries - 1:
                    print(f"Gemini API quá tải (429). Tự động chờ {wait_time:.1f} giây...")
                    time.sleep(wait_time)
                    continue
            raise Exception(f"Lỗi khi xào kịch bản: {err_str}")
    return original_text

def analyze_image_for_video(image_path, gemini_api_key, source_type="youtube"):
    """
    Dùng Gemini phân tích ảnh, trả về (từ khoá tìm kiếm, kịch bản bán hàng mẫu).
    """
    if not gemini_api_key:
        raise ValueError("Vui lòng cung cấp Gemini API Key để phân tích ảnh.")
        
    import re
    from google import genai
    import PIL.Image
    client = genai.Client(api_key=gemini_api_key)
    
    img = PIL.Image.open(image_path)
    
    kw_instruction = "Tạo ra 1 cụm từ khoá (tiếng Anh hoặc tiếng Việt) ngắn gọn, chuẩn xác nhất để tìm kiếm các video review/sử dụng sản phẩm này hoặc tương tự trên mạng (nhớ thêm từ khoá 'shorts' hoặc 'review' để dễ tìm video dọc)."
    example = "đồ chơi flycam mini shorts review | Wow anh em ơi, hôm nay review cho anh em con flycam mini siêu đỉnh này! Bay cực đầm, chống va đập tốt mà giá lại cực kỳ hạt dẻ. Bấm ngay vào giỏ hàng để chốt đơn nhé!"
        
    prompt = f"""Hãy phân tích hình ảnh sản phẩm này và thực hiện 2 nhiệm vụ sau.
Trả về kết quả ĐÚNG định dạng có 2 dòng tách biệt bởi dấu "|":

Nhiệm vụ 1: {kw_instruction}
Nhiệm vụ 2: Viết một đoạn kịch bản lồng tiếng bán hàng ngắn (khoảng 3-4 câu, 15-20 giây) bằng TIẾNG VIỆT siêu hấp dẫn, giật tít để quảng cáo sản phẩm này trên TikTok.

Ví dụ định dạng trả về:
{example}
"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt, img]
            )
            text = response.text.strip()
            parts = text.split('|', 1)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
            else:
                return "viral product review shorts", text
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                wait_time = 15
                match = re.search(r'retry in ([\d\.]+)s', err_str)
                if match:
                    wait_time = float(match.group(1)) + 1
                if attempt < max_retries - 1:
                    print(f"Gemini API quá tải (429). Tự động chờ {wait_time:.1f} giây...")
                    time.sleep(wait_time)
                    continue
            raise Exception(f"Lỗi khi phân tích ảnh: {err_str}")
    return "viral product review shorts", "Sản phẩm cực chất, mua ngay thôi các bạn ơi!"

def prepare_clips(video_dir, temp_dir, clip_duration=3, target_w=1080, target_h=1920):
    """
    Cắt tất cả video trong video_dir thành các clip ngắn và chuẩn hoá độ phân giải.
    """
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
        
    valid_exts = ['.mp4', '.mkv', '.avi', '.mov']
    raw_videos = [os.path.join(video_dir, f) for f in os.listdir(video_dir) if os.path.splitext(f)[1].lower() in valid_exts]
    
    if not raw_videos:
        raise ValueError(f"Không tìm thấy video nào trong thư mục {video_dir}")
        
    all_clips = []
    
    for idx, video in enumerate(raw_videos):
        # Lấy thông tin thời lượng
        cmd_probe = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video
        ]
        try:
            duration = float(subprocess.check_output(cmd_probe).decode('utf-8').strip())
        except:
            continue
            
        # Chia video thành các clip nhỏ
        num_clips = int(duration // clip_duration)
        if num_clips == 0:
            num_clips = 1
            
        for i in range(num_clips):
            start_time = i * clip_duration
            out_clip = os.path.join(temp_dir, f"clip_{idx}_{i}.mp4")
            
            # Cắt và chuẩn hoá (Scale & Crop to 9:16)
            cmd_cut = [
                "ffmpeg", "-y", "-ss", str(start_time), "-t", str(clip_duration),
                "-i", video,
                "-vf", f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,crop={target_w}:{target_h},setsar=1,fps=30",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-an", # Loại bỏ âm thanh gốc
                out_clip
            ]
            try:
                subprocess.run(cmd_cut, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                all_clips.append(out_clip)
            except Exception as e:
                print(f"Lỗi khi tạo clip từ {video}: {e}")
                continue
                
    return all_clips

def random_mashup_videos(clips, output_path, target_duration=15):
    """
    Trộn ngẫu nhiên các clip cho đến khi đạt target_duration.
    """
    import random
    import ffmpeg
    if not clips:
        return
        
    random.shuffle(clips)
    selected_clips = []
    current_duration = 0
    
    for clip in clips:
        selected_clips.append(clip)
        current_duration += 3 # Ước tính mỗi clip 3s
        if current_duration >= target_duration:
            break
            
    # Tạo file danh sách cho ffmpeg concat
    list_file = output_path + ".txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for clip in selected_clips:
            # ffmpeg concat demuxer requires relative or absolute path formatted properly
            safe_path = clip.replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")
            
    # Concat
    try:
        (
            ffmpeg
            .input(list_file, format='concat', safe=0)
            .output(output_path, c='copy')
            .run(overwrite_output=True, quiet=True)
        )
    except ffmpeg.Error as e:
        print(f"Lỗi khi mix video: {e.stderr.decode()}")
        
    # Xoá list file
    if os.path.exists(list_file):
        os.remove(list_file)

def apply_random_anti_reup(input_path, output_path):
    """
    Áp dụng các bộ lọc ngẫu nhiên để lách bản quyền:
    - Phóng to nhẹ ngẫu nhiên (1.02 đến 1.05)
    - Đổi tốc độ ngẫu nhiên (1.02 đến 1.05)
    - Tăng sáng/tương phản ngẫu nhiên
    - Lật ngang ngẫu nhiên
    - Đổi tone giọng (Pitch)
    - Fake siêu dữ liệu (Metadata) giả lập quay bằng điện thoại iPhone/Samsung
    """
    import random
    import ffmpeg
    import datetime
    import subprocess
    import os
    
    do_hflip = random.choice([True, False])
    speed_factor = round(random.uniform(1.02, 1.05), 2)
    zoom_factor = round(random.uniform(1.02, 1.05), 2)
    contrast = round(random.uniform(1.01, 1.05), 2)
    brightness = round(random.uniform(0.01, 0.04), 2)
    
    in_file = ffmpeg.input(input_path)
    
    # --- Xử lý Hình ảnh ---
    video = in_file.video
    if do_hflip: video = video.hflip()
    
    # Bắt buộc crop về tỷ lệ dọc 9:16 (trường hợp tải dính video ngang)
    # Lấy phần chính giữa khung hình: width = height * 9/16
    video = video.filter('crop', 'ih*(9/16)', 'ih')
    
    # Phóng to (Zoom) từ khung 9:16 đó
    video = video.filter('crop', f'iw/{zoom_factor}', f'ih/{zoom_factor}')
    video = video.filter('scale', '1080', '1920')
    video = video.filter('eq', contrast=contrast, brightness=brightness)
    video = video.filter('setpts', f'{1/speed_factor}*PTS')
    video = video.filter('noise', alls=1, allf='t')
    
    # --- Xử lý Âm thanh ---
    audio = in_file.audio
    audio = audio.filter('asetrate', int(44100 * speed_factor)).filter('aresample', 44100)
    
    # --- Fake Metadata Máy Ảnh ---
    devices = [
        {"make": "Apple", "model": "iPhone 13 Pro Max"},
        {"make": "Apple", "model": "iPhone 14 Pro"},
        {"make": "Apple", "model": "iPhone 15 Pro Max"},
        {"make": "Samsung", "model": "SM-S918B"}, # S23 Ultra
        {"make": "Samsung", "model": "SM-S928B"}  # S24 Ultra
    ]
    device = random.choice(devices)
    days_ago = random.randint(0, 15)
    fake_time = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago)
    creation_time_str = fake_time.strftime('%Y-%m-%dT%H:%M:%S.000000Z')
    
    out = ffmpeg.output(video, audio, output_path, map_metadata="-1", vcodec="libx264", acodec="aac", preset="veryfast")
    args = ffmpeg.get_args(out)
    
    # Lắp ghép lệnh ffmpeg thủ công để hỗ trợ ghi đè nhiều thông số metadata
    cmd = ['ffmpeg', '-y'] + args
    meta_args = [
        '-metadata', f'creation_time={creation_time_str}',
        '-metadata', f'make={device["make"]}',
        '-metadata', f'model={device["model"]}'
    ]
    # Chèn meta_args vào trước output_path (phần tử cuối cùng)
    cmd = cmd[:-1] + meta_args + [cmd[-1]]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"Lỗi khi apply anti-reup (subprocess): {e}")
        
    return output_path
