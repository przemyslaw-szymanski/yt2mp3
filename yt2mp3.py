#!/usr/bin/env python3
"""
yt2mp3.py  –  Download a YouTube video or playlist as MP3.

Requirements:
    pip install yt-dlp

FFmpeg must also be installed and on PATH (needed for audio extraction).
  Windows: winget install --id=Gyan.FFmpeg  OR  choco install ffmpeg
  Linux:   sudo apt install ffmpeg
  macOS:   brew install ffmpeg
"""

import argparse
import sys
import os


def BuildArgParser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download a YouTube video or playlist as MP3 file(s).",
    )
    p.add_argument("url", help="YouTube video or playlist URL.")
    p.add_argument(
        "-o", "--output",
        default=".",
        help="Output directory (created if it does not exist). Default: current directory.",
    )
    p.add_argument(
        "-q", "--quality",
        type=int,
        default=0,
        choices=range(0, 11),
        metavar="0-10",
        help="VBR quality passed to LAME: 0 = best, 10 = worst. Default: 0.",
    )
    p.add_argument(
        "--no-playlist",
        action="store_true",
        help="If a playlist URL is given, download only the single video in it.",
    )
    p.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        help="Extract cookies from BROWSER (e.g. chrome, firefox, edge) to handle age-gated "
             "or members-only content.",
    )
    p.add_argument(
        "--concurrent",
        type=int,
        default=1,
        metavar="N",
        help="Number of concurrent downloads (playlist only). Default: 1.",
    )
    p.add_argument(
        "--player-client",
        default="android,web",
        metavar="CLIENTS",
        help="Comma-separated yt-dlp player clients to try (e.g. android,ios,web,mweb). "
             "android bypasses most 403/bot-detection errors without needing cookies. Default: android,web.",
    )
    return p


def BuildYdlOptions(args: argparse.Namespace) -> dict:
    os.makedirs(args.output, exist_ok=True)

    # yt-dlp output template: artist – title when metadata is available, otherwise just title.
    outtmpl = os.path.join(
        args.output,
        "%(artist,uploader)s - %(title)s.%(ext)s",
    )

    # The android client is unauthenticated but returns real audio/video formats;
    # it bypasses the bot-detection 403 that the plain web client hits on many videos.
    player_clients = [c.strip() for c in args.player_client.split(",") if c.strip()]

    opts = {
        # Select the single best audio-only stream to avoid downloading video.
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": args.no_playlist,
        "concurrent_fragment_downloads": args.concurrent,
        # Retry on transient network errors.
        "retries": 5,
        "fragment_retries": 5,
        "sleep_interval_requests": 1,
        # Try multiple player clients in order; tv_embedded skips most 403s.
        "extractor_args": {"youtube": {"player_client": player_clients}},
        # Write thumbnail as cover art.
        "writethumbnail": True,
        "postprocessors": [
            {
                # Convert to MP3.
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(args.quality),
            },
            {
                # Embed thumbnail as cover art inside the MP3.
                "key": "EmbedThumbnail",
            },
            {
                # Write ID3 tags from video metadata.
                "key": "FFmpegMetadata",
                "add_metadata": True,
            },
        ],
    }

    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser,)

    return opts


def Main() -> int:
    try:
        import yt_dlp
    except ImportError:
        print("Error: yt-dlp is not installed. Run:  pip install yt-dlp", file=sys.stderr)
        return 1

    args = BuildArgParser().parse_args()
    opts = BuildYdlOptions(args)

    print(f"Downloading to: {os.path.abspath(args.output)}")
    with yt_dlp.YoutubeDL(opts) as ydl:
        ret = ydl.download([args.url])

    return ret


if __name__ == "__main__":
    sys.exit(Main())
