class AddTrailingSlashMiddleware:
    def __init__(self, app):
        self.app = app
        
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # Nếu path là /mcp/messages (không có slash), thêm slash vào
            if path == "/mcp/messages":
                scope["path"] = "/mcp/messages/"
        return await self.app(scope, receive, send)
