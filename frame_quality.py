import os

from config import (
    FRAME_QUALITY_CHECK_ENABLED,
    FRAME_QUALITY_MAX_BRIGHTNESS,
    FRAME_QUALITY_MIN_BRIGHTNESS,
    FRAME_QUALITY_MIN_CONTRAST_STDDEV,
    FRAME_QUALITY_MIN_LAPLACIAN_VAR,
    FRAME_QUALITY_RESIZE_WIDTH,
)

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None


def _resize_for_speed(gray):
    """Downscale before metrics to keep CPU usage low on Pi Zero-class hardware."""
    if FRAME_QUALITY_RESIZE_WIDTH <= 0:
        return gray

    width = int(gray.shape[1])
    if width <= FRAME_QUALITY_RESIZE_WIDTH:
        return gray

    ratio = FRAME_QUALITY_RESIZE_WIDTH / float(width)
    height = max(1, int(gray.shape[0] * ratio))
    return cv2.resize(gray, (FRAME_QUALITY_RESIZE_WIDTH, height), interpolation=cv2.INTER_AREA)


def get_frame_quality_metrics(image_path):
    """Return brightness/contrast/sharpness metrics for an image path, or None if unreadable."""
    if not image_path or not os.path.exists(image_path):
        return None

    if cv2 is None:
        return None

    gray = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.size == 0:
        return None

    gray = _resize_for_speed(gray)

    mean, stddev = cv2.meanStdDev(gray)
    brightness = float(mean[0][0])
    contrast_stddev = float(stddev[0][0])
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    return {
        "brightness": brightness,
        "contrast_stddev": contrast_stddev,
        "laplacian_var": laplacian_var,
    }


def are_metrics_usable(metrics):
    """Evaluate whether computed metrics satisfy current configured thresholds."""
    if metrics is None:
        return False

    brightness = float(metrics["brightness"])
    contrast_stddev = float(metrics["contrast_stddev"])
    laplacian_var = float(metrics["laplacian_var"])

    if brightness < FRAME_QUALITY_MIN_BRIGHTNESS:
        return False
    if brightness > FRAME_QUALITY_MAX_BRIGHTNESS:
        return False
    if contrast_stddev < FRAME_QUALITY_MIN_CONTRAST_STDDEV:
        return False
    if laplacian_var < FRAME_QUALITY_MIN_LAPLACIAN_VAR:
        return False

    return True


def is_frame_usable(image_path):
    """Return True when frame passes basic brightness, contrast, and sharpness checks."""
    if not FRAME_QUALITY_CHECK_ENABLED:
        return True

    if not image_path or not os.path.exists(image_path):
        return False

    if cv2 is None:
        # Keep pipeline operational when OpenCV is unavailable.
        return True

    metrics = get_frame_quality_metrics(image_path)
    return are_metrics_usable(metrics)
