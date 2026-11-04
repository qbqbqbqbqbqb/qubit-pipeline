from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from png_routes import png_router
from profile_routes import profile_router
from log_routes import log_router

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(png_router)
app.include_router(profile_router)
app.include_router(log_router)


@app.get("/", response_class=HTMLResponse)
async def control_page(request: Request):
    return templates.TemplateResponse(request=request, name="control.html")