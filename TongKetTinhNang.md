# 🚀 TỔNG QUAN KIẾN TRÚC & TÍNH NĂNG AUTO VIETSUB PRO

Phần mềm **Auto Vietsub Pro - Desktop Edition** là một giải pháp tự động hóa toàn diện (End-to-End Pipeline) dành cho việc lồng tiếng, dịch thuật và lách bản quyền video ngắn (Reup). Hệ thống được xây dựng trên ngôn ngữ Python với giao diện PyQt6 hiện đại.

Dưới đây là chi tiết kỹ thuật chuyên sâu về các Module đang hoạt động trong hệ thống.

---

## 1. KIẾN TRÚC GIAO DIỆN (UI/UX)
- **Framework:** `PyQt6`.
- **Thiết kế (Styling):** Sử dụng hệ thống QSS (Qt Style Sheets) tuỳ chỉnh với bảng màu *Catppuccin Mocha* (Dark Mode) chuẩn hiện đại. 
- **Tương tác Đồ hoạ (Interactive GUI):** 
  - Tích hợp lớp `ImageLabel` kế thừa từ `QLabel`, cho phép người dùng dùng chuột vẽ bounding box (Khung chữ nhật xanh) để định vị trực quan vùng cần che mờ (Blur) phụ đề gốc.
- **Xử lý Đa luồng (Multi-threading):** Giao diện được tách biệt hoàn toàn khỏi logic xử lý nặng thông qua kiến trúc `QThread` (UI Workers). Giúp UI không bao giờ bị "Not Responding" khi đang Render.

---

## 2. QUY TRÌNH XỬ LÝ LÕI (CORE PIPELINE)

Hệ thống hoạt động qua 3 trạm (3 Bước) nối tiếp nhau cực kỳ chặt chẽ:

### BƯỚC 1: TRÍCH XUẤT VÀ NHẬN DIỆN GIỌNG NÓI (STT - Speech-to-Text)
- **Kỹ thuật:** `FFmpeg` tách file `.wav` chuẩn 16kHz từ video MP4.
- **AI Model:** Sử dụng **Whisper** (OpenAI). Hệ thống tự động nhận diện phần cứng: Nếu có Card đồ hoạ Nvidia, model sẽ chạy trên `CUDA` (tốc độ ánh sáng); nếu không có sẽ tự động fallback về chạy `CPU`.
- **Output:** File `.srt` chứa nguyên bản kịch bản gốc khớp đến từng mili-giây.

### BƯỚC 2: DỊCH THUẬT VÀ VIỆT HOÁ (AI Translation)
- **Công nghệ cốt lõi:** LLM (Large Language Models).
- **Mô hình hỗ trợ:** `Gemini 2.0 Flash`, `Gemini 2.5 Flash-Lite` (Siêu nhanh), và `Groq (Qwen/Llama)`.
- **Tối ưu Rate Limit (Chống Block API):**
  - Áp dụng thuật toán **Batched Translation**: Gộp 80 dòng phụ đề thành 1 mẻ (batch) thay vì gửi từng câu.
  - Parse JSON khép kín: Ép AI trả về chuẩn cấu trúc JSON để bóc tách text mà không làm phá vỡ cấu trúc thời gian của file SRT gốc.
  - Prompt Engineering: Ép AI dịch theo phong cách Content Creator (hài hước, kịch tính, viral).

### BƯỚC 3: TỔNG HỢP GIỌNG ĐỌC AI (TTS - Text-to-Speech)
Đây là module được tối ưu hóa cực kỳ phức tạp để đảm bảo độ tự nhiên và khớp hình:
- **Nguồn giọng đa dạng:**
  - **TikTok/CapCut API:** Các giọng trend như *Nữ CapCut (VN), Nam CapCut (US)*.
  - **Edge-TTS (Microsoft):** Các giọng Neural AI siêu mượt (Hoài My, Nam Minh, Jenny) hoàn toàn Miễn phí & Không cần Key.
  - **gTTS (Google):** Chị Google huyền thoại.
- **Thuật toán Khớp Hình (Auto Time-Stretch / Native Speedup):**
  - Hệ thống đếm số từ (word_count) và đối chiếu với target_duration (thời lượng cho phép của câu đó). 
  - Nếu câu dịch tiếng Việt quá dài so với thời gian gốc, hệ thống tự động ép `speed_rate` cho API TikTok/Edge để giọng AI đọc nhanh lên (tối đa 1.5x) nhằm chèn vừa khít khuôn miệng nhân vật.
- **Kiến trúc Fault Tolerance (Chống lỗi diện rộng):**
  - Multithreading (`ThreadPoolExecutor`): Render nhiều câu thoại cùng lúc.
  - **Timeout & Fallback:** Nếu API TikTok chết hoặc timeout (10s), ngay lập tức Try-Catch bắt lỗi và chuyển giao sang Edge-TTS xử lý cứu hộ, đảm bảo Render hàng chục video không bao giờ bị đứt gánh.

---

## 3. MODULE XỬ LÝ HÌNH ẢNH & VIDEO (FFmpeg Processor)

Hệ thống điều khiển thư viện `ffmpeg-python` thông qua các bộ lọc (filters) ma trận siêu phức tạp.

**Quy trình Render cuối (Final Mix):**
1. **Lách Bản Quyền Âm Thanh:**
   - Kéo âm thanh gốc về 0% (Triệt tiêu hoàn toàn phổ quang âm thanh để chống Content ID).
   - Trộn âm: Giọng AI (Đã được sắp xếp khớp Timeline) + Nhạc Nền (BGM - Chèn ngoài).
2. **Xóa/Che Phụ đề Gốc (Blur):**
   - Áp dụng `boxblur` với thuật toán chia luồng (split/overlay) chính xác vào toạ độ khung xanh đã vẽ trên UI. Có tinh chỉnh luma_radius mượt mà.
3. **Phụ đề mới (Subtitles):**
   - Compile file SRT thành chuẩn `.ASS` (Advanced SubStation Alpha) để hỗ trợ can thiệp sâu: Cỡ chữ, Màu Chữ, Độ dày viền, Căn lề Y (Đẩy Sub lên cao xuống thấp).
4. **Bộ Khiên Lách Bản Quyền Hình Ảnh (Anti-Reup Shield):**
   - **Xóa Sạch Siêu Dữ Liệu (Metadata Eraser):** Tiêm tham số `-map_metadata -1` vào luồng xuất cuối cùng. Bóc tách và vứt bỏ hoàn toàn Tracking ID, EXIF data, GPS info và Device/Software Info của video gốc. File xuất ra được tính là một file "mới tinh tươm" ra lò (Zero-Day Creation).
   - **Static Watermark:** Đóng dấu Logo với Opacity bị ép cứng `10%` (0.1), neo cố định ở các góc. Vừa giấu danh tính tinh tế vừa lách quét diện rộng.
   - **Temporal Uniform Noise:** Bọc 1 lớp màng nhiễu hạt siêu nhỏ `noise=alls=3:allf=t+u`. Hạt nhiễu này thay đổi vị trí ngẫu nhiên theo từng khung hình (Temporal), khiến thuật toán MD5 hay Video Fingerprinting của YouTube/Facebook hoàn toàn bị mù.
   - **Lật Video / Thu Phóng (Dynamic Zoom):** Có hỗ trợ.
5. **Động cơ Xuất Video (Encoder):**
   - Tự động nhận diện phần cứng.
   - **Nvidia GPU:** Kích hoạt `h264_nvenc` với preset `fast`, ép `cq=23` (Cân bằng tuyệt đối Tốc độ - Chất lượng).
   - **CPU:** Fallback về `libx264` với preset `faster`, ép `crf=23` (Chuẩn xuất video nhẹ, sắc nét).

---

## 4. TỔNG KẾT
**Auto Vietsub Pro** hiện tại không chỉ là một tool dịch sub đơn thuần, mà là một **"Xưởng sản xuất Video tự động"** với độ chịu lỗi cực cao (Fault-tolerant), tiết kiệm chi phí vận hành API (Batched Prompting) và có khả năng Lách bản quyền hoàn hảo nhờ việc kết hợp triệt tiêu âm học và nhiễu động hình học.
