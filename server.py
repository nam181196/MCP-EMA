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

# Khởi tạo FastMCP - Đại diện cho CRM MCP
mcp = FastMCP("CRM MCP")

# --- MOCK DATABASE TẠM THỜI ĐỂ LƯU QUYỀN CỦA USER ---
# Trong thực tế, bạn sẽ query cái này từ PostgreSQL, MongoDB, Redis, v.v.
MOCK_PERMISSION_DB = {
    "user_1": {
        "allowed_mcps": ["CRM MCP"],
        "permissions": ["orders.read", "orders.update"]
    },
    "user_2": {
        "allowed_mcps": ["CRM MCP"],
        "permissions": ["orders.read", "users.read"]
    }
}

def has_permission(ctx: Context, required_permission: str) -> bool:
    """Hàm helper để kiểm tra xem user hiện tại có quyền cụ thể không."""
    user = getattr(ctx.request.state, "user", {})
    user_id = user.get("sub", "")
    
    # Tra cứu user_id trong Database
    user_record = MOCK_PERMISSION_DB.get(user_id)
    if not user_record:
        return False
        
    return required_permission in user_record.get("permissions", [])

# --- ĐỊNH NGHĨA CÁC TOOLS VỚI PHÂN QUYỀN CHI TIẾT ---

@mcp.tool()
def read_orders(ctx: Context) -> str:
    """Lấy danh sách các đơn hàng (Yêu cầu quyền: orders.read)."""
    if not has_permission(ctx, "orders.read"):
        return "❌ Lỗi: Bạn không có quyền truy cập dữ liệu (Missing 'orders.read')."
    return "✅ [DATA] Danh sách đơn hàng: Order01 (100$), Order02 (500$)."

@mcp.tool()
def update_orders(order_id: str, status: str, ctx: Context) -> str:
    """Cập nhật trạng thái đơn hàng (Yêu cầu quyền: orders.update)."""
    if not has_permission(ctx, "orders.update"):
        return "❌ Lỗi: Bạn không được phép sửa đơn hàng (Missing 'orders.update')."
    return f"✅ [SUCCESS] Đã cập nhật đơn hàng {order_id} thành {status}."

@mcp.tool()
def read_users(ctx: Context) -> str:
    """Xem danh sách khách hàng (Yêu cầu quyền: users.read)."""
    if not has_permission(ctx, "users.read"):
        return "❌ Lỗi: Bạn không có quyền truy cập dữ liệu người dùng (Missing 'users.read')."
    return "✅ [DATA] Danh sách User: KH_A, KH_B, KH_C."

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
            
        user_id = decoded_token.get("sub")
        
        # Kiểm tra xem User có được phép kết nối vào MCP này không (Global Check)
        user_record = MOCK_PERMISSION_DB.get(user_id)
        if not user_record or "CRM MCP" not in user_record.get("allowed_mcps", []):
            return JSONResponse(
                {"detail": f"Access Denied: User {user_id} is not allowed to access CRM MCP"}, 
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
