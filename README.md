# Hướng dẫn tích hợp MCP với Claude Desktop

1. Lấy **User ID** của bạn trên Clerk (vào Clerk Dashboard -> Users -> Copy User ID có dạng `user_2...`).
2. Mở file `server.py`, tìm đoạn `MOCK_PERMISSION_DB` và thay chữ `user_1` bằng User ID thật của bạn. (Sau đó tắt server đang chạy và bật lại bằng lệnh `python server.py`).
3. Đăng nhập trên trang `http://localhost:3000/demo_login.html` và copy toàn bộ chuỗi Token.
4. Mở file cấu hình của Claude Desktop (bạn đang mở file `claude_desktop_config.json`), dán đoạn cấu hình sau vào:

```json
{
  "mcpServers": {
    "crm-mcp": {
      "command": "python",
      "args": ["-m", "fastmcp", "run", "/Users/nam/Desktop/MCP-EMA/server.py:mcp"],
      "env": {
        "EMA_TOKEN": "DÁN_CHUỖI_TOKEN_BẠN_VỪA_COPY_VÀO_ĐÂY"
      }
    }
  }
}
```

5. Khởi động lại ứng dụng Claude Desktop. Nhắn tin cho Claude: "Hãy lấy danh sách đơn hàng cho tôi" -> Claude sẽ tự động dùng quyền của bạn để truy cập dữ liệu một cách an toàn!
