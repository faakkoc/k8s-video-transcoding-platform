"""
FFmpeg Transcoding Presets

Defines video encoding parameters for different quality levels.
Each preset balances quality, file size, and encoding speed.
"""

from typing import Dict, List


class FFmpegPreset:
    """
    FFmpeg preset configuration.

    Attributes:
        resolution: Output resolution (e.g., "1280x720")
        video_bitrate: Target video bitrate
        audio_bitrate: Target audio bitrate
        codec: Video codec (h264, h265, etc.)
        preset: Encoding speed preset (fast, medium, slow)
        profile: H.264 profile (baseline, main, high)
    """

    def __init__(
            self,
            resolution: str,
            video_bitrate: str,
            audio_bitrate: str = "128k",
            codec: str = "libx264",
            preset: str = "medium",
            profile: str = "high",
            fps: int = 30
    ):
        self.resolution = resolution
        self.video_bitrate = video_bitrate
        self.audio_bitrate = audio_bitrate
        self.codec = codec
        self.preset = preset
        self.profile = profile
        self.fps = fps

    def to_ffmpeg_args(self) -> List[str]:
        """
        Convert preset to FFmpeg command-line arguments.

        Returns:
            List of FFmpeg arguments
        """
        args = [
            # Video codec
            "-c:v", self.codec,

            # Video bitrate
            "-b:v", self.video_bitrate,

            # Resolution (scale filter)
            "-vf", f"scale={self.resolution}",

            # Frame rate
            "-r", str(self.fps),

            # Encoding preset (speed vs quality)
            "-preset", self.preset,

            # Profile (compatibility)
            "-profile:v", self.profile,

            # Audio codec
            "-c:a", "aac",

            # Audio bitrate
            "-b:a", self.audio_bitrate,

            # Move metadata to beginning (for web streaming)
            "-movflags", "+faststart",
        ]

        return args


# Preset definitions
PRESETS: Dict[str, FFmpegPreset] = {
    "480p": FFmpegPreset(
        resolution="854x480",
        video_bitrate="1000k",
        audio_bitrate="96k",
        preset="fast",
        profile="main",
        fps=30
    ),

    "720p": FFmpegPreset(
        resolution="1280x720",
        video_bitrate="2500k",
        audio_bitrate="128k",
        preset="medium",
        profile="high",
        fps=30
    ),

    "1080p": FFmpegPreset(
        resolution="1920x1080",
        video_bitrate="5000k",
        audio_bitrate="192k",
        preset="medium",
        profile="high",
        fps=30
    ),

    "4k": FFmpegPreset(
        resolution="3840x2160",
        video_bitrate="15000k",
        audio_bitrate="256k",
        preset="slow",
        profile="high",
        fps=30
    ),
}


def get_preset(preset_name: str) -> FFmpegPreset:
    """
    Get FFmpeg preset by name.

    Args:
        preset_name: Preset identifier (480p, 720p, 1080p, 4k)

    Returns:
        FFmpegPreset object

    Raises:
        ValueError: If preset not found
    """
    if preset_name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise ValueError(
            f"Unknown preset: {preset_name}. "
            f"Available presets: {available}"
        )

    return PRESETS[preset_name]


def get_available_presets() -> List[str]:
    """Get list of available preset names."""
    return list(PRESETS.keys())