import cloudinary
import cloudinary.uploader
from config import CLOUD_NAME, API_KEY, API_SECRET
import logging

cloudinary.config(cloud_name=CLOUD_NAME,
                  api_key=API_KEY,
                  api_secret=API_SECRET)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upload_image(path):
    try:
        result = cloudinary.uploader.upload(path, folder="agos/")
        if "secure_url" not in result:
            logger.error(f"Upload result missing 'secure_url' key for {path}")
            return None
        return result["secure_url"]
    except (cloudinary.exceptions.Error, Exception) as e:
        logger.error(f"Failed to upload image {path}: {e}")
        return None
