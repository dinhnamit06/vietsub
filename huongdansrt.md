# BÍ KÍP XỬ LÝ HARDSUB (CHỮ NHẢY/CỐ ĐỊNH) VỚI VIDEO SUBTITLE EXTRACTOR (VSE) VÀ TOOL VIETSUB

Tài liệu này hướng dẫn bạn cách dùng công nghệ "Nhìn (OCR)" để trích xuất phụ đề cứng (Hardsub) tiếng Trung từ video gốc và đưa vào Tool Vietsub để dịch & lồng tiếng, thay vì dùng cách "Nghe (STT)" truyền thống. 

Phương pháp này ĐẶC BIỆT HIỆU QUẢ khi:
- Nhạc nền quá to, tiếng ồn lấn át giọng nói.
- Nhân vật nói tiếng địa phương, từ lóng khó nghe.
- Có chữ "cứng" (Hardsub) đính kèm sẵn trên video.

---

## PHẦN 1: TẢI VÀ SỬ DỤNG VIDEO SUBTITLE EXTRACTOR (VSE)

Video Subtitle Extractor (VSE) là phần mềm quét chữ từ hình ảnh cực kỳ nổi tiếng, miễn phí và sử dụng sức mạnh Card đồ họa của bạn.

### Bước 1: Tải phần mềm
1. Lên Google gõ tìm kiếm: **"Video Subtitle Extractor GitHub"** (hoặc truy cập trực tiếp repo của tác giả *bylwx* / *Yaojie*).
2. Tìm đến phần **Releases** ở cạnh phải trang web.
3. Tải file nén `.zip` mới nhất về máy (thường có dung lượng khá lớn vì chứa các model AI).
4. Giải nén ra một thư mục. (Nên để ở ổ C hoặc ổ D, tránh để trong thư mục có dấu tiếng Việt).

### Bước 2: Quét Video lấy file SRT
1. Chạy file `vse.exe` (hoặc tên tương tự) trong thư mục vừa giải nén để mở phần mềm.
2. Giao diện hiện lên, bạn bấm nút **"Mở Video"** (Open Video) và chọn video TikTok/Douyin của bạn.
3. **[QUAN TRỌNG] Chọn vùng quét:** 
   - Trên màn hình video, bạn dùng chuột kéo thả thanh trượt để khoanh đúng **vùng chứa phụ đề** (Subtitle Area). 
   - Đừng khoanh toàn màn hình! Chỉ khoanh cái dải băng dưới cùng nơi chữ xuất hiện để AI quét siêu tốc (như đã giải thích, nó sẽ soi sự thay đổi điểm ảnh).
4. Ở mục Ngôn ngữ (Language), chọn **Tiếng Trung** (Chinese) hoặc ngôn ngữ của chữ trên video.
5. Bấm nút **"Bắt đầu" (Run / Extract)**. 
6. Đợi phần mềm chạy xong. Nó sẽ soi từng khung hình có chữ và xuất ra cho bạn một file `.srt` tiếng Trung cực kỳ chính xác (từng mili-giây).

---

## PHẦN 2: KẾT HỢP VỚI TOOL VIETSUB CỦA BẠN

Bây giờ bạn đã có file SRT tiếng Trung chuẩn 100% lấy từ "Mắt thần". Hãy nạp nó vào Tool của chúng ta!

### Bước 1: Khởi tạo Video
1. Mở **Auto Vietsub Pro** lên.
2. Ở Tab **Bước 1**, bấm "📂 Chọn File" và trỏ đến video gốc mà bạn vừa dùng ở trên.
3. **KHÔNG** bấm nút "Bắt đầu Xử lý Bước 1" (Vì chúng ta không cần nghe âm thanh nữa).

### Bước 2: Nạp "Linh hồn" cho Video
1. Chuyển sang Tab **"Bước 2 (Chỉnh Phụ Đề)"** trên thanh công cụ.
2. Bấm nút **"📥 Nhập SRT"** và chọn cái file `.srt` tiếng Trung mà VSE vừa tạo ra.
3. Bảng phụ đề sẽ ngay lập tức được lấp đầy bởi các dòng tiếng Trung chuẩn xác.

### Bước 3: Dịch thuật, Lồng tiếng và Render
1. Chuyển sang Tab **"Bước 3 (Xuất Video)"**.
2. **Cấu hình chống đè chữ:** Chọn Kiểu viền phụ đề là **"Khung nền mờ (Opaque Box)"**. Nhớ căn chỉnh Vị trí chiều dọc (Margin V) để lát nữa cái hộp đen của tiếng Việt đè khít lên cái chữ tiếng Trung gốc.
3. Tắt luôn âm thanh gốc: Kéo thanh **"Âm lượng Video gốc"** về **0%** để tránh bị tạp âm.
4. Chọn giọng đọc (CapCut/Edge) như bình thường.
5. Bấm **"🎥 Render Video Cuối (Bước 3)"**.

🎉 **Xong!** 
Tool Vietsub sẽ tự động tóm gọn mớ tiếng Trung trong bảng, nhờ AI Gemini/Groq dịch siêu tốc sang tiếng Việt, cho AI đọc diễn cảm, tự động tua nhanh tốc độ cho khớp nhịp, rồi ép cái hộp đen lên che sạch chữ cũ. Bạn sẽ có một video Reup hoàn hảo!
