import os
import sys

def _setup_cuda_path():
    """Tự động thêm đường dẫn chứa cublas64_12.dll và cudnn vào PATH trên Windows"""
    if os.name != 'nt':
        return
    try:
        import site
        # Quét tất cả các thư mục site-packages
        paths = site.getsitepackages()
        if hasattr(site, 'getusersitepackages'):
            paths.append(site.getusersitepackages())
            
        for sp in paths:
            cublas_bin = os.path.join(sp, "nvidia", "cublas", "bin")
            cudnn_bin = os.path.join(sp, "nvidia", "cudnn", "bin")
            nvrtc_bin = os.path.join(sp, "nvidia", "cuda_nvrtc", "bin")
            
            for bin_path in [cublas_bin, cudnn_bin, nvrtc_bin]:
                if os.path.exists(bin_path):
                    os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(bin_path)
    except Exception:
        pass

_setup_cuda_path()

# Bắt buộc import thư viện sau khi đã thiết lập xong PATH
from faster_whisper import WhisperModel
def format_timestamp(seconds):
    """Định dạng thời gian sang chuẩn SRT: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

_cached_whisper_model = None
_cached_device = None

def transcribe_audio(audio_path, model_size="base", output_dir="temp", overwrite=True, device_type="cpu"):
    """
    Nhận diện giọng nói từ file audio/video và tạo file .srt.
    """
    global _cached_whisper_model, _cached_device
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    
    if not overwrite and os.path.exists(srt_path):
        print(f"Cache hit: {srt_path}")
        return srt_path, "unknown"
        
    if _cached_whisper_model is None or _cached_device != device_type:
        print(f"Loading Whisper model '{model_size}' on {device_type.upper()}...")
        try:
            compute_type = "float16" if device_type == "cuda" else "int8"
            _cached_whisper_model = WhisperModel(model_size, device=device_type, compute_type=compute_type)
            _cached_device = device_type
        except Exception as e:
            print(f"Failed to load on {device_type}, falling back to CPU... Error: {e}")
            _cached_whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
            _cached_device = "cpu"
            
    model = _cached_whisper_model
    
    print(f"Transcribing {audio_path}...")
    
    class DummySegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text
            
    from pydub import AudioSegment
    import math
    audio = AudioSegment.from_file(audio_path)
    chunk_length_ms = 5 * 60 * 1000 # 5 minutes
    
    segments_all = []
    language_detected = "unknown"
    
    if len(audio) <= chunk_length_ms:
        segments, info = model.transcribe(
            audio_path, 
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            word_timestamps=True
        )
        language_detected = info.language
        for seg in segments:
            actual_end = seg.end
            if hasattr(seg, 'words') and seg.words:
                # Cắt bỏ khoảng lặng thừa bằng cách lấy timestamp của từ cuối cùng
                actual_end = seg.words[-1].end
                
            segments_all.append(DummySegment(seg.start, actual_end, seg.text))
    else:
        print("Audio is long. Splitting into chunks to prevent MemoryError...")
        for i in range(math.ceil(len(audio) / chunk_length_ms)):
            chunk = audio[i * chunk_length_ms : (i+1) * chunk_length_ms]
            chunk_path = audio_path.replace(".wav", f"_part{i}.wav")
            chunk.export(chunk_path, format="wav")
            
            print(f"  -> Transcribing chunk {i+1}...")
            chunk_segments, info = model.transcribe(
                chunk_path, 
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                word_timestamps=True
            )
            if i == 0:
                language_detected = info.language
                
            offset_seconds = (i * chunk_length_ms) / 1000.0
            for seg in chunk_segments:
                actual_end = seg.end
                if hasattr(seg, 'words') and seg.words:
                    actual_end = seg.words[-1].end
                    
                segments_all.append(DummySegment(
                    start=seg.start + offset_seconds,
                    end=actual_end + offset_seconds,
                    text=seg.text
                ))
            
            if os.path.exists(chunk_path):
                os.remove(chunk_path)
    
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    
    # Bộ lọc chống ảo giác (Whisper Hallucination)
    filtered_segments = []
    prev_text = ""
    repeat_count = 0
    
    for seg in segments_all:
        text = seg.text.strip()
        if not text: continue
        
        if text == prev_text:
            repeat_count += 1
            if repeat_count >= 2: # Nếu 1 câu y hệt lặp lại tới lần thứ 3 -> Bỏ qua
                continue
        else:
            repeat_count = 0
            prev_text = text
            
        filtered_segments.append(seg)

    # Write SRT
    print(f"Writing SRT file... (Filtered {len(segments_all) - len(filtered_segments)} hallucinated segments)")
    with open(srt_path, "w", encoding="utf-8-sig") as f:
        for i, segment in enumerate(filtered_segments, start=1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{segment.text.strip()}\n\n")
            
    print(f"Transcription complete. Language detected: {info.language}")
    return srt_path, info.language
