import os
from PyQt6.QtCore import QThread, pyqtSignal
from core.video_processor import extract_audio, process_video
from core.stt_engine import transcribe_audio
from core.translator import translate_srt, parse_srt
from core.tts_engine import generate_tts_for_srt

class WorkerStep1(QThread):
    progress = pyqtSignal(int, str) # Phần trăm, Text thông báo
    log = pyqtSignal(str) # Log Terminal
    work_done = pyqtSignal(bool, str, object, str) # Thành công, Video Path, Danh sách Sub (Dict), BGM Path
    
    def __init__(self, input_type, input_val, config, overwrite=True):
        super().__init__()
        self.input_type = input_type # "url" hoặc "file"
        self.input_val = input_val
        self.config = config
        self.overwrite = overwrite
        
    def run(self):
        try:
            self.log.emit("--- BẮT ĐẦU BƯỚC 1 ---")
            
            self.progress.emit(10, "Đang nạp file video...")
            video_path = self.input_val
                
            self.log.emit(f"Video sẵn sàng: {video_path}")
            
            self.progress.emit(25, "Đang tách âm thanh...")
            audio_path = extract_audio(video_path, output_dir="temp", overwrite=self.overwrite)
            self.log.emit(f"Đã tách âm thanh: {audio_path}")
            
            stt_audio_path = audio_path
            bgm_path = ""
            
            self.progress.emit(40, "Đang nhận diện giọng nói (STT)...")
            self.log.emit("Đang gửi audio lên server để STT...")
            device_type = self.config.get("device_type", "cpu")
            raw_srt, lang = transcribe_audio(stt_audio_path, output_dir="temp", overwrite=self.overwrite, device_type=device_type)
            self.log.emit(f"Đã tạo phụ đề gốc: {raw_srt} (Ngôn ngữ: {lang})")
            
            self.progress.emit(65, "Đang dịch phụ đề...")
            self.log.emit("Đang dùng AI để dịch thuật...")
            trans_model = self.config.get("translation_model", "Gemini 2.0 Flash")
            translated_srt = raw_srt.replace(".srt", "_translated.srt")
            
            if "Flash-Lite" in trans_model: trans_mod = "gemini_lite"
            elif "Gemini" in trans_model: trans_mod = "gemini"
            elif "Qwen" in trans_model: trans_mod = "groq_qwen"
            elif "Groq" in trans_model: trans_mod = "groq"
            elif "Google" in trans_model: trans_mod = "google_free"
            else: trans_mod = "gemini"
                
            gemini_key = self.config.get("gemini_api_key", "")
            groq_key = self.config.get("groq_api_key", "")
            gemini_backup = self.config.get("gemini_api_key_backup", "")
            prompt = self.config.get("gemini_prompt", "")
            target_lang = self.config.get("target_lang", "Tiếng Việt")
            
            translated_srt = translate_srt(
                raw_srt, 
                target_lang=target_lang, 
                output_dir="temp", 
                overwrite=self.overwrite, 
                translation_model=trans_mod, 
                gemini_api_key=gemini_key, 
                gemini_prompt=prompt, 
                groq_api_key=groq_key,
                gemini_api_key_backup=gemini_backup,
                tts_speed=float(self.config.get("tts_speed", 1.2))
            )
                
            self.log.emit("Dịch thuật hoàn tất!")
            
            self.progress.emit(90, "Đang trích xuất dữ liệu bảng...")
            subs_data = parse_srt(translated_srt)
            
            self.progress.emit(100, "Hoàn tất Bước 1!")
            self.log.emit("--- BƯỚC 1 XONG ---")
            self.work_done.emit(True, video_path, subs_data, bgm_path)
            
        except Exception as e:
            self.log.emit(f"[LỖI BƯỚC 1] {str(e)}")
            self.work_done.emit(False, "", [], "")

class WorkerStep3(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    work_done = pyqtSignal(bool, str) # Thành công, Output Video Path
    
    def __init__(self, srt_path, video_path, config, sub_margin_v, use_blur, blur_box, overwrite=True, out_dir="", font_size=45, font_color="Vàng", outline_color="Đen", outline_width=2, adv_config=None, base_audio_path=""):
        super().__init__()
        self.srt_path = srt_path
        self.video_path = video_path
        self.config = config
        self.sub_margin_v = sub_margin_v
        self.use_blur = use_blur
        self.blur_box = blur_box
        self.overwrite = overwrite
        self.out_dir = out_dir
        self.font_size = font_size
        self.font_color = font_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.adv_config = adv_config or {}
        self.base_audio_path = base_audio_path
        
    def run(self):
        try:
            self.log.emit("--- BẮT ĐẦU BƯỚC 3 ---")
            
            enable_tts = self.config.get("enable_tts", True)
            
            dubbed_audio = None
            if enable_tts:
                self.progress.emit(10, "Đang tạo âm thanh lồng tiếng (TTS)...")
                from core.tts_engine import VOICE_MAP
                voice_display = self.config.get("voice", "Nữ Hoài My (Edge)")
                voice = VOICE_MAP.get(voice_display, "vi-VN-HoaiMyNeural")
                gcp_key = self.config.get("gcp_api_key", "")
                tiktok_key = self.config.get("tiktok_session_id", "")
                
                self.log.emit(f"Dùng giọng: {voice}")
                
                tts_threads = int(self.config.get("tts_threads", 2))
                
                dubbed_audio = generate_tts_for_srt(
                    self.srt_path, 
                    voice=voice, 
                    output_dir="temp", 
                    overwrite=self.overwrite, 
                    tiktok_session_id=tiktok_key,
                    max_workers=tts_threads,
                    tts_speed=float(self.config.get("tts_speed", 1.2)),
                    max_tts_speed=float(self.config.get("max_tts_speed", 1.35))
                )
            else:
                self.log.emit("Đã bỏ qua tiến trình tạo TTS (Do tùy chọn 'Bật Lồng tiếng' đang tắt).")
            
            self.progress.emit(60, "Đang mix âm thanh và ghép phụ đề...")
            self.log.emit("Chạy FFmpeg mix audio + video + sub...")
            
            bg_vol = self.config.get("bg_volume", 0.1)
            
            if self.out_dir:
                if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)
                base_name = os.path.basename(self.video_path).replace(".mp4", "_dubbed.mp4")
                output_video = os.path.join(self.out_dir, base_name)
            else:
                output_video = self.video_path.replace(".mp4", "_dubbed.mp4")
            
            final_video = process_video(
                self.video_path, 
                dubbed_audio, 
                self.srt_path, 
                output_path=output_video, 
                bg_volume=bg_vol, 
                sub_margin_v=self.sub_margin_v, 
                blur_box=self.blur_box if self.use_blur else None,
                font_size=self.font_size,
                font_color=self.font_color,
                outline_color=self.outline_color,
                outline_width=self.outline_width,
                adv_config=self.adv_config,
                base_audio_path=self.base_audio_path if self.base_audio_path else None
            )
            
            self.progress.emit(100, "Hoàn tất Render!")
            self.log.emit(f"--- RENDER THÀNH CÔNG: {final_video} ---")
            self.work_done.emit(True, final_video)
            
        except Exception as e:
            self.log.emit(f"[LỖI BƯỚC 3] {str(e)}")
            self.work_done.emit(False, "")

import time
import shutil

class WorkerBatch(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    video_status = pyqtSignal(str, str, str) # filepath, status, note
    batch_done = pyqtSignal(bool)
    
    def __init__(self, video_paths, config, sub_margin_v, use_blur, blur_box, out_dir="", font_size=45, font_color="Vàng", outline_color="Đen", outline_width=2, adv_config=None):
        super().__init__()
        self.video_paths = video_paths
        self.config = config
        self.sub_margin_v = sub_margin_v
        self.use_blur = use_blur
        self.blur_box = blur_box
        self.out_dir = out_dir
        self.font_size = font_size
        self.font_color = font_color
        self.outline_color = outline_color
        self.outline_width = outline_width
        self.adv_config = adv_config
        

    def cleanup_temp_files(self, video_path):
        try:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_dir = "temp"
            if not os.path.exists(temp_dir): return
            
            # Xoá các file wav, srt có chứa base_name
            for f in os.listdir(temp_dir):
                if base_name in f and (f.endswith(".wav") or f.endswith(".srt")):
                    os.remove(os.path.join(temp_dir, f))
            
            # Xoá thư mục TTS nếu có
            tts_dir = os.path.join(temp_dir, f"{base_name}_tts")
            if os.path.exists(tts_dir):
                shutil.rmtree(tts_dir, ignore_errors=True)
                
            # Xoá thư mục demucs nếu có
            demucs_dir = os.path.join(temp_dir, "htdemucs", base_name)
            if os.path.exists(demucs_dir):
                shutil.rmtree(demucs_dir, ignore_errors=True)
                
            self.log.emit(f"[DỌN DẸP] Đã xoá file tạm của: {base_name}")
        except Exception as e:
            self.log.emit(f"[LỖI DỌN DẸP] {str(e)}")

    def run(self):
        self.log.emit(f"--- BẮT ĐẦU XỬ LÝ {len(self.video_paths)} VIDEO ---")
        
        for idx, video_path in enumerate(self.video_paths):
            try:
                self.video_status.emit(video_path, "Đang xử lý", "Trích xuất âm thanh...")
                self.log.emit(f"\n[VIDEO {idx+1}/{len(self.video_paths)}] Đang xử lý: {os.path.basename(video_path)}")
                
                # --- BƯỚC 1: Xử lý AI ---
                audio_path = extract_audio(video_path, output_dir="temp", overwrite=True)
                
                stt_audio_path = audio_path
                bgm_path = ""
                
                self.video_status.emit(video_path, "Đang xử lý", "Nhận diện giọng nói (STT)...")
                raw_srt, lang = transcribe_audio(stt_audio_path, output_dir="temp", overwrite=True, device_type=self.config.get("device_type", "cpu"))
                
                self.video_status.emit(video_path, "Đang xử lý", "Dịch thuật (AI)...")
                trans_model = self.config.get("translation_model", "Gemini 2.0 Flash")
                if "Flash-Lite" in trans_model: trans_mod = "gemini_lite"
                elif "Gemini" in trans_model: trans_mod = "gemini"
                elif "Qwen" in trans_model: trans_mod = "groq_qwen"
                elif "Groq" in trans_model: trans_mod = "groq"
                elif "Google" in trans_model: trans_mod = "google_free"
                else: trans_mod = "gemini"
                
                translated_srt = translate_srt(
                    raw_srt, 
                    target_lang=self.config.get("target_lang", "Tiếng Việt"), 
                    output_dir="temp", 
                    overwrite=True, 
                    translation_model=trans_mod, 
                    gemini_api_key=self.config.get("gemini_api_key", ""), 
                    gemini_prompt=self.config.get("gemini_prompt", ""), 
                    groq_api_key=self.config.get("groq_api_key", ""),
                    gemini_api_key_backup=self.config.get("gemini_api_key_backup", ""),
                    tts_speed=float(self.config.get("tts_speed", 1.2))
                )
                
                # --- BƯỚC 2: TẠO TTS ---
                enable_tts = self.config.get("enable_tts", True)
                dubbed_audio = None
                
                if enable_tts:
                    self.video_status.emit(video_path, "Đang xử lý", "Tạo Giọng đọc (TTS)...")
                    from core.tts_engine import VOICE_MAP
                    voice_display = self.config.get("voice", "vi-VN-HoaiMyNeural")
                    voice_id = VOICE_MAP.get(voice_display, "vi-VN-HoaiMyNeural")
                    
                    dubbed_audio = generate_tts_for_srt(
                        translated_srt, 
                        voice=voice_id, 
                        output_dir="temp", 
                        overwrite=True, 
                        tiktok_session_id=self.config.get("tiktok_session_id", ""),
                        max_workers=int(self.config.get("tts_threads", 2)),
                        tts_speed=float(self.config.get("tts_speed", 1.2)),
                        max_tts_speed=float(self.config.get("max_tts_speed", 1.35))
                    )
                else:
                    self.log.emit(f"[VIDEO {idx+1}] Bỏ qua tạo TTS do tùy chọn đã tắt.")
                
                # --- BƯỚC 3: RENDER ---
                self.video_status.emit(video_path, "Đang xử lý", "Ghép Video cuối...")
                if self.out_dir:
                    if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)
                    base_name = os.path.basename(video_path).replace(".mp4", "_dubbed.mp4")
                    output_video = os.path.join(self.out_dir, base_name)
                else:
                    output_video = video_path.replace(".mp4", "_dubbed.mp4")
                    
                final_video = process_video(
                    video_path, 
                    dubbed_audio, 
                    translated_srt, 
                    output_path=output_video, 
                    bg_volume=self.config.get("bg_volume", 0.1), 
                    sub_margin_v=self.sub_margin_v, 
                    blur_box=self.blur_box if self.use_blur else None,
                    font_size=self.font_size,
                    font_color=self.font_color,
                    outline_color=self.outline_color,
                    outline_width=self.outline_width,
                    adv_config=self.adv_config,
                    base_audio_path=bgm_path if bgm_path else None
                )
                
                self.video_status.emit(video_path, "Thành công", f"Xong: {os.path.basename(final_video)}")
                self.log.emit(f"[THÀNH CÔNG] Video {idx+1}: {final_video}")
                
                # Xoá rác khi thành công
                self.cleanup_temp_files(video_path)
                
            except Exception as e:
                self.video_status.emit(video_path, "Lỗi", str(e))
                self.log.emit(f"[LỖI BỎ QUA] Video {idx+1} thất bại: {str(e)}")
                # Giữ lại file srt và wav nếu có lỗi để sửa lỗi (không cleanup)
                
            # Nghỉ ngơi giữa các video để tránh Rate Limit API
            if idx < len(self.video_paths) - 1:
                self.log.emit("Đang nghỉ 10 giây để làm mát và tránh chặn API...")
                time.sleep(10)
                
        self.progress.emit(100, "Hoàn thành toàn bộ!")
        self.log.emit("--- ĐÃ XỬ LÝ XONG BATCH ---")
        self.batch_done.emit(True)

class WorkerTranslateSRT(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    work_done = pyqtSignal(bool, str, list)

    def __init__(self, srt_content, config):
        super().__init__()
        self.srt_content = srt_content
        self.config = config

    def run(self):
        try:
            self.log.emit("--- BẮT ĐẦU DỊCH SRT THỦ CÔNG ---")
            self.progress.emit(10, "Đang khởi tạo model dịch...")
            
            import os
            temp_dir = "temp"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
                
            in_srt = os.path.join(temp_dir, "manual_input.srt")
            with open(in_srt, "w", encoding="utf-8") as f:
                f.write(self.srt_content)
                
            trans_model = self.config.get("translation_model", "Gemini 2.0 Flash")
            if "Flash-Lite" in trans_model: trans_mod = "gemini_lite"
            elif "Gemini" in trans_model: trans_mod = "gemini"
            elif "Qwen" in trans_model: trans_mod = "groq_qwen"
            elif "Groq" in trans_model: trans_mod = "groq"
            elif "Google" in trans_model: trans_mod = "google_free"
            else: trans_mod = "gemini"
            
            self.progress.emit(30, f"Đang dịch bằng {trans_model}...")
            
            from core.translator import translate_srt
            out_srt = translate_srt(
                in_srt,
                target_lang=self.config.get("target_lang", "Tiếng Việt"),
                output_dir="temp",
                overwrite=True,
                translation_model=trans_mod,
                gemini_api_key=self.config.get("gemini_api_key", ""),
                gemini_prompt=self.config.get("gemini_prompt", ""),
                groq_api_key=self.config.get("groq_api_key", ""),
                gemini_api_key_backup=self.config.get("gemini_api_key_backup", "")
            )
            
            self.progress.emit(90, "Đang nạp kết quả...")
            from core.translator import parse_srt
            translated_subs = parse_srt(out_srt)
            new_subs_data = translated_subs
            
            self.progress.emit(100, "Hoàn thành!")
            self.log.emit("Đã dịch xong SRT thủ công.")
            self.work_done.emit(True, out_srt, new_subs_data)
        except Exception as e:
            self.log.emit(f"Lỗi dịch SRT: {str(e)}")
            self.work_done.emit(False, str(e), [])

import yt_dlp

class WorkerDownloadVideo(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    work_done = pyqtSignal(bool, str)

    def __init__(self, url, out_dir, cookie_string=""):
        super().__init__()
        self.url = url
        self.out_dir = out_dir
        self.cookie_string = cookie_string

    def run(self):
        try:
            import re
            
            # Trích xuất URL nếu chuỗi đầu vào chứa text rác (ví dụ copy từ Douyin/TikTok)
            url_match = re.search(r'(https?://[^\s]+)', self.url)
            if url_match:
                clean_url = url_match.group(1)
            else:
                clean_url = self.url

            self.log.emit(f"--- BẮT ĐẦU TẢI VIDEO TỪ: {clean_url} ---")
            self.progress.emit(10, "Đang phân tích liên kết...")
            
            if not os.path.exists(self.out_dir):
                os.makedirs(self.out_dir)

            ydl_opts = {
                'outtmpl': os.path.join(self.out_dir, '%(title)s.%(ext)s'),
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }

            if self.cookie_string.strip():
                if "# Netscape HTTP Cookie File" in self.cookie_string:
                    try:
                        with open("cookies.txt", "w", encoding="utf-8") as f:
                            f.write(self.cookie_string)
                        self.log.emit("Đã lưu Cookie định dạng Netscape vào file cục bộ.")
                    except Exception as e:
                        self.log.emit(f"Lỗi khi lưu cookies.txt: {e}")
                else:
                    ydl_opts['http_headers'] = {'Cookie': self.cookie_string.strip()}
                    self.log.emit("Đang sử dụng Cookie trực tiếp qua HTTP Header.")

            class Logger:
                def __init__(self, log_sig, prog_sig):
                    self.log_sig = log_sig
                    self.prog_sig = prog_sig
                    self.suppress_errors = False
                def debug(self, msg): pass
                def warning(self, msg): pass
                def error(self, msg): 
                    if not self.suppress_errors:
                        self.log_sig.emit(f"[LỖI yt-dlp] {msg}")

            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        p = d['_percent_str']
                        p = float(p.replace('%', '').strip())
                        self.progress.emit(int(10 + p * 0.8), f"Đang tải... {d.get('_percent_str', '')} (Tốc độ: {d.get('_speed_str', '')})")
                    except:
                        pass
                elif d['status'] == 'finished':
                    self.progress.emit(95, "Tải xong, đang gộp file (nếu có)...")
                    self.log.emit(f"Đã tải xong file gốc, đang xử lý: {d.get('filename', '')}")

            logger_instance = Logger(self.log, self.progress)
            ydl_opts['logger'] = logger_instance
            ydl_opts['progress_hooks'] = [progress_hook]

            self.log.emit("Đang tiến hành tải xuống...")
            
            def try_download(browser=None):
                opts = ydl_opts.copy()
                if browser:
                    opts['cookiesfrombrowser'] = (browser,)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(clean_url, download=True)
                    fpath = ydl.prepare_filename(info)
                    if not os.path.exists(fpath):
                        fpath = os.path.splitext(fpath)[0] + ".mp4"
                    return fpath
                    
            try:
                # Mặc định tắt báo lỗi đỏ để thử lần 1
                logger_instance.suppress_errors = True
                
                # Ưu tiên dùng cookies.txt nếu có
                if os.path.exists("cookies.txt"):
                    self.log.emit("Tìm thấy file cookies.txt! Đang sử dụng...")
                    ydl_opts['cookiefile'] = "cookies.txt"
                    
                file_path = try_download(None)
                logger_instance.suppress_errors = False
            except Exception as e:
                err_msg = str(e).lower()
                if "cookies" in err_msg or "douyin" in err_msg or "tiktok" in err_msg or "login" in err_msg:
                    self.log.emit("Nền tảng yêu cầu Cookies hoặc Token! Đang tự động thử các cách lấy Cookie...")
                    try:
                        self.log.emit("[1/3] Đang thử tự động lấy từ Firefox (Khuyên dùng)...")
                        file_path = try_download("firefox")
                        logger_instance.suppress_errors = False
                    except Exception:
                        try:
                            self.log.emit("[2/3] Không tìm thấy Firefox, đang lấy từ Google Chrome...")
                            file_path = try_download("chrome")
                            logger_instance.suppress_errors = False
                        except Exception:
                            try:
                                self.log.emit("[3/3] Chrome bị chặn bảo mật (DPAPI), đang thử Microsoft Edge...")
                                file_path = try_download("edge")
                                logger_instance.suppress_errors = False
                            except Exception as e3:
                                logger_instance.suppress_errors = False
                                err3 = str(e3).lower()
                                if "dpapi" in err3:
                                    self.log.emit("❌ TẤT CẢ TRÌNH DUYỆT ĐỀU CHẶN LẤY COOKIE (LỖI DPAPI BẢO MẬT MỚI).")
                                    self.log.emit("👉 CÁCH KHẮC PHỤC 1: Cài đặt và dùng Firefox (nó không bị lỗi này).")
                                    self.log.emit("👉 CÁCH KHẮC PHỤC 2: Tải extension 'Get cookies.txt LOCALLY' trên Chrome, xuất file cookies ra và đổi tên thành 'cookies.txt', sau đó copy vào thư mục chứa tool này rồi bấm tải lại.")
                                else:
                                    self.log.emit(f"[LỖI yt-dlp] {str(e3)}")
                                raise e3
                else:
                    logger_instance.suppress_errors = False
                    self.log.emit(f"[LỖI yt-dlp] {str(e)}")
                    raise e
                    
            self.progress.emit(100, "Tải xuống hoàn tất!")
            self.log.emit(f"--- TẢI THÀNH CÔNG: {file_path} ---")
            self.work_done.emit(True, file_path)

        except Exception as e:
            self.log.emit(f"[LỖI TẢI VIDEO] {str(e)}")
            self.work_done.emit(False, "")

                new_script = spin_script(
                    self.original_script, 
                    gemini_key, 
                    prompt_style=self.config.get("gemini_prompt", "Hấp dẫn, kịch tính, chốt sale")
                )
                
                self.progress.emit(100, "Xào kịch bản hoàn tất!")
                self.log.emit("--- KỊCH BẢN MỚI ---")
                self.log.emit(new_script)
                self.log.emit("-------------------")
                self.work_done.emit(True, new_script)

        except Exception as e:
            self.log.emit(f"[LỖI XƯỞNG AI] {str(e)}")
            self.work_done.emit(False, None)

class WorkerExtractScript(QThread):
    progress = pyqtSignal(int, str)
    log = pyqtSignal(str)
    work_done = pyqtSignal(bool, str)

    def __init__(self, video_path, config):
        super().__init__()
        self.video_path = video_path
        self.config = config

    def run(self):
        try:
            self.log.emit(f"Bắt đầu trích xuất kịch bản từ: {os.path.basename(self.video_path)}")
            self.progress.emit(10, "Đang tách âm thanh...")
            from core.video_processor import extract_audio
            import os
            
            audio_path = extract_audio(self.video_path, output_dir="temp", overwrite=True)
            
            self.progress.emit(40, "Đang dùng AI nghe và chép lại kịch bản (STT)...")
            from core.video_processor import transcribe_audio
            raw_srt, lang = transcribe_audio(audio_path, output_dir="temp", overwrite=True, device_type=self.config.get("device_type", "cpu"))
            
            self.progress.emit(80, "Đang ghép nối văn bản...")
            from core.translator import parse_srt
            subs = parse_srt(raw_srt)
            full_text = " ".join([sub['text'] for sub in subs])
            
            self.progress.emit(100, "Bóc tách kịch bản hoàn tất!")
            self.log.emit("Đã bóc tách thành công!")
            self.work_done.emit(True, full_text)
        except Exception as e:
            self.log.emit(f"[LỖI TRÍCH XUẤT KỊCH BẢN] {str(e)}")
            self.work_done.emit(False, str(e))
