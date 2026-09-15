import os
import logging
import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Đọc cấu hình từ biến môi trường (hoặc file .env)
# Ví dụ về JWKS URL của Keycloak: https://<domain>/auth/realms/<realm>/protocol/openid-connect/certs
EMA_JWKS_URL = os.getenv("EMA_JWKS_URL", "")
EMA_OIDC_AUDIENCE = os.getenv("EMA_OIDC_AUDIENCE", "")
EMA_OIDC_ISSUER = os.getenv("EMA_OIDC_ISSUER", "")

# Khởi tạo client để lấy public keys từ IdP
jwks_client = PyJWKClient(EMA_JWKS_URL) if EMA_JWKS_URL else None

def verify_ema_token(token: str) -> bool:
    """
    Hàm xác thực token JWT thực tế thông qua Identity Provider (IdP) sử dụng JWKS.
    """
    if not token:
        logger.warning("Không có token EMA được cung cấp.")
        return False
        
    if not jwks_client:
        logger.error("Chưa cấu hình EMA_JWKS_URL trong môi trường. Vui lòng thiết lập .env")
        # Rơi vào chế độ fallback hoặc từ chối toàn bộ
        return False

    try:
        # 1. Lấy public key từ JWKS URL tương ứng với 'kid' trong Header của JWT
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # 2. Xác thực và giải mã Token
        # Bắt buộc phải khớp thuật toán (ví dụ: RS256), audience và issuer
        decoded_token = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=EMA_OIDC_AUDIENCE if EMA_OIDC_AUDIENCE else None,
            issuer=EMA_OIDC_ISSUER if EMA_OIDC_ISSUER else None,
            options={
                "verify_aud": bool(EMA_OIDC_AUDIENCE),
                "verify_iss": bool(EMA_OIDC_ISSUER),
                "verify_exp": True, # Luôn kiểm tra hạn sử dụng
            }
        )
        
        # Tới bước này, token hợp lệ 100%
        user_id = decoded_token.get("sub")
        logger.info(f"Xác thực EMA thành công cho user: {user_id}")
        return True
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token EMA đã hết hạn (Expired).")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token EMA không hợp lệ: {str(e)}")
    except Exception as e:
        logger.error(f"Lỗi không xác định khi verify EMA token: {str(e)}")
        
    return False
