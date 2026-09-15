# pyrefly: ignore [missing-import]
import uvicorn
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()  # Nạp biến môi trường từ .env

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from starlette.middleware.base import BaseHTTPMiddleware
# pyrefly: ignore [missing-import]
from fastmcp import FastMCP

from ema_auth import verify_ema_token, generate_ema_token

# Khởi tạo FastMCP
mcp = FastMCP("Enterprise MCP Server")

@mcp.tool()
def get_enterprise_data(query: str) -> str:
    """Lấy dữ liệu doanh nghiệp bí mật."""
    return f"Dữ liệu doanh nghiệp bí mật cho query: {query}"

@mcp.tool()
def get_user_profile(user_id: str) -> str:
    """Lấy thông tin người dùng từ IdP."""
    return f"Profile của user {user_id}: Role=Admin, Department=IT"

# Khởi tạo FastAPI app
app = FastAPI(title="Enterprise MCP Gateway (Local OAuth)")

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/token")
def login_for_token(req: LoginRequest):
    """
    Endpoint OAuth cục bộ để demo.
    Kiểm tra username/password (hardcode: admin/admin123) và sinh JWT.
    """
    if req.username == "admin" and req.password == "admin123":
        # Sinh token bằng hàm từ ema_auth
        token = generate_ema_token(req.username)
        return {"access_token": token, "token_type": "bearer"}
    return JSONResponse(status_code=401, content={"detail": "Tài khoản hoặc mật khẩu không đúng"})

class EMAAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Bỏ qua xác thực cho các public endpoint nếu có, ví dụ /docs, /token
        if (request.url.path.startswith("/docs") or 
            request.url.path.startswith("/openapi") or 
            request.url.path.startswith("/token")):
            return await call_next(request)
            
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header. Expected 'Bearer ema_...'"}, 
                status_code=401
            )
        
        token = auth_header[7:]
        if not verify_ema_token(token):
            return JSONResponse(
                {"detail": "EMA Token verification failed"}, 
                status_code=403
            )
            
        return await call_next(request)

# Áp dụng middleware kiểm tra EMA token cho toàn bộ app
app.add_middleware(EMAAuthMiddleware)

class MCPPathRewriteMiddleware:
    """
    Middleware ASGI dùng để bóc tách và viết lại đường dẫn sao cho:
    - /mcp -> /sse
    - /mcp/messages -> /messages
    Để đảm bảo tương thích 100% với các client chỉ cho phép endpoint kết thúc bằng /mcp (ví dụ Claude Web).
    """
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == "/mcp":
                scope["path"] = "/sse"
            elif path == "/mcp/messages":
                scope["path"] = "/messages"
        return await self.app(scope, receive, send)

# Mount ASGI app của FastMCP vào root (đã được bọc bởi middleware viết lại path)
app.mount("/", MCPPathRewriteMiddleware(mcp.http_app))

if __name__ == "__main__":
    print("Khởi động MCP Server (FastAPI + FastMCP) tại http://localhost:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
