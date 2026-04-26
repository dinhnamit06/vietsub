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
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    
    # Write SRT
    print("Writing SRT file...")
    with open(srt_path, "w", encoding="utf-8-sig") as f:
        for i, segment in enumerate(segments, start=1):
            start_time = format_timestamp(segment.start)
            end_time = format_timestamp(segment.end)
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{segment.text.strip()}\n\n")
            
    print(f"Transcription complete. Language detected: {info.language}")
    return srt_path, info.language
