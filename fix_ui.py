import os

filepath = r'c:\Users\Admin\Desktop\CÁC TOOL TÂM ĐẮC\toolvietsub\ui_workers.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i in range(len(lines)):
    if 'elif "Gemini" in trans_model: trans_mod = "gemini"' in lines[i]:
        new_lines.extend(lines[:i+1])
        break

new_code = '''                elif "Qwen" in trans_model: trans_mod = "groq_qwen"
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
                        tts_speed=float(self.config.get("tts_speed", 1.2))
                    )
                else:
                    self.log.emit(f"[VIDEO {idx+1}] Bỏ qua tạo TTS do tùy chọn đã tắt.")
                    
                # --- BƯỚC 3: RENDER ---
                self.video_status.emit(video_path, "Đang xử lý", "Ghép Video cuối...")
                if self.out_dir:
                    if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)
                    base_name = os.path.splitext(os.path.basename(video_path))[0] + "_dubbed.mp4"
                    output_video = os.path.join(self.out_dir, base_name)
                else:
                    output_video = os.path.splitext(video_path)[0] + "_dubbed.mp4"
                    
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
            new_subs_data = []
            for sub in translated_subs:
                try:
                    timestamp = sub['timestamp']
                    start_str, end_str = timestamp.split("-->")
                    start_str = start_str.strip()
                    end_str = end_str.strip()
                    
                    def parse_time(ts):
                        h, m, s_ms = ts.split(':')
                        s, ms = s_ms.replace('.', ',').split(',')
                        return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000.0
                        
                    new_subs_data.append({
                        "start": parse_time(start_str),
                        "end": parse_time(end_str),
                        "text": sub['text']
                    })
                except:
                    pass
                
            self.progress.emit(100, "Hoàn thành!")
            self.log.emit("Đã dịch xong SRT thủ công.")
            self.work_done.emit(True, out_srt, new_subs_data)
        except Exception as e:
            self.log.emit(f"Lỗi dịch SRT: {str(e)}")
            self.work_done.emit(False, str(e), [])
'''

new_lines.append(new_code)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
