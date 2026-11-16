# tuong_tac_nguoi_may
# https://github.com/vinhdinh-star/hoithoai_thongminh


# 📦 Hệ thống Text-to-SQL Quản lý Kho thông minh (FastAPI + LLM + In-Context Learning)

Hệ thống ứng dụng trí tuệ nhân tạo (Text-to-SQL) giúp chuyển đổi câu hỏi bằng ngôn ngữ tự nhiên tiếng Việt thành câu lệnh SQL chuẩn xác, kết nối trực tiếp với cơ sở dữ liệu quản lý kho vật liệu xây dựng (VLXD). Dự án tích hợp cơ chế **In-Context Learning (Học theo ngữ cảnh)** từ hàng ngàn mẫu dữ liệu (Spider dataset) kết hợp cùng mô hình ngôn ngữ lớn (LLM) và giao diện API tốc độ cao bằng **FastAPI**.

---

## 🚀 Các Tính Năng Nổi Bật

1. **Chuyển đổi Text-to-SQL thông minh:** Nhận câu hỏi tiếng Việt linh hoạt từ người dùng và tự động sinh câu lệnh `SELECT` tối ưu.
2. **Học theo ngữ cảnh động (In-Context Learning / Few-Shot):** Tự động tìm kiếm các câu hỏi tương tự nhất từ bộ dữ liệu mẫu lớn (`spider_7000_vietnamese.csv`) để đưa vào prompt giúp mô hình LLM hiểu rõ ngữ cảnh nghiệp vụ.
3. **Cơ chế An toàn (SQL Safety Validation):** Kiểm tra chặt chẽ cấu trúc câu lệnh SQL, chỉ cho phép các câu lệnh truy vấn dữ liệu (`SELECT`), ngăn chặn tuyệt đối các lệnh nguy hiểm (`DROP`, `DELETE`, `UPDATE`, `INSERT`, v.v.).
4. **Kiến trúc Lai (Hybrid Fallback Engine):** Hỗ trợ gọi mô hình LLM chuyên biệt (CodeS qua Ollama) kết hợp cùng hệ thống dự phòng từ khóa chuyên ngành kho giúp hệ thống luôn hoạt động ổn định (không bao giờ trả về lỗi 500 khi chưa bật AI local).
5. **Giao diện API chuẩn RESTful:** Xây dựng trên nền tảng **FastAPI** với tài liệu Swagger UI trực quan.

---

## 📂 Cấu trúc Cơ sở dữ liệu (Schema)

Hệ thống quản lý kho gồm 9 bảng chính chuẩn hóa quan hệ:
* `NhanVien` (MaNV, HoTen, ChucVu)
* `NhaCungCap` (MaNCC, TenNCC, DiaChi, DienThoai)
* `VatTu` (MaVT, TenVT, DonViTinh, GiaGoc)
* `Kho` (MaKho, TenKho, DiaChi)
* `TonKho` (MaKho, MaVT, SoLuongTon)
* `PhieuNhap` & `ChiTietPhieuNhap` (Quản lý nhập hàng)
* `PhieuXuat` & `ChiTietPhieuXuat` (Quản lý xuất hàng)

---

## 🛠️ Cài đặt và Chạy Dự án

### 1. Yêu cầu hệ thống
* Python 3.11 trở lên
* Các file dữ liệu mẫu đặt cùng thư mục:
  * `spider_7000_vietnamese.csv` (hoặc `spider_7000_vietnamese_2.csv`)
  * `spider_sample_vietnamese_augmented.csv` *(tùy chọn)*
  * `https://huggingface.co/datasets/xlangai/spider`

### 2. Cài đặt các thư viện phụ thuộc
Chạy lệnh sau trên terminal để cài đặt FastAPI, Uvicorn, Pandas và các thư viện cần thiết:
```bash
pip install fastapi uvicorn pandas ollama
