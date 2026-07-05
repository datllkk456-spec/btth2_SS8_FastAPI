
from enum import Enum
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field, EmailStr

app=FastAPI(title="IT Asset Management")

class AssetStatus(str,Enum):
    READY="READY";ALLOCATED="ALLOCATED";REPAIRING="REPAIRING";SCRAPPED="SCRAPPED"

assets=[
{"id":1,"serial_number":"SN-MAC-01","model":"MacBook Pro M3","stock_available":5,"status":"READY"},
{"id":2,"serial_number":"SN-DELL-02","model":"Dell UltraSharp 27","stock_available":10,"status":"READY"},
{"id":3,"serial_number":"SN-THINK-03","model":"ThinkPad X1 Carbon","stock_available":0,"status":"REPAIRING"}]
allocations=[{"id":1,"asset_id":1,"employee_email":"dev.nguyen@company.com","allocated_quantity":1,"start_date":"2026-07-01","duration_months":12}]

class AssetIn(BaseModel):
    serial_number:str
    model:str=Field(min_length=2,max_length=255)
    stock_available:int=Field(ge=0)
    status:AssetStatus
class AssetOut(AssetIn): id:int
class AllocationIn(BaseModel):
    asset_id:int
    employee_email:EmailStr
    allocated_quantity:int=Field(gt=0)
    start_date:str
    duration_months:int=Field(ge=1,le=12)
class AllocationOut(AllocationIn): id:int

def get_asset(i):
    for a in assets:
        if a["id"]==i:return a
    raise HTTPException(404,"Asset not found")

@app.post("/assets",response_model=AssetOut,status_code=201)
def create(x:AssetIn):
    if any(a["serial_number"].lower()==x.serial_number.lower() for a in assets):
        raise HTTPException(400,"Serial number already exists")
    d=x.model_dump();d["status"]=x.status.value;d["id"]=max(a["id"] for a in assets)+1;assets.append(d);return d

@app.get("/assets",response_model=list[AssetOut])
def list_assets(keyword:str|None=None,status:AssetStatus|None=None,min_stock:int|None=Query(None)):
    rs=assets
    if keyword:
        k=keyword.lower();rs=[a for a in rs if k in a["serial_number"].lower() or k in a["model"].lower()]
    if status: rs=[a for a in rs if a["status"]==status.value]
    if min_stock is not None: rs=[a for a in rs if a["stock_available"]>=min_stock]
    return rs

@app.get("/assets/{asset_id}",response_model=AssetOut)
def detail(asset_id:int): return get_asset(asset_id)

@app.put("/assets/{asset_id}",response_model=AssetOut)
def update(asset_id:int,x:AssetIn):
    a=get_asset(asset_id)
    if any(i["id"]!=asset_id and i["serial_number"].lower()==x.serial_number.lower() for i in assets):
        raise HTTPException(400,"Serial number already exists")
    a.update(x.model_dump());a["status"]=x.status.value;return a

@app.delete("/assets/{asset_id}")
def delete(asset_id:int):
    a=get_asset(asset_id);assets.remove(a);return {"message":"Asset deleted successfully"}

@app.post("/allocations",response_model=AllocationOut,status_code=201)
def alloc(x:AllocationIn):
    a=get_asset(x.asset_id)
    if a["status"]!="READY": raise HTTPException(400,"Asset is not READY")
    if x.allocated_quantity>a["stock_available"]: raise HTTPException(400,"Allocated quantity exceeds stock")
    a["stock_available"]-=x.allocated_quantity
    if a["stock_available"]==0:a["status"]="ALLOCATED"
    d=x.model_dump();d["id"]=max([i["id"] for i in allocations],default=0)+1;allocations.append(d);return d

@app.get("/allocations",response_model=list[AllocationOut])
def list_allocations(): return allocations
