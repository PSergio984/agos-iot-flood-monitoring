import os
from dotenv import load_dotenv
load_dotenv()

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")
SERVER_URL = os.getenv("SERVER_URL")
SENSOR_DEVICE_ID = int(os.getenv("SENSOR_DEVICE_ID", "1"))
