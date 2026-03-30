from collections import deque
import math
import statistics


class WaterLevelFilter:
    """Robust filter for ultrasonic level telemetry.

    Processing stages:
      1) Physical plausibility range check.
      2) MAD-based modified Z-score outlier rejection.
      3) Moving-average smoothing on accepted samples.
    """

    def __init__(
        self,
        enabled,
        window_size,
        min_valid_samples,
        min_cm,
        max_cm,
        modz_threshold,
        zero_mad_tolerance_cm,
        rebaseline_outlier_streak,
    ):
        self.enabled = enabled
        self.window_size = max(3, int(window_size))
        self.min_valid_samples = max(1, int(min_valid_samples))
        self.min_cm = float(min_cm)
        self.max_cm = float(max_cm)
        self.modz_threshold = float(modz_threshold)
        self.zero_mad_tolerance_cm = float(zero_mad_tolerance_cm)
        self.rebaseline_outlier_streak = max(2, int(rebaseline_outlier_streak))
        self._history = deque(maxlen=self.window_size)
        self._outlier_streak = 0
        self._outlier_buffer = deque(maxlen=self.window_size)

    def _range_valid(self, value):
        return self.min_cm <= value <= self.max_cm

    def process(self, raw_value):
        if raw_value is None:
            return None, "no-reading"

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None, "non-numeric"

        if not math.isfinite(value):
            return None, "non-finite"

        if not self._range_valid(value):
            self._outlier_streak = 0
            self._outlier_buffer.clear()
            return None, "out-of-range"

        if not self.enabled:
            return value, "bypass"

        # Use accepted history to keep rejected spikes from polluting statistics.
        if len(self._history) >= self.min_valid_samples:
            median = statistics.median(self._history)
            abs_devs = [abs(x - median) for x in self._history]
            mad = statistics.median(abs_devs)

            if mad == 0:
                if abs(value - median) > self.zero_mad_tolerance_cm:
                    self._outlier_streak += 1
                    self._outlier_buffer.append(value)
                    if self._outlier_streak >= self.rebaseline_outlier_streak:
                        self._history.clear()
                        self._history.extend(self._outlier_buffer)
                        self._outlier_streak = 0
                        self._outlier_buffer.clear()
                        filtered = sum(self._history) / len(self._history)
                        return filtered, "rebaseline"
                    return None, "outlier-zero-mad"
            else:
                modified_z = 0.6745 * abs(value - median) / mad
                if modified_z > self.modz_threshold:
                    self._outlier_streak += 1
                    self._outlier_buffer.append(value)
                    if self._outlier_streak >= self.rebaseline_outlier_streak:
                        self._history.clear()
                        self._history.extend(self._outlier_buffer)
                        self._outlier_streak = 0
                        self._outlier_buffer.clear()
                        filtered = sum(self._history) / len(self._history)
                        return filtered, "rebaseline"
                    return None, "outlier-modz"

        self._outlier_streak = 0
        self._outlier_buffer.clear()
        self._history.append(value)
        filtered = sum(self._history) / len(self._history)
        return filtered, "ok"
