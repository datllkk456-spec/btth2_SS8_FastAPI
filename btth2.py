from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# Khởi tạo ứng dụng FastAPI
app = FastAPI(title="IT Asset Management API")

# --- 1. ENUM & DỮ LIỆU MẪU ---
class AssetStatus(str, Enum):
    READY = "READY"
    ALLOCATED = "ALLOCATED"
    REPAIRING = "REPAIRING"
    SCRAPPED = "SCRAPPED"

assets_db = [
    {"id": 1, "serial_number": "SN-MAC-01", "model": "MacBook Pro M3", "stock_available": 5, "status": "READY"},
    {"id": 2, "serial_number": "SN-DELL-02", "model": "Dell UltraSharp 27", "stock_available": 10, "status": "READY"},
    {"id": 3, "serial_number": "SN-THINK-03", "model": "ThinkPad X1 Carbon", "stock_available": 0, "status": "REPAIRING"}
]

allocations_db = [
    {
        "id": 1,
        "asset_id": 1,
        "employee_email": "dev.nguyen@company.com",
        "allocated_quantity": 1,
        "start_date": "2026-07-01",
        "duration_months": 12
    }
]

# --- 2. CÁC LỚP RÀNG BUỘC DỮ LIỆU (PYDANTIC MODELS) ---
class AssetBase(BaseModel):
    serial_number: str
    # model có độ dài từ 2 đến 255 ký tự
    model: str = Field(..., min_length=2, max_length=255)
    # stock_available phải là số nguyên >= 0 (ge = greater than or equal)
    stock_available: int = Field(..., ge=0)
    status: AssetStatus

class AssetResponse(AssetBase):
    id: int

class AllocationCreate(BaseModel):
    asset_id: int
    # Kiểm tra email bằng Regex (Biểu thức chính quy)
    employee_email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
    # Số lượng cấp phát lớn hơn 0 (gt = greater than)
    allocated_quantity: int = Field(..., gt=0)
    start_date: str
    # Thời gian mượn từ 1 đến 12 tháng
    duration_months: int = Field(..., ge=1, le=12)

class AllocationResponse(AllocationCreate):
    id: int

# --- 3. API CHO TÀI SẢN (ASSETS) ---
@app.get("/assets", response_model=List[AssetResponse])
def get_assets(
    keyword: Optional[str] = Query(None, description="Tìm theo serial_number hoặc model"),
    status: Optional[AssetStatus] = Query(None, description="Lọc theo trạng thái"),
    min_stock: Optional[int] = Query(None, description="Tồn kho khả dụng tối thiểu")
):
    result = assets_db
    if keyword:
        kw = keyword.lower()
        result = [a for a in result if kw in a["serial_number"].lower() or kw in a["model"].lower()]
    if status:
        result = [a for a in result if a["status"] == status]
    if min_stock is not None:
        result = [a for a in result if a["stock_available"] >= min_stock]
    
    return result

@app.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset_detail(asset_id: int):
    asset = next((a for a in assets_db if a["id"] == asset_id), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@app.post("/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(asset: AssetBase):
    # Kiểm tra tính duy nhất của serial_number
    if any(a["serial_number"] == asset.serial_number for a in assets_db):
        raise HTTPException(status_code=400, detail="Serial number đã tồn tại")
    
    # Tạo ID tự động tăng
    new_id = max((a["id"] for a in assets_db), default=0) + 1
    new_asset = {"id": new_id, **asset.model_dump()}
    assets_db.append(new_asset)
    return new_asset

@app.put("/assets/{asset_id}", response_model=AssetResponse)
def update_asset(asset_id: int, asset_update: AssetBase):
    # 1. Kiểm tra xem ID có tồn tại không
    index = next((i for i, a in enumerate(assets_db) if a["id"] == asset_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # 2. Kiểm tra trùng lặp serial_number (bỏ qua chính thiết bị đang sửa)
    if any(a["serial_number"] == asset_update.serial_number and a["id"] != asset_id for a in assets_db):
        raise HTTPException(status_code=400, detail="Serial number đã bị trùng với thiết bị khác")
        
    # Cập nhật
    assets_db[index].update(asset_update.model_dump())
    return assets_db[index]

@app.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: int):
    index = next((i for i, a in enumerate(assets_db) if a["id"] == asset_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    assets_db.pop(index)
    return None


# --- 4. API CHO CẤP PHÁT (ALLOCATIONS) ---
@app.get("/allocations", response_model=List[AllocationResponse])
def get_allocations():
    return allocations_db

@app.post("/allocations", response_model=AllocationResponse, status_code=status.HTTP_201_CREATED)
def create_allocation(alloc: AllocationCreate):
    # Tìm thông tin tài sản cần cấp phát
    asset = next((a for a in assets_db if a["id"] == alloc.asset_id), None)
    
    # Kiểm tra nghiệp vụ theo yêu cầu bài toán
    if not asset:
        raise HTTPException(status_code=400, detail="Thiết bị không tồn tại trong hệ thống")
        
    if asset["status"] != "READY":
        raise HTTPException(status_code=400, detail="Thiết bị hiện không ở trạng thái READY để bàn giao")
        
    if alloc.allocated_quantity > asset["stock_available"]:
        raise HTTPException(status_code=400, detail="Số lượng yêu cầu vượt quá số lượng tồn kho khả dụng")
    
    # (Tùy chọn bổ sung thực tế) Có thể trừ đi số lượng stock_available của asset sau khi bàn giao
    # asset["stock_available"] -= alloc.allocated_quantity
    
    # Thêm mới lịch sử cấp phát
    new_id = max((al["id"] for al in allocations_db), default=0) + 1
    new_allocation = {"id": new_id, **alloc.model_dump()}
    allocations_db.append(new_allocation)
    
    return new_allocation
