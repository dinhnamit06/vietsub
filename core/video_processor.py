import ffmpeg
import os
import sys
import subprocess

def extract_audio(video_path, output_dir="temp", overwrite=True):
    """Trích xuất âm thanh từ video gốc"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{base_name}.wav")
    
    if not overwrite and os.path.exists(audio_path):
        print(f"Cache hit: {audio_path}")
        return audio_path
        
    print(f"Extracting audio from {video_path}...")
    try:
        ffmpeg.input(video_path).output(audio_path, acodec='pcm_s16le', ac=1, ar='16k').run(overwrite_output=True, quiet=True)
        return audio_path
    except ffmpeg.Error as e:
        print("FFmpeg error:", e.stderr.decode('utf-8') if e.stderr else str(e))
        raise e



def extract_preview_frame(video_path, output_dir="temp"):
    """Trích xuất 1 khung hình ở giữa video để làm ảnh Preview cài đặt Blur"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    frame_path = os.path.join(output_dir, f"{base_name}_preview.jpg")
    
    # Nếu có sẵn thì dùng luôn cho lẹ
    if os.path.exists(frame_path):
        return frame_path
        
    print("Extracting preview frame...")
    try:
        # Lấy 1 frame ở giây thứ 2 (hoặc giữa video)
        ffmpeg.input(video_path, ss=2).output(frame_path, vframes=1).run(overwrite_output=True, quiet=True)
        return frame_path
    except ffmpeg.Error as e:
        print("FFmpeg extract frame error:", e.stderr.decode('utf-8') if e.stderr else str(e))
        return None

def srt_to_ass(srt_path, ass_path, video_width, video_height, font_size, font_color, outline_color, outline_width, margin_v, speed=1.0):
    # Đọc nội dung SRT
    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        srt_content = f.read().strip()
        
    import re
    blocks = re.split(r'\n\s*\n', srt_content)
    
    # Map màu từ HEX #RRGGBB sang định dạng ASS &H00BBGGRR
    def hex_to_ass_color(hex_color):
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H00{b}{g}{r}"
        return "&H0000FFFF" # Vàng mặc định
        
    def time_to_seconds(t_str):
        parts = t_str.replace(',', '.').split(':')
        h, m = float(parts[0]), float(parts[1])
        s = float(parts[2])
        return h * 3600 + m * 60 + s
        
    def seconds_to_ass_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"
        
    color_map = {
        "Trắng": "#FFFFFF", "Vàng": "#FFFF00", "Xanh Lơ": "#00FFFF", 
        "Xanh Lá": "#00FF00", "Đỏ": "#FF0000", "Hồng": "#FF00FF", "Đen": "#000000"
    }
    
    ass_font_color = hex_to_ass_color(color_map.get(font_color, "#FFFF00"))
    ass_outline_color = hex_to_ass_color(color_map.get(outline_color, "#000000"))
    
    # Tạo Header ASS
    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{ass_font_color},&H000000FF,{ass_outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,{outline_width},0,2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) >= 3:
            time_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if time_match:
                start_sec = time_to_seconds(time_match.group(1)) / speed
                end_sec = time_to_seconds(time_match.group(2)) / speed
                
                start_ass = seconds_to_ass_time(start_sec)
                end_ass = seconds_to_ass_time(end_sec)
                
                text = "\\N".join(lines[2:])
                ass_content += f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{text}\n"

    with open(ass_path, 'w', encoding='utf-8-sig') as f:
        f.write(ass_content)

def process_video(video_path, dubbed_audio_path, srt_path, output_path, bg_volume=0.1, overwrite=True, blur_box=None, sub_margin_v=20, font_size=45, font_color="Vàng", outline_color="Đen", outline_width=2, adv_config=None, base_audio_path=None):
    """
    Ghép video gốc, âm thanh lồng tiếng, và phụ đề.
    bg_volume: Âm lượng của video gốc (0.0 đến 1.0).
    """
    if adv_config is None: adv_config = {}
    
    speed = adv_config.get("speed", 1.0)
    flip = adv_config.get("flip", False)
    zoom_cfg = adv_config.get("zoom", {})
    logo_cfg = adv_config.get("logo", {})
    bgm_cfg = adv_config.get("bgm", {})
    enable_sub = adv_config.get("enable_sub", True)
    color_eq = adv_config.get("color_eq", {})
    overlay_cfg = adv_config.get("overlay", {})
    
    if not overwrite and os.path.exists(output_path):
        print(f"Cache hit: {output_path}")
        return output_path
        
    print(f"Mixing video, audio and subtitles into {output_path}...")
    
    try:
        # Chuẩn bị input
        video_input = ffmpeg.input(video_path)
        audio_input = ffmpeg.input(dubbed_audio_path)
        
        # Audio Processing
        if base_audio_path and os.path.exists(base_audio_path):
            bg_audio = ffmpeg.input(base_audio_path).audio.filter('volume', bg_volume)
        else:
            bg_audio = video_input.audio.filter('volume', bg_volume)
        dub_audio = audio_input.audio
        
        audio_inputs = [bg_audio, dub_audio]
        
        # Thêm BGM nếu có
        if bgm_cfg and bgm_cfg.get("path") and os.path.exists(bgm_cfg["path"]):
            bgm_audio = ffmpeg.input(bgm_cfg["path"]).audio.filter('volume', bgm_cfg.get("vol", 0.1))
            audio_inputs.append(bgm_audio)
            
        mixed_audio = ffmpeg.filter(audio_inputs, 'amix', inputs=len(audio_inputs), duration='longest')
        # Tăng volume tổng thể (vì amix làm giảm volume)
        mixed_audio = mixed_audio.filter('volume', float(len(audio_inputs)))
        
        if speed != 1.0:
            mixed_audio = mixed_audio.filter('atempo', speed)
        
        # Lấy thông tin video
        probe = ffmpeg.probe(video_path)
        video_stream_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        video_w = int(video_stream_info['width'])
        video_h = int(video_stream_info['height'])
        
        fps_str = video_stream_info.get('r_frame_rate', '25/1')
        fps_parts = fps_str.split('/')
        video_fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 25
        
        # Convert SRT to ASS
        ass_path = os.path.join("temp", "render_subtitles.ass")
        srt_to_ass(srt_path, ass_path, video_w, video_h, font_size, font_color, outline_color, outline_width, sub_margin_v, speed=speed)
        ass_filter_path = ass_path.replace('\\', '/')    
        
        video_stream = video_input.video
        
        # 1. Color EQ (Sáng, Tương phản, Bão hoà)
        if color_eq:
            b = color_eq.get('brightness', 0.0)
            c = color_eq.get('contrast', 1.0)
            s = color_eq.get('saturation', 1.0)
            if b != 0.0 or c != 1.0 or s != 1.0:
                video_stream = video_stream.filter('eq', brightness=b, contrast=c, saturation=s)
                
        # 2. Blur
        if blur_box:
            if 'x_pct' in blur_box:
                x = int(blur_box.get('x_pct', 0) * video_w)
                y = int(blur_box.get('y_pct', 0) * video_h)
                w = int(blur_box.get('w_pct', 1.0) * video_w)
                h = int(blur_box.get('h_pct', 0.5) * video_h)
            else:
                x, y = blur_box.get('x', 0), blur_box.get('y', 0)
                w, h = blur_box.get('w', 100), blur_box.get('h', 50)
            split = video_stream.split()
            v_main = split[0]
            v_blur = split[1]
            blurred_box = v_blur.crop(x, y, w, h).filter('boxblur', luma_radius=20, luma_power=2, chroma_radius=20, chroma_power=2)
            video_stream = ffmpeg.overlay(v_main, blurred_box, x=x, y=y)
            
        # 3. Zoom (Crop tĩnh & Auto Dynamic)
        zoom_pct = zoom_cfg.get("percent", 0)
        if zoom_pct > 0:
            if zoom_cfg.get("mode") == "Động (Auto Zoom)":
                static_t = zoom_cfg.get("static_time", 2.0)
                dyn_t = zoom_cfg.get("dyn_time", 1.0)
                cycle = static_t + dyn_t
                
                # zoompan evaluate per frame, giữ nguyên resolution và framerate
                z_expr = f"if(lt(mod(in_time,{cycle}),{static_t}),1.0,{1 + zoom_pct/100.0})"
                video_stream = video_stream.filter('zoompan', z=z_expr, x='iw/2-(iw/zoom/2)', y='ih/2-(ih/zoom/2)', d=1, s=f"{video_w}x{video_h}", fps=video_fps)
            else:
                crop_w = video_w * (1 - zoom_pct/100.0)
                crop_h = video_h * (1 - zoom_pct/100.0)
                crop_x = (video_w - crop_w) / 2
                crop_y = (video_h - crop_h) / 2
                video_stream = video_stream.crop(crop_x, crop_y, crop_w, crop_h).filter('scale', w=video_w, h=video_h)
            
        # 4. Flip
        if flip:
            video_stream = video_stream.filter('hflip')
            
        # 5. Speed (Video)
        if speed != 1.0:
            video_stream = video_stream.filter('setpts', f"{1.0/speed}*PTS")
            
        # 6. Lớp phủ (Overlay mờ chống MD5)
        if overlay_cfg and overlay_cfg.get("path") and os.path.exists(overlay_cfg["path"]):
            op = overlay_cfg.get("opacity", 0.1)
            overlay_img = ffmpeg.input(overlay_cfg["path"]).filter('format', 'rgba').filter('colorchannelmixer', aa=op).filter('scale', video_w, video_h)
            video_stream = ffmpeg.overlay(video_stream, overlay_img, x=0, y=0)
            
        # 7. Logo Overlay (Motion & Scale)
        if logo_cfg and logo_cfg.get("path") and os.path.exists(logo_cfg["path"]):
            logo_scale = logo_cfg.get("scale", 0.2)
            lw = int(video_w * logo_scale)
            # scale h=-1 có thể gây lỗi với số lẻ, nên dùng biểu thức tính tỷ lệ. Hoặc để FFmpeg tự chọn
            logo_img = ffmpeg.input(logo_cfg["path"]).filter('format', 'rgba')
            
            opacity = logo_cfg.get("opacity", 1.0)
            if opacity < 1.0:
                logo_img = logo_img.filter('colorchannelmixer', aa=opacity)
                
            logo_img = logo_img.filter('scale', w=lw, h=-1)
            
            pos = logo_cfg.get("pos", "Góc trên Trái")
            move = logo_cfg.get("move", "Đứng yên")
            padding = 20
            
            if move == "Trôi nổi (Lissajous)":
                overlay_x = f"(main_w-overlay_w)/2 + ((main_w-overlay_w)/2 - {padding}) * sin(t*0.5)"
                overlay_y = f"(main_h-overlay_h)/2 + ((main_h-overlay_h)/2 - {padding}) * cos(t*0.7)"
            elif move == "Nảy (DVD Bounce)":
                overlay_x = f"abs(mod(t*150, 2*(main_w-overlay_w)) - (main_w-overlay_w))"
                overlay_y = f"abs(mod(t*200, 2*(main_h-overlay_h)) - (main_h-overlay_h))"
            else:
                if pos == "Góc trên Trái": overlay_x, overlay_y = padding, padding
                elif pos == "Góc trên Phải": overlay_x, overlay_y = f"main_w-overlay_w-{padding}", padding
                elif pos == "Góc dưới Trái": overlay_x, overlay_y = padding, f"main_h-overlay_h-{padding}"
                elif pos == "Góc dưới Phải": overlay_x, overlay_y = f"main_w-overlay_w-{padding}", f"main_h-overlay_h-{padding}"
                else: overlay_x, overlay_y = "(main_w-overlay_w)/2", "(main_h-overlay_h)/2"
            
            video_stream = ffmpeg.overlay(video_stream, logo_img, x=overlay_x, y=overlay_y)
            
        # 8. Subtitles (ASS)
        if enable_sub:
            video_stream = video_stream.filter('subtitles', ass_filter_path)
        
        # Ghép và xuất file (Dùng preset ultrafast)
        out = ffmpeg.output(video_stream, mixed_audio, output_path, vcodec='libx264', preset='ultrafast', acodec='aac', audio_bitrate='192k')
        ffmpeg.run(out, overwrite_output=True, quiet=True)
        
        print(f"Finished processing! Output saved to {output_path}")
        return output_path
    except ffmpeg.Error as e:
        print("FFmpeg error:", e.stderr.decode('utf-8') if e.stderr else str(e))
        raise e
