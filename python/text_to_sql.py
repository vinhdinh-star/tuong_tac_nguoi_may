# -*- coding: utf-8 -*-
"""text_to_sql.py - API Text-to-SQL trả về trực tiếp chuỗi câu lệnh SQL"""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI()

class QueryRequest(BaseModel):
    question: str

def convert_vietnamese_to_sql(user_query: str) -> str:
    """
    Hàm dịch câu hỏi tiếng Việt sang câu lệnh SQL (SQLite)
    """
    database_schema = """
    Cơ sở dữ liệu SQLite Quản lý Kho gồm các bảng sau:
    1. NhanVien (MaNV, HoTen, ChucVu)
    2. NhaCungCap (MaNCC, TenNCC, DiaChi, DienThoai)
    3. VatTu (MaVT, TenVT, DonViTinh, GiaGoc)
    4. Kho (MaKho, TenKho, DiaChi)
    5. TonKho (MaKho, MaVT, SoLuongTon)
    6. PhieuNhap (MaPN, NgayNhap, MaNCC, MaNV)
    7. ChiTietPhieuNhap (MaPN, MaVT, SoLuong, DonGia)
    8. PhieuXuat (MaPX, NgayXuat, NguoiNhan, MaNV)
    9. ChiTietPhieuXuat (MaPX, MaVT, SoLuong, DonGia)
    """

    # 1. Thử gọi mô hình LLM (Ollama / CodeS nếu có)
    try:
        import ollama
        prompt = f"""[INST] Bạn là một chuyên gia Text-to-SQL. Dựa vào schema sau:
{database_schema}
Hãy viết câu lệnh SQL SQLite cho câu hỏi: "{user_query}"
Chỉ trả về duy nhất câu lệnh SQL, không kèm giải thích hay markdown. [/INST]"""

        response = ollama.chat(model='codes', messages=[{'role': 'user', 'content': prompt}])
        sql_result = response['message']['content'].strip()
        if sql_result:
            return sql_result
    except Exception:
        pass

    # 2. Xử lý dự phòng (Fallback) bằng từ khóa ngữ nghĩa tiếng Việt
    query_lower = user_query.lower()

    if 'nhân viên' in query_lower or 'thủ kho' in query_lower or 'danh sách nhân viên' in query_lower:
        return "SELECT HoTen, ChucVu FROM NhanVien;"
    elif 'tồn kho' in query_lower or 'vật tư trong kho' in query_lower:
        return "SELECT v.TenVT, k.TenKho, t.SoLuongTon, v.DonViTinh FROM TonKho t JOIN VatTu v ON t.MaVT = v.MaVT JOIN Kho k ON t.MaKho = k.MaKho;"
    elif 'nhà cung cấp' in query_lower or 'ncc' in query_lower:
        return "SELECT TenNCC, DiaChi, DienThoai FROM NhaCungCap;"
    elif 'phiếu nhập' in query_lower:
        return "SELECT p.MaPN, p.NgayNhap, n.TenNCC, nv.HoTen FROM PhieuNhap p JOIN NhaCungCap n ON p.MaNCC = n.MaNCC JOIN NhanVien nv ON p.MaNV = nv.MaNV;"
    elif 'vật tư' in query_lower:
        return "SELECT TenVT, DonViTinh, GiaGoc FROM VatTu;"

    return "SELECT * FROM VatTu;"

# Sử dụng PlainTextResponse để API trả về trực tiếp định dạng chuỗi văn bản SQL
@app.post("/api/to-sql", response_class=PlainTextResponse)
def translate_to_sql(request: QueryRequest):
    sql_query = convert_vietnamese_to_sql(request.question)
    return sql_query

if __name__ == "__main__":
    uvicorn.run("text_to_sql:app", host="127.0.0.1", port=8000, reload=True)