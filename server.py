# pyrefly: ignore [missing-import]
import uvicorn
import uuid
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
load_dotenv()  # Nạp biến môi trường từ .env

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Request
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse
# pyrefly: ignore [missing-import]
from starlette.middleware.base import BaseHTTPMiddleware
# pyrefly: ignore [missing-import]
from mcp.server.mcpserver import MCPServer

from ema_auth import verify_ema_token

# Khởi tạo FastMCP - Đại diện cho CRM MCP
mcp = MCPServer("CRM MCP")

# Bảng Phân quyền Động dựa trên Role (Role-based Access Control Matrix)
# Thay vì lưu user_id, ta định nghĩa quyền hạn cho các Role chung.
ROLE_PERMISSIONS = {
    "customer": {
        "allowed_mcps": ["CRM MCP"],
        "permissions": ["products.read", "orders.read_own", "orders.create"]
    },
    "staff": {
        "allowed_mcps": ["CRM MCP"],
        "permissions": ["products.read", "orders.read_all", "orders.update"]
    },
    "admin": {
        "allowed_mcps": ["CRM MCP"],
        "permissions": ["products.read", "products.write", "orders.read_all", "orders.update", "users.read_all", "stats.read"]
    }
}

# --- GLOBAL SESSION STORE ---
# Lưu trữ ánh xạ: session_id -> {"user_id": "...", "role": "..."}
SESSIONS = {}

def has_permission(session_id: str, required_permission: str) -> bool:
    """Hàm helper để kiểm tra xem user hiện tại có quyền cụ thể không dựa vào Role trên Clerk."""
    session_data = SESSIONS.get(session_id)
    if not session_data:
        return False
        
    # Tra cứu Role trong Bảng Phân quyền
    role = session_data.get("role")
    role_record = ROLE_PERMISSIONS.get(role)
    if not role_record:
        return False
        
    return required_permission in role_record.get("permissions", [])

# --- ĐỊNH NGHĨA CÁC TOOLS VỚI PHÂN QUYỀN CHI TIẾT ---

@mcp.tool()
def login() -> str:
    """Sử dụng công cụ này khi người dùng muốn đăng nhập. Nó sẽ trả về một link đăng nhập và một session_id."""
    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = None
    
    login_url = f"http://localhost:3000/demo_login.html?session_id={session_id}"
    return f"Vui lòng cung cấp link này cho người dùng để họ đăng nhập: {login_url}\n\nQuan trọng: Bắt buộc nhắc người dùng quay lại đây báo cáo sau khi đăng nhập xong. Sau đó, hãy dùng {session_id} truyền vào tham số 'session_id' của tất cả các công cụ khác."

@mcp.tool()
def get_products(session_id: str) -> str:
    """Lấy danh sách sản phẩm hiển thị trên Cửa hàng (Yêu cầu quyền: products.read)."""
    if not has_permission(session_id, "products.read"):
        return "❌ Lỗi: Bạn chưa đăng nhập hoặc không có quyền xem sản phẩm."
    return "✅ [DATA] Bảng `products`: \n1. Giày Nike Air Max (Giá: $120)\n2. Áo thun Adidas (Giá: $30)\n3. Quần thể thao Puma (Giá: $45)"

@mcp.tool()
def get_all_orders(session_id: str) -> str:
    """[Dành cho Admin/Staff] Lấy toàn bộ danh sách đơn hàng của hệ thống (Yêu cầu quyền: orders.read_all)."""
    if not has_permission(session_id, "orders.read_all"):
        return "❌ Lỗi: Từ chối truy cập. Chỉ Nhân viên hoặc Admin mới được xem toàn bộ đơn hàng của hệ thống."
    return "✅ [DATA] Bảng `orders` (Tất cả): \n- Đơn #001: Giày Nike -> Đang giao\n- Đơn #002: Áo thun Adidas -> Đã giao"

@mcp.tool()
def get_my_orders(session_id: str) -> str:
    """[Dành cho Customer] Lấy danh sách đơn hàng của chính bạn (Yêu cầu quyền: orders.read_own)."""
    if not has_permission(session_id, "orders.read_own"):
        return "❌ Lỗi: Từ chối truy cập (Missing 'orders.read_own')."
    
    # Lấy User ID hiện tại từ Session
    session_data = SESSIONS.get(session_id)
    current_user_id = session_data.get("user_id") if session_data else "Unknown"
    return f"✅ [DATA] Đơn hàng của {current_user_id}: \n- Đơn #999: Quần thể thao Puma -> Chờ xử lý"

@mcp.tool()
def update_order_status(session_id: str, order_id: str, status: str) -> str:
    """[Dành cho Admin/Staff] Cập nhật trạng thái đơn hàng (Yêu cầu quyền: orders.update)."""
    if not has_permission(session_id, "orders.update"):
        return "❌ Lỗi: Khách hàng không được phép sửa trạng thái đơn hàng (Missing 'orders.update')."
    return f"✅ [SUCCESS] Bảng `orders`: Đã cập nhật đơn hàng {order_id} thành trạng thái '{status}'."

@mcp.tool()
def get_all_users(session_id: str) -> str:
    """[Dành cho Admin] Xem danh sách tất cả tài khoản hệ thống (Yêu cầu quyền: users.read_all)."""
    if not has_permission(session_id, "users.read_all"):
        return "❌ Lỗi: Từ chối truy cập! Chỉ Admin mới được quyền xem danh sách khách hàng."
    return "✅ [DATA] Bảng `users`: \n- user_2jF3sP... (Customer)\n- user_staff_xyz (Staff)\n- user_admin_abc (Admin)"


# Khởi tạo FastAPI app
mcp_app = mcp.sse_app(sse_path="/mcp/sse", message_path="/mcp/messages/", host="*")
app = FastAPI(title="Enterprise MCP Gateway")

# Cấu hình CORS để Frontend (port 3000) có thể fetch API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/auth")
def auth_callback(session_id: str, token: str):
    """API để Frontend gửi Token về cho Server sau khi đăng nhập thành công"""
    if not session_id or not token:
        return JSONResponse({"error": "Thiếu session_id hoặc token"}, status_code=400)
        
    decoded_token = verify_ema_token(token)
    if not decoded_token:
        return JSONResponse({"error": "Xác thực Token thất bại"}, status_code=403)
        
    user_id = decoded_token.get("sub")
    
    # Clerk thường lưu metadata trong trường 'public_metadata'. 
    # Ta cũng hỗ trợ đọc trực tiếp từ trường 'role' (Custom Claim) nếu có.
    # Mặc định (Default Fallback) là role 'customer' nếu người dùng chưa được gán.
    public_metadata = decoded_token.get("public_metadata", {})
    role = public_metadata.get("role") or decoded_token.get("role") or "customer"
    
    # Kiểm tra xem Role này có được phép vào MCP không
    role_record = ROLE_PERMISSIONS.get(role)
    if not role_record or "CRM MCP" not in role_record.get("allowed_mcps", []):
        return JSONResponse({"error": f"Tài khoản {user_id} (Role: {role}) bị cấm truy cập hệ thống MCP."}, status_code=403)
        
    # Lưu user_id và role vào phiên làm việc
    SESSIONS[session_id] = {"user_id": user_id, "role": role}
    print(f"✅ User {user_id} (Role: {role}) đã đăng nhập thành công cho phiên {session_id}")
    return JSONResponse({"message": "Xác thực thành công. Vui lòng đóng cửa sổ này."})

class MCPPathRewriteMiddleware:
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






app.mount("/", mcp_app)




if __name__ == "__main__":
    print("Khởi động MCP Server (FastAPI + FastMCP) tại http://localhost:8000 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
