"""
This module contains a container for stream manifest data.

A container object for the media stream (video only / audio only / video+audio
combined). This was referred to as ``Video`` in the legacy pytube version, but
has been renamed to accommodate DASH (which serves the audio and video
separately).
"""

import logging
from datetime import datetime
from math import ceil
from typing import Dict, Optional, Tuple
from urllib.error import HTTPError
from urllib.parse import parse_qs

from pytubefix import extract, request
from pytubefix.itags import get_format_profile
from pytubefix.monostate import Monostate
from pytubefix.streams import Stream

logger = logging.getLogger(__name__)


class EncryptedStream:
    """Container for stream manifest data."""

    def __init__(
        self, stream: Dict, monostate: Monostate, cipher, discovered_n
    ):
        """Construct a :class:`Stream <Stream>`.

        :param dict stream:
            The unscrambled data extracted from YouTube.
        :param dict monostate:
            Dictionary of data shared across all instances of
            :class:`Stream <Stream>`.
        """
        # A dictionary shared between all instances of :class:`Stream <Stream>`
        # (Borg pattern).
        self._monostate = monostate

        def decrypt():
            extract.apply_signature_single(stream, cipher, discovered_n)
            return Stream(stream, monostate)
        self.decrypt = decrypt

        self.encrypted_url = stream["url"]
        self.itag = int(
            stream["itag"]
        )  # stream format id (youtube nomenclature)

        # set type and codec info

        # 'video/webm; codecs="vp8, vorbis"' -> 'video/webm', ['vp8', 'vorbis']
        self.mime_type, self.codecs = extract.mime_type_codec(stream["mimeType"])

        # 'video/webm' -> 'video', 'webm'
        self.type, self.subtype = self.mime_type.split("/")

        # ['vp8', 'vorbis'] -> video_codec: vp8, audio_codec: vorbis. DASH
        # streams return NoneType for audio/video depending.
        self.video_codec, self.audio_codec = self.parse_codecs()

        self.is_otf: bool = stream["is_otf"]
        self.bitrate: Optional[int] = stream["bitrate"]

        # filesize in bytes
        self._filesize: Optional[int] = int(stream.get('contentLength', 0))
        
        # filesize in kilobytes
        self._filesize_kb: Optional[float] = float(ceil(float(stream.get('contentLength', 0)) / 1024 * 1000) / 1000)
        
        # filesize in megabytes
        self._filesize_mb: Optional[float] = float(ceil(float(stream.get('contentLength', 0)) / 1024 / 1024 * 1000) / 1000)
        
        # filesize in gigabytes(fingers crossed we don't need terabytes going forward though)
        self._filesize_gb: Optional[float] = float(ceil(float(stream.get('contentLength', 0)) / 1024 / 1024 / 1024 * 1000) / 1000)

        # Additional information about the stream format, such as resolution,
        # frame rate, and whether the stream is live (HLS) or 3D.
        itag_profile = get_format_profile(self.itag)
        self.is_dash = itag_profile["is_dash"]
        self.abr = itag_profile["abr"]  # average bitrate (audio streams only)
        if 'fps' in stream:
            self.fps = stream['fps']  # Video streams only
        self.resolution = itag_profile[
            "resolution"
        ]  # resolution (e.g.: "480p")

        self._width = stream["width"] if 'width' in stream else None
        self._height = stream["height"] if 'height' in stream else None

        self.is_3d = itag_profile["is_3d"]
        self.is_hdr = itag_profile["is_hdr"]
        self.is_live = itag_profile["is_live"]

        self.includes_multiple_audio_tracks: bool = 'audioTrack' in stream
        if self.includes_multiple_audio_tracks:
            self.is_default_audio_track = stream['audioTrack']['audioIsDefault']
            self.audio_track_name = str(stream['audioTrack']['displayName']).split(" ")[0]
        else:
            self.is_default_audio_track = self.includes_audio_track and not self.includes_video_track
            self.audio_track_name = None

    @property
    def is_adaptive(self) -> bool:
        """Whether the stream is DASH.

        :rtype: bool
        """
        # if codecs has two elements (e.g.: ['vp8', 'vorbis']): 2 % 2 = 0
        # if codecs has one element (e.g.: ['vp8']) 1 % 2 = 1
        return bool(len(self.codecs) % 2)

    @property
    def is_progressive(self) -> bool:
        """Whether the stream is progressive.

        :rtype: bool
        """
        return not self.is_adaptive

    @property
    def includes_audio_track(self) -> bool:
        """Whether the stream only contains audio.

        :rtype: bool
        """
        return self.is_progressive or self.type == "audio"

    @property
    def includes_video_track(self) -> bool:
        """Whether the stream only contains video.

        :rtype: bool
        """
        return self.is_progressive or self.type == "video"

    def parse_codecs(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the video/audio codecs from list of codecs.

        Parse a variable length sized list of codecs and returns a
        constant two element tuple, with the video codec as the first element
        and audio as the second. Returns None if one is not available
        (adaptive only).

        :rtype: tuple
        :returns:
            A two element tuple with audio and video codecs.

        """
        video = None
        audio = None
        if not self.is_adaptive:
            video, audio = self.codecs
        elif self.includes_video_track:
            video = self.codecs[0]
        elif self.includes_audio_track:
            audio = self.codecs[0]
        return video, audio

    @property
    def width(self) -> int:
        """Video width. Returns None if it does not have the value.

        :rtype: int
        :returns:
            Returns an int of the video width
        """
        return self._width

    @property
    def height(self) -> int:
        """Video height. Returns None if it does not have the value.

        :rtype: int
        :returns:
            Returns an int of the video height
        """
        return self._height

    @property
    def filesize(self) -> int:
        """File size of the media stream in bytes.

        :rtype: int
        :returns:
            Filesize (in bytes) of the stream.
        """
        if self._filesize == 0:
            try:
                self._filesize = request.filesize(self.url)
            except HTTPError as e:
                if e.code != 404:
                    raise
                self._filesize = request.seq_filesize(self.url)
        return self._filesize
    
    @property
    def filesize_kb(self) -> float:
        """File size of the media stream in kilobytes.

        :rtype: float
        :returns:
            Rounded filesize (in kilobytes) of the stream.
        """
        if self._filesize_kb == 0:
            try:
                self._filesize_kb = float(ceil(request.filesize(self.url)/1024 * 1000) / 1000)
            except HTTPError as e:
                if e.code != 404:
                    raise
                self._filesize_kb = float(ceil(request.seq_filesize(self.url)/1024 * 1000) / 1000)
        return self._filesize_kb
    
    @property
    def filesize_mb(self) -> float:
        """File size of the media stream in megabytes.

        :rtype: float
        :returns:
            Rounded filesize (in megabytes) of the stream.
        """
        if self._filesize_mb == 0:
            try:
                self._filesize_mb = float(ceil(request.filesize(self.url)/1024/1024 * 1000) / 1000)
            except HTTPError as e:
                if e.code != 404:
                    raise
                self._filesize_mb = float(ceil(request.seq_filesize(self.url)/1024/1024 * 1000) / 1000)
        return self._filesize_mb

    @property
    def filesize_gb(self) -> float:
        """File size of the media stream in gigabytes.

        :rtype: float
        :returns:
            Rounded filesize (in gigabytes) of the stream.
        """
        if self._filesize_gb == 0:
            try:
                self._filesize_gb = float(ceil(request.filesize(self.url)/1024/1024/1024 * 1000) / 1000)
            except HTTPError as e:
                if e.code != 404:
                    raise
                self._filesize_gb = float(ceil(request.seq_filesize(self.url)/1024/1024/1024 * 1000) / 1000)
        return self._filesize_gb
    
    @property
    def title(self,) -> str:
        """Get title of video

        :rtype: str
        :returns:
            Youtube video title
        """
        return self._monostate.title or "Unknown YouTube Video Title"

    @property
    def filesize_approx(self) -> int:
        """Get approximate filesize of the video

        Falls back to HTTP call if there is not sufficient information to approximate

        :rtype: int
        :returns: size of video in bytes
        """
        if self._monostate.duration and self.bitrate:
            bits_in_byte = 8
            return int(
                (self._monostate.duration * self.bitrate) / bits_in_byte
            )

        return self.filesize

    @property
    def expiration(self) -> datetime:
        expire = parse_qs(self.url.split("?")[1])["expire"][0]
        return datetime.utcfromtimestamp(int(expire))

    @property
    def default_filename(self) -> str:
        """Generate filename based on the video title.

        :rtype: str
        :returns:
            An os file system compatible filename.
        """
        if 'audio' in self.mime_type and 'video' not in self.mime_type:
            self.subtype = "m4a"

        return f"{self.title}.{self.subtype}"

    def __repr__(self) -> str:
        """Printable object representation.

        :rtype: str
        :returns:
            A string representation of a :class:`Stream <Stream>` object.
        """
        parts = ['itag="{s.itag}"', 'mime_type="{s.mime_type}"']
        if self.includes_video_track:
            parts.extend(['res="{s.resolution}"', 'fps="{s.fps}fps"'])
            if not self.is_adaptive:
                parts.extend(
                    ['vcodec="{s.video_codec}"', 'acodec="{s.audio_codec}"',]
                )
            else:
                parts.extend(['vcodec="{s.video_codec}"'])
        else:
            parts.extend(['abr="{s.abr}"', 'acodec="{s.audio_codec}"'])
        parts.extend(['progressive="{s.is_progressive}"', 'type="{s.type}"'])
        return f"<EncryptedStream: {' '.join(parts).format(s=self)}>"
