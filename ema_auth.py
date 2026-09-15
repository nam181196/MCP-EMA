import os
import logging
# pyrefly: ignore [missing-import]
import jwt
import datetime

logger = logging.getLogger(__name__)

# Đọc cấu hình từ biến môi trường (hoặc file .env)
# Sử dụng một SECRET_KEY tĩnh để ký (sign) JWT
EMA_SECRET_KEY = os.getenv("EMA_SECRET_KEY", "super-secret-key-for-local-oauth-12345")

def generate_ema_token(user_id: str) -> str:
    """
    Hàm sinh token JWT nội bộ (OAuth cục bộ).
    """
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2) # Hết hạn sau 2 giờ
    }
    token = jwt.encode(payload, EMA_SECRET_KEY, algorithm="HS256")
    return token

def verify_ema_token(token: str) -> bool:
    """
    Hàm xác thực token JWT nội bộ bằng SECRET_KEY.
    """
    if not token:
        logger.warning("Không có token EMA được cung cấp.")
        return False
        
    try:
        # Giải mã và xác minh chữ ký JWT
        decoded_token = jwt.decode(
            token,
            EMA_SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": True} # Luôn kiểm tra hạn sử dụng
        )
        
        # Tới bước này, token hợp lệ
        user_id = decoded_token.get("sub")
        logger.info(f"Xác thực nội bộ thành công cho user: {user_id}")
        return True
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token EMA đã hết hạn (Expired).")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token EMA không hợp lệ: {str(e)}")
    except Exception as e:
        logger.error(f"Lỗi không xác định khi verify EMA token: {str(e)}")
        
    return False
