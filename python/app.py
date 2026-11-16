# -*- coding: utf-8 -*-
"""app.py - Hệ thống Quản lý kho kết hợp FastAPI và Text-to-SQL động bằng LLM an toàn"""

import math
import os
import re
import sqlite3
from collections import Counter, defaultdict

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 1. Khởi tạo FastAPI
app = FastAPI()

THU_MUC = os.path.dirname(os.path.abspath(__file__))

# 2. Kết nối database SQLite
conn = sqlite3.connect('quan_ly_kho.db', check_same_thread=False)
cursor = conn.cursor()

# Tạo toàn bộ các bảng theo chuẩn sơ đồ cơ sở dữ liệu kho
cursor.executescript('''
CREATE TABLE IF NOT EXISTS NhanVien (
    MaNV TEXT PRIMARY KEY,
    HoTen TEXT,
    ChucVu TEXT
);

CREATE TABLE IF NOT EXISTS NhaCungCap (
    MaNCC TEXT PRIMARY KEY,
    TenNCC TEXT,
    DiaChi TEXT,
    DienThoai TEXT
);

CREATE TABLE IF NOT EXISTS VatTu (
    MaVT TEXT PRIMARY KEY,
    TenVT TEXT,
    DonViTinh TEXT,
    GiaGoc REAL
);

CREATE TABLE IF NOT EXISTS Kho (
    MaKho TEXT PRIMARY KEY,
    TenKho TEXT,
    DiaChi TEXT
);

CREATE TABLE IF NOT EXISTS TonKho (
    MaKho TEXT,
    MaVT TEXT,
    SoLuongTon INTEGER,
    PRIMARY KEY (MaKho, MaVT)
);

CREATE TABLE IF NOT EXISTS PhieuNhap (
    MaPN TEXT PRIMARY KEY,
    NgayNhap TEXT,
    MaNCC TEXT,
    MaNV TEXT
);

CREATE TABLE IF NOT EXISTS ChiTietPhieuNhap (
    MaPN TEXT,
    MaVT TEXT,
    SoLuong INTEGER,
    DonGia REAL,
    PRIMARY KEY (MaPN, MaVT)
);

CREATE TABLE IF NOT EXISTS PhieuXuat (
    MaPX TEXT PRIMARY KEY,
    NgayXuat TEXT,
    NguoiNhan TEXT,
    MaNV TEXT
);

CREATE TABLE IF NOT EXISTS ChiTietPhieuXuat (
    MaPX TEXT,
    MaVT TEXT,
    SoLuong INTEGER,
    DonGia REAL,
    PRIMARY KEY (MaPX, MaVT)
);
''')

# Thêm dữ liệu mẫu
cursor.executescript('''
INSERT OR IGNORE INTO NhanVien VALUES ('NV01', 'Nguyen Van A', 'Thu kho');
INSERT OR IGNORE INTO NhanVien VALUES ('NV02', 'Tran Thi B', 'Nhan vien ban hang');

INSERT OR IGNORE INTO NhaCungCap VALUES ('NCC01', 'Cong ty VLXD Mien Trung', 'Quy Nhon', '0351234567');
INSERT OR IGNORE INTO NhaCungCap VALUES ('NCC02', 'Dai ly Sat Thep Nam A', 'Da Nang', '0905111222');

INSERT OR IGNORE INTO VatTu VALUES ('VT01', 'Xi mang Hoang Thach', 'Bao', 85000);
INSERT OR IGNORE INTO VatTu VALUES ('VT02', 'Sat phi 10 Pomina', 'Cay', 115000);
INSERT OR IGNORE INTO VatTu VALUES ('VT03', 'Gach ong 2 lo', 'Vien', 1200);

INSERT OR IGNORE INTO Kho VALUES ('K01', 'Kho Tong Quy Nhon', '150 An Duong Vuong');
INSERT OR IGNORE INTO Kho VALUES ('K02', 'Kho Phu', '12 Tran Hung Dao');

INSERT OR IGNORE INTO TonKho VALUES ('K01', 'VT01', 500);
INSERT OR IGNORE INTO TonKho VALUES ('K01', 'VT02', 200);
INSERT OR IGNORE INTO TonKho VALUES ('K02', 'VT03', 1000);

INSERT OR IGNORE INTO PhieuNhap VALUES ('PN01', '2026-06-01', 'NCC01', 'NV01');
INSERT OR IGNORE INTO PhieuNhap VALUES ('PN02', '2026-06-05', 'NCC02', 'NV01');

INSERT OR IGNORE INTO ChiTietPhieuNhap VALUES ('PN01', 'VT01', 500, 80000);
INSERT OR IGNORE INTO ChiTietPhieuNhap VALUES ('PN02', 'VT02', 200, 110000);

INSERT OR IGNORE INTO PhieuXuat VALUES ('PX01', '2026-06-10', 'Cong ty Xay dung ABC', 'NV02');
INSERT OR IGNORE INTO ChiTietPhieuXuat VALUES ('PX01', 'VT01', 50, 90000);
''')
conn.commit()

# Kết nối CHỈ ĐỌC dùng để chạy câu SQL do mô hình sinh ra
conn_doc = sqlite3.connect('file:quan_ly_kho.db?mode=ro', uri=True, check_same_thread=False)


# =====================================================================
# 3. NẠP CÁC BỘ DỮ LIỆU VÍ DỤ (Tự động tìm file đúng tên)
# =====================================================================
def tim_file(danh_sach_ten):
    for ten in danh_sach_ten:
        duong_dan = os.path.join(THU_MUC, ten)
        if os.path.exists(duong_dan):
            return duong_dan
    return None

FILE_SPIDER_7000 = tim_file(["spider_7000_vietnamese.csv", "spider_7000_vietnamese.csv"])
FILE_SPIDER_MAU = tim_file(["spider_sample_vietnamese_augmented.csv"])
FILE_VI_DU_KHO = tim_file(["vi_du_kho.csv"])

SO_VI_DU_KHO = 2
SO_VI_DU_SPIDER = 2
NGUONG_KHO = 0.10
NGUONG_SPIDER = 0.25
MAX_DO_DAI_SQL = 250


def chuan_hoa_sql(sql: str) -> str:
    sql = re.sub(r"\s+", " ", str(sql)).strip()
    return sql.replace(" ,", ",")


def them_vi_du(ds: list, da_co: set, cau_hoi, sql, db_id: str, nguon: str) -> None:
    if not isinstance(cau_hoi, str) or not isinstance(sql, str):
        return
    cau_hoi = re.sub(r"\s+", " ", cau_hoi).strip()
    sql = chuan_hoa_sql(sql)
    if not sql.lower().startswith("select") or len(sql) > MAX_DO_DAI_SQL:
        return
    khoa = (cau_hoi.lower(), sql)
    if khoa in da_co:
        return
    da_co.add(khoa)
    ds.append({"question": cau_hoi, "sql": sql, "db_id": db_id, "nguon": nguon})


def nap_spider_7000(ds: list, da_co: set) -> int:
    if not FILE_SPIDER_7000:
        print("[Ví dụ] Không tìm thấy file Spider 7000 nào trong thư mục.")
        return 0
    print(f"[Ví dụ] Đang đọc từ: {os.path.basename(FILE_SPIDER_7000)}")
    truoc = len(ds)
    try:
        df = pd.read_csv(FILE_SPIDER_7000, encoding="utf-8")
        # Xác định tên cột câu hỏi tiếng Việt
        cot_q = "question_vi" if "question_vi" in df.columns else "question"
        cot_query = "query" if "query" in df.columns else "sql"
        cot_db = "db_id" if "db_id" in df.columns else "db"

        for _, r in df.iterrows():
            q_val = r.get(cot_q)
            sql_val = r.get(cot_query)
            db_val = str(r.get(cot_db, "unknown"))
            if pd.notna(q_val) and pd.notna(sql_val):
                them_vi_du(ds, da_co, str(q_val), str(sql_val), db_val, "spider_7000")
    except Exception as e:
        print(f"[Ví dụ] Lỗi đọc file Spider 7000: {e}")
    return len(ds) - truoc


def nap_spider_mau(ds: list, da_co: set) -> int:
    if not FILE_SPIDER_MAU:
        return 0
    truoc = len(ds)
    try:
        df = pd.read_csv(FILE_SPIDER_MAU, encoding="utf-8")
        cot_hoi = ["question_original_vi", "question_variant_1", "question_variant_2", "question_vi", "question"]
        for _, r in df.iterrows():
            for c in cot_hoi:
                if c in df.columns and pd.notna(r[c]):
                    them_vi_du(ds, da_co, str(r[c]), str(r["query"]), str(r.get("db_id", "mau")), "spider_mau")
    except Exception as e:
        print(f"[Ví dụ] Lỗi đọc file Spider mẫu: {e}")
    return len(ds) - truoc


def nap_vi_du_kho(ds: list, da_co: set) -> int:
    if not FILE_VI_DU_KHO:
        return 0
    truoc = len(ds)
    try:
        df = pd.read_csv(FILE_VI_DU_KHO, encoding="utf-8")
        for _, r in df.iterrows():
            if pd.notna(r.get("question")) and pd.notna(r.get("query")):
                them_vi_du(ds, da_co, str(r["question"]), str(r["query"]), "kho", "kho")
    except Exception as e:
        print(f"[Ví dụ] Lỗi đọc file ví dụ kho: {e}")
    return len(ds) - truoc


def dac_trung(text: str) -> list:
    tu = re.findall(r"\w+", text.lower())
    return tu + [a + "_" + b for a, b in zip(tu, tu[1:])]


class ChiMucViDu:
    def __init__(self, vi_du: list):
        self.vi_du = vi_du
        df = Counter()
        docs = []
        for v in vi_du:
            dem = Counter(dac_trung(v["question"]))
            docs.append(dem)
            df.update(dem.keys())

        n = max(len(vi_du), 1)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.chi_muc = defaultdict(list)
        self.chuan = []
        for i, dem in enumerate(docs):
            w = {t: (1 + math.log(f)) * self.idf[t] for t, f in dem.items()}
            chuan = math.sqrt(sum(x * x for x in w.values())) or 1.0
            self.chuan.append(chuan)
            for t, x in w.items():
                self.chi_muc[t].append((i, x))

    def tim(self, cau_hoi: str, k: int, nguong: float) -> list:
        dem = Counter(dac_trung(cau_hoi))
        q = {t: (1 + math.log(f)) * self.idf[t] for t, f in dem.items() if t in self.idf}
        if not q:
            return []
        diem = defaultdict(float)
        for t, wq in q.items():
            for i, wd in self.chi_muc[t]:
                diem[i] += wq * wd
        chuan_q = math.sqrt(sum(x * x for x in q.values())) or 1.0

        xep = sorted(((s / (chuan_q * self.chuan[i]), i) for i, s in diem.items()), reverse=True)
        ket_qua, da_dung_sql, da_dung_hoi = [], set(), set()
        for do_giong, i in xep:
            if do_giong < nguong or len(ket_qua) >= k:
                break
            v = self.vi_du[i]
            hoi = v["question"].lower()
            if v["sql"] in da_dung_sql or hoi in da_dung_hoi:
                continue
            da_dung_sql.add(v["sql"])
            da_dung_hoi.add(hoi)
            ket_qua.append({**v, "do_giong": round(do_giong, 3)})
        return ket_qua


def khoi_tao_kho_vi_du():
    da_co: set = set()
    kho, spider = [], []
    n_kho = nap_vi_du_kho(kho, da_co)
    n_spider = nap_spider_7000(spider, da_co)
    n_mau = nap_spider_mau(spider, da_co)
    print(f"🎯 [Ví dụ] Kho: {n_kho} | Spider: {n_spider} | Mẫu: {n_mau}")
    return ChiMucViDu(kho), ChiMucViDu(spider), {"kho": n_kho, "spider_7000": n_spider, "spider_mau": n_mau}


CHI_MUC_KHO, CHI_MUC_SPIDER, THONG_KE_VI_DU = khoi_tao_kho_vi_du()


def lay_vi_du(cau_hoi: str) -> list:
    return (CHI_MUC_KHO.tim(cau_hoi, SO_VI_DU_KHO, NGUONG_KHO)
            + CHI_MUC_SPIDER.tim(cau_hoi, SO_VI_DU_SPIDER, NGUONG_SPIDER))


# =====================================================================
# 4. SINH SQL BẰNG LLM + KIỂM TRA AN TOÀN
# =====================================================================
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum|reindex)\b",
    re.IGNORECASE,
)


def lam_sach_sql(text: str) -> str:
    text = re.sub(r"```(?:sql)?", "", text, flags=re.IGNORECASE)
    m = re.search(r"\bselect\b", text, flags=re.IGNORECASE)
    if not m:
        return ""
    sql = text[m.start():]
    i = sql.find(";")
    if i != -1:
        sql = sql[:i]
    return sql.strip()


def sql_hop_le(sql: str) -> bool:
    sql = sql.strip().rstrip(";").strip()
    if not sql or not sql.lower().startswith("select"):
        return False
    khong_chuoi = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return ";" not in khong_chuoi and not FORBIDDEN.search(khong_chuoi)


class QueryRequest(BaseModel):
    question: str


def tao_prompt(user_query: str, database_schema: str) -> str:
    vi_du = lay_vi_du(user_query)
    ve_kho = [v for v in vi_du if v["nguon"] == "kho"]
    ve_spider = [v for v in vi_du if v["nguon"] != "kho"]

    phan_vi_du = ""
    if ve_kho:
        phan_vi_du += "Ví dụ ĐÚNG với cơ sở dữ liệu kho ở trên:\n"
        for v in ve_kho:
            phan_vi_du += f"Câu hỏi: {v['question']}\nSQL: {v['sql']}\n\n"
    if ve_spider:
        phan_vi_du += ("Ví dụ chỉ để tham khảo CÁCH VIẾT cú pháp SQL (tên bảng/cột trong các ví dụ này "
                       "thuộc cơ sở dữ liệu khác, KHÔNG được dùng):\n")
        for v in ve_spider:
            phan_vi_du += f"Câu hỏi: {v['question']}\nSQL: {v['sql']}\n\n"

    return f"""[INST] Bạn là một trợ lý AI chuyên gia Text-to-SQL cho hệ thống quản lý kho. 
Dựa vào cấu trúc schema cơ sở dữ liệu SQLite dưới đây:
{database_schema}

{phan_vi_du}Hãy viết một câu lệnh SQL (SQLite) chính xác để trả lời cho câu hỏi của người dùng: "{user_query}"
Lưu ý: Chỉ dùng các bảng và cột có trong schema ở trên. Chỉ trả về duy nhất câu lệnh SQL, không kèm theo giải thích hoặc ký tự bọc ngoài markdown nào khác. [/INST]"""


def generate_sql_with_codes_llm(user_query: str) -> str:
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

    prompt = tao_prompt(user_query, database_schema)

    try:
        import ollama
        response = ollama.chat(model='codes', messages=[{'role': 'user', 'content': prompt}])
        sql_result = lam_sach_sql(response['message']['content'])
        if sql_result and sql_hop_le(sql_result):
            return sql_result
    except Exception:
        pass

    # Cơ chế dự phòng thông minh (Fallback) phân tích từ khóa tiếng Việt
    query_lower = user_query.lower()
    
    if 'nhân viên' in query_lower or 'thủ kho' in query_lower:
        return "SELECT HoTen, ChucVu FROM NhanVien"
    elif 'tồn kho' in query_lower or 'vật tư trong kho' in query_lower:
        return "SELECT v.TenVT, k.TenKho, t.SoLuongTon, v.DonViTinh FROM TonKho t JOIN VatTu v ON t.MaVT = v.MaVT JOIN Kho k ON t.MaKho = k.MaKho"
    elif 'nhà cung cấp' in query_lower or 'ncc' in query_lower:
        return "SELECT TenNCC, DiaChi, DienThoai FROM NhaCungCap"
    elif 'phiếu nhập' in query_lower:
        return "SELECT p.MaPN, p.NgayNhap, n.TenNCC, nv.HoTen FROM PhieuNhap p JOIN NhaCungCap n ON p.MaNCC = n.MaNCC JOIN NhanVien nv ON p.MaNV = nv.MaNV"
    elif 'vật tư' in query_lower:
        return "SELECT TenVT, DonViTinh, GiaGoc FROM VatTu"
    
    return "SELECT * FROM VatTu"


@app.get("/api/vi_du")
def xem_vi_du(q: str = ""):
    return {
        "thong_ke": THONG_KE_VI_DU,
        "cau_hoi": q,
        "vi_du_duoc_chon": lay_vi_du(q) if q else [],
    }


@app.post("/api/query")
def process_query(request: QueryRequest):
    sql = generate_sql_with_codes_llm(request.question)
    
    if not sql:
        raise HTTPException(status_code=400, detail="Không thể sinh câu lệnh SQL cho câu hỏi này.")

    if not sql_hop_le(sql):
        raise HTTPException(status_code=400, detail="Chỉ cho phép câu lệnh SELECT.")

    try:
        df_result = pd.read_sql_query(sql, conn_doc)
        data_json = df_result.to_dict(orient="records")
        return {
            "status": "success",
            "model": "CodeS-Hybrid-Engine",
            "sql": sql,
            "data": data_json,
            "vi_du": [{"nguon": v["nguon"], "question": v["question"], "do_giong": v["do_giong"]}
                      for v in lay_vi_du(request.question)]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi thực thi câu lệnh SQL trên Database: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)