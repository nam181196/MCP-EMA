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
from starlette.middleware.base import BaseHTTPMiddleware
# pyrefly: ignore [missing-import]
from fastmcp import FastMCP, Context
from ema_auth import verify_ema_token

# Khởi tạo FastMCP
mcp = FastMCP("Enterprise MCP Server")

@mcp.tool()
def get_enterprise_data(query: str, ctx: Context) -> str:
    """Lấy dữ liệu doanh nghiệp bí mật."""
    # Lấy metadata từ JWT
    user = getattr(ctx.request.state, "user", {})
    metadata = user.get("metadata", {})
    role = metadata.get("role", "")
    
    if role not in ["admin", "director"]:
        return f"❌ Truy cập bị từ chối: Chỉ admin hoặc director mới được xem dữ liệu doanh nghiệp. Role hiện tại: {role or 'None'}"
        
    return f"Dữ liệu doanh nghiệp bí mật cho query: {query}"

@mcp.tool()
def get_user_profile(user_id: str, ctx: Context) -> str:
    """Lấy thông tin người dùng từ IdP."""
    user = getattr(ctx.request.state, "user", {})
    current_user_id = user.get("sub", "")
    metadata = user.get("metadata", {})
    role = metadata.get("role", "")
    
    if current_user_id != user_id and role != "hr":
        return f"❌ Truy cập bị từ chối: Bạn chỉ có thể xem profile của chính mình hoặc cần role HR."
        
    return f"Profile của user {user_id}: Role={role}, Department=IT"

# Khởi tạo FastAPI app
app = FastAPI(title="Enterprise MCP Gateway")

class EMAAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Bỏ qua xác thực cho các public endpoint nếu có, ví dụ /docs
        if request.url.path.startswith("/docs") or request.url.path.startswith("/openapi"):
            return await call_next(request)
            
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                {"detail": "Missing or invalid Authorization header. Expected 'Bearer ema_...'"}, 
                status_code=401
            )
        
        token = auth_header[7:]
        decoded_token = verify_ema_token(token)
        if not decoded_token:
            return JSONResponse(
                {"detail": "EMA Token verification failed"}, 
                status_code=403
            )
            
        # Tiêm thông tin user vào request state
        request.state.user = decoded_token
            
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
