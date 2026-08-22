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
import re
import sys
import os


def BuildArgParser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download a YouTube video or playlist as MP3 file(s).",
    )
    p.add_argument("url", help="YouTube video or playlist URL. "
                             "IMPORTANT: wrap in double quotes if the URL contains '&', e.g.: "
                             'python yt2mp3.py "https://youtube.com/watch?v=ID&list=PL..."')
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
    p.add_argument(
        "--no-archive",
        action="store_true",
        help="Disable the download archive and re-download already downloaded files.",
    )
    p.add_argument(
        "--archive-file",
        metavar="FILE",
        default=None,
        help="Path to the download archive file. "
             "Default: download-archive.txt inside the output directory.",
    )
    return p


def BuildYdlOptions(args: argparse.Namespace) -> dict:
    os.makedirs(args.output, exist_ok=True)

    # A playlist URL (query has "list=", or a "/playlist" path) gets its own subfolder named
    # after the playlist, so each playlist downloaded into the same --output stays separated.
    # Single-video URLs (or --no-playlist) keep the flat "<output>/artist - title.mp3" layout.
    is_playlist_url = not args.no_playlist and bool(
        re.search(r"[?&]list=", args.url) or "/playlist" in args.url
    )
    if is_playlist_url:
        outtmpl = os.path.join(
            args.output,
            "%(playlist_title,playlist_id,playlist)s",
            "%(playlist_index)s - %(artist,uploader)s - %(title)s.%(ext)s",
        )
    else:
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

    # Record every downloaded video ID so subsequent runs skip already-fetched files.
    # The archive file lives next to the MP3s by default so playlist re-runs are safe.
    if not args.no_archive:
        archive_file = args.archive_file or os.path.join(
            os.path.abspath(args.output), "download-archive.txt"
        )
        opts["download_archive"] = archive_file

    return opts


def Main() -> int:
    try:
        import yt_dlp
    except ImportError:
        print("Error: yt-dlp is not installed. Run:  pip install yt-dlp", file=sys.stderr)
        print("FFmpeg must also be installed and on PATH (needed for audio extraction): winget install --id=Gyan.FFmpeg.", file=sys.stderr)
        return 1

    args = BuildArgParser().parse_args()

    # Detect URLs that were split by the Windows CMD '&' command separator.
    # When a URL like "?v=ID&list=PL..." is passed without quotes in CMD, the shell
    # treats '&' as a command separator and Python only receives the truncated part
    # before the first '&'. The 'list=...' and 'index=...' tokens are executed as
    # separate (failing) shell commands and are never visible to this script.
    url = args.url
    if ("youtube.com" in url or "youtu.be" in url) and "&" not in url and "?" in url:
        print(
            "\nWarning: the URL looks truncated - '&list=...' or '&index=...' parameters are missing.\n"
            "On Windows CMD the '&' character splits the command line.\n"
            "Wrap the URL in double quotes and run again:\n"
            f'  python yt2mp3.py "{url}&list=PLAYLIST_ID"\n',
            file=sys.stderr,
        )

    opts = BuildYdlOptions(args)

    print(f"Downloading to: {os.path.abspath(args.output)}")
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ret = ydl.download([args.url])
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Private video" in msg or "Sign in" in msg:
            browser_hint = args.cookies_from_browser or "edge"
            print(
                "\nThis video is private. You need to be signed in to a YouTube account that "
                "has access to it.\n"
                "Pass your browser cookies so yt-dlp can authenticate:\n\n"
                f"  python yt2mp3.py \"<URL>\" --cookies-from-browser {browser_hint}\n\n"
                "Supported browsers: chrome, firefox, edge, opera, brave, chromium, safari\n"
                "Make sure you are already logged in to YouTube in that browser before running.",
                file=sys.stderr,
            )
        elif "Could not copy" in msg and "cookie database" in msg:
            print(
                "\nCould not read the browser's cookie database because the browser is running "
                "and has it locked.\n"
                f"Close all {args.cookies_from_browser} windows completely (check the system tray/"
                "Task Manager for background processes) and run the command again.\n"
                "Alternatively, use a different browser you are logged into YouTube with, e.g.:\n\n"
                "  python yt2mp3.py \"<URL>\" --cookies-from-browser firefox\n",
                file=sys.stderr,
            )
        return 1

    return ret


if __name__ == "__main__":
    sys.exit(Main())
