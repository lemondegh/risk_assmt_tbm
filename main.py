import os
from typing import Optional
from fastapi import FastAPI, Form, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from app.core.dify_client import DifyTBMClient

app = FastAPI(
    title="Safety TBM Copilot",
    description="산업 현장 위험성평가표 및 TBM 안전일지 자동 생성기",
    version="1.0.0"
)

templates = Jinja2Templates(directory="app/templates")
dify_client = DifyTBMClient()

class TBMRequestModel(BaseModel):
    site_name: str
    work_date: str
    work_description: str
    worker_count: str = "10"

class ConfigUpdateModel(BaseModel):
    dify_api_key: str
    dify_base_url: Optional[str] = "https://api.dify.ai/v1"

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "dify_configured": bool(os.getenv("DIFY_API_KEY", "").strip())
    })

@app.post("/api/generate-tbm")
async def generate_tbm(
    request: Request,
    site_name: Optional[str] = Form(None),
    work_date: Optional[str] = Form(None),
    work_description: Optional[str] = Form(None),
    worker_count: Optional[str] = Form("10"),
    allow_generative_accident: Optional[str] = Form("true")
):
    try:
        # JSON 요청과 Form 요청 모두 지원
        content_type = request.headers.get("content-type", "")
        allow_gen = True
        if "application/json" in content_type:
            body = await request.json()
            site_name = body.get("site_name", "")
            work_date = body.get("work_date", "")
            work_description = body.get("work_description", "")
            worker_count = str(body.get("worker_count", "10"))
            allow_gen = bool(body.get("allow_generative_accident", True))
        else:
            allow_gen = str(allow_generative_accident).lower() in ("true", "1", "yes", "on")

        if not site_name or not work_date or not work_description:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "현장명, 작업일자, 작업 내용을 모두 입력해 주세요."}
            )

        report = dify_client.generate_tbm_report(site_name, work_date, work_description, worker_count, allow_gen)
        return JSONResponse(content={"status": "success", "data": report})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/api/config-status")
async def get_config_status():
    api_key = os.getenv("DIFY_API_KEY", "").strip()
    return JSONResponse(content={
        "status": "success",
        "dify_configured": bool(api_key),
        "dify_masked_key": f"{api_key[:4]}****{api_key[-4:]}" if len(api_key) > 8 else ("설정됨" if api_key else "미설정 (KOSHA 지능형 로컬 엔진 가동)"),
        "dify_base_url": os.getenv("DIFY_BASE_URL", "https://api.dify.ai/v1")
    })

@app.post("/api/update-config")
async def update_config(config: ConfigUpdateModel):
    try:
        env_path = ".env"
        # .env 파일 갱신
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()
        
        new_lines = []
        key_found = False
        url_found = False
        for line in env_lines:
            if line.startswith("DIFY_API_KEY="):
                new_lines.append(f"DIFY_API_KEY={config.dify_api_key.strip()}\n")
                key_found = True
            elif line.startswith("DIFY_BASE_URL="):
                new_lines.append(f"DIFY_BASE_URL={(config.dify_base_url or 'https://api.dify.ai/v1').strip()}\n")
                url_found = True
            else:
                new_lines.append(line)
        
        if not key_found:
            new_lines.append(f"DIFY_API_KEY={config.dify_api_key.strip()}\n")
        if not url_found:
            new_lines.append(f"DIFY_BASE_URL={(config.dify_base_url or 'https://api.dify.ai/v1').strip()}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        os.environ["DIFY_API_KEY"] = config.dify_api_key.strip()
        os.environ["DIFY_BASE_URL"] = (config.dify_base_url or 'https://api.dify.ai/v1').strip()
        dify_client.reload_config()

        return JSONResponse(content={"status": "success", "message": "Dify 설정이 성공적으로 저장되었습니다."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8089"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
