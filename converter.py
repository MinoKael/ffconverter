#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║             FFMPEG CONVERTER  —  powered by ffmpeg           ║
║         Interface de terminal interativa para conversão       ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import shutil
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ─────────────────────────────────────────────────────────────────
#  AUTO-INSTALL DE DEPENDÊNCIAS
# ─────────────────────────────────────────────────────────────────
def _ensure_deps() -> None:
    need = []
    for mod, pkg in [("rich", "rich>=13.0.0"), ("InquirerPy", "InquirerPy>=0.3.4")]:
        try:
            __import__(mod)
        except ImportError:
            need.append(pkg)
    if need:
        print(f"\n  [*] Instalando dependencias: {', '.join(need)} ...", flush=True)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + need + ["--quiet"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + need)
        print("  [OK] Dependencias instaladas!\n", flush=True)

_ensure_deps()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.align import Align
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    TimeElapsedColumn, TaskProgressColumn,
)
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich import box
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator

console = Console(highlight=False)

# ─────────────────────────────────────────────────────────────────
#  MAPEAMENTO DE EXTENSÕES
# ─────────────────────────────────────────────────────────────────
VIDEO_EXTS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
    ".m4v", ".mpg", ".mpeg", ".3gp", ".ts", ".vob", ".f4v",
    ".rm", ".rmvb", ".divx", ".ogv",
}
AUDIO_EXTS = {
    ".mp3", ".aac", ".m4a", ".flac", ".wav", ".ogg", ".opus",
    ".wma", ".aiff", ".aif", ".alac", ".mp2", ".ac3", ".mka",
}
IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".tiff", ".tif", ".avif", ".heic", ".heif",
}

# ─────────────────────────────────────────────────────────────────
#  PRESETS DE CONVERSÃO
# ─────────────────────────────────────────────────────────────────
VIDEO_PRESETS: Dict[str, Dict] = {
    "mp4_h264": {
        "label": "MP4 (H.264)  — compatibilidade maxima",
        "ext": "mp4", "emoji": "🎬",
        "args": [
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        ],
    },
    "mp4_h265": {
        "label": "MP4 (H.265 / HEVC) — melhor compressao",
        "ext": "mp4", "emoji": "📦",
        "args": [
            "-c:v", "libx265", "-crf", "28", "-preset", "medium",
            "-c:a", "aac", "-b:a", "128k", "-tag:v", "hvc1",
        ],
    },
    "webm": {
        "label": "WebM (VP9) — para web",
        "ext": "webm", "emoji": "🌐",
        "args": ["-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
                 "-c:a", "libopus", "-b:a", "96k"],
    },
    "mkv": {
        "label": "MKV — copia sem re-encode (rapido)",
        "ext": "mkv", "emoji": "🗃️",
        "args": ["-c", "copy"],
    },
    "mov": {
        "label": "MOV — Apple / Final Cut Pro",
        "ext": "mov", "emoji": "🍎",
        "args": ["-c:v", "copy", "-c:a", "copy"],
    },
    "avi": {
        "label": "AVI — legado / compatibilidade antiga",
        "ext": "avi", "emoji": "📼",
        "args": ["-c:v", "mpeg4", "-q:v", "6", "-c:a", "mp3", "-b:a", "128k"],
    },
    "gif": {
        "label": "GIF — animacao (480px, 12 fps)",
        "ext": "gif", "emoji": "🎭",
        "args": [
            "-vf",
            "fps=12,scale=480:-1:flags=lanczos,"
            "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
        ],
    },
}

EXTRACT_PRESETS: Dict[str, Dict] = {
    "mp3_ex": {
        "label": "MP3 — extrair audio (192 kbps)",
        "ext": "mp3", "emoji": "🎵",
        "args": ["-vn", "-c:a", "libmp3lame", "-b:a", "192k"],
    },
    "aac_ex": {
        "label": "AAC / M4A — extrair audio",
        "ext": "m4a", "emoji": "🎶",
        "args": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    },
    "flac_ex": {
        "label": "FLAC — extrair audio sem perdas",
        "ext": "flac", "emoji": "💎",
        "args": ["-vn", "-c:a", "flac"],
    },
    "wav_ex": {
        "label": "WAV — extrair audio sem compressao",
        "ext": "wav", "emoji": "〰️",
        "args": ["-vn", "-c:a", "pcm_s16le"],
    },
    "opus_ex": {
        "label": "OPUS — extrair audio (menor / alta qualidade)",
        "ext": "opus", "emoji": "✨",
        "args": ["-vn", "-c:a", "libopus", "-b:a", "128k"],
    },
}

AUDIO_PRESETS: Dict[str, Dict] = {
    "mp3": {
        "label": "MP3 — universal (192 kbps)",
        "ext": "mp3", "emoji": "🎵",
        "args": ["-c:a", "libmp3lame", "-b:a", "192k"],
    },
    "aac": {
        "label": "AAC / M4A — alta qualidade",
        "ext": "m4a", "emoji": "🎧",
        "args": ["-c:a", "aac", "-b:a", "192k"],
    },
    "flac": {
        "label": "FLAC — sem perdas",
        "ext": "flac", "emoji": "💎",
        "args": ["-c:a", "flac"],
    },
    "wav": {
        "label": "WAV — sem compressao / PCM",
        "ext": "wav", "emoji": "〰️",
        "args": ["-c:a", "pcm_s16le"],
    },
    "ogg": {
        "label": "OGG Vorbis — open source",
        "ext": "ogg", "emoji": "🔊",
        "args": ["-c:a", "libvorbis", "-q:a", "5"],
    },
    "opus": {
        "label": "OPUS — melhor qualidade/tamanho",
        "ext": "opus", "emoji": "✨",
        "args": ["-c:a", "libopus", "-b:a", "128k"],
    },
}

IMAGE_PRESETS: Dict[str, Dict] = {
    "jpg": {
        "label": "JPEG — compatibilidade maxima",
        "ext": "jpg", "emoji": "📸",
        "args": ["-q:v", "2"],
    },
    "png": {
        "label": "PNG — sem perdas + transparencia",
        "ext": "png", "emoji": "🖼️",
        "args": [],
    },
    "webp": {
        "label": "WebP — moderno e eficiente",
        "ext": "webp", "emoji": "🌐",
        "args": ["-quality", "85"],
    },
    "bmp": {
        "label": "BMP — bitmap sem compressao",
        "ext": "bmp", "emoji": "🎨",
        "args": [],
    },
    "avif": {
        "label": "AVIF — proxima geracao",
        "ext": "avif", "emoji": "🚀",
        "args": [],
    },
}

ALL_PRESETS = {**VIDEO_PRESETS, **EXTRACT_PRESETS, **AUDIO_PRESETS, **IMAGE_PRESETS}

# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────
def get_file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:  return "video"
    if ext in AUDIO_EXTS:  return "audio"
    if ext in IMAGE_EXTS:  return "image"
    return "unknown"


def format_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_duration(seconds: float) -> str:
    if not seconds:
        return "N/A"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def probe_file(path: Path) -> dict:
    info: dict = {
        "size": path.stat().st_size,
        "streams": [], "duration": 0.0, "format_name": "",
    }
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", str(path)],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            fmt = data.get("format", {})
            info["duration"]    = float(fmt.get("duration", 0) or 0)
            info["format_name"] = fmt.get("format_long_name", "")
            info["streams"]     = data.get("streams", [])
    except Exception:
        pass
    return info


def build_output_path(input_path: Path, ext: str) -> Path:
    stem   = input_path.stem
    parent = input_path.parent
    # Same extension → use _converted suffix
    base = (
        parent / f"{stem}_converted.{ext}"
        if input_path.suffix.lower() == f".{ext}"
        else parent / f"{stem}.{ext}"
    )
    if not base.exists():
        return base
    # Avoid overwriting existing files
    for i in range(1, 10000):
        cand = parent / f"{stem}_converted_{i}.{ext}"
        if not cand.exists():
            return cand
    return base


# ─────────────────────────────────────────────────────────────────
#  UI — BANNER
# ─────────────────────────────────────────────────────────────────
def print_banner() -> None:
    title = Text()
    title.append(
        "  ███████╗███████╗███╗   ███╗██████╗ ███████╗ ██████╗\n",
        "bold bright_blue",
    )
    title.append(
        "  ██╔════╝██╔════╝████╗ ████║██╔══██╗██╔════╝██╔════╝\n",
        "bold #5599ff",
    )
    title.append(
        "  █████╗  █████╗  ██╔████╔██║██████╔╝█████╗  ██║  ███╗\n",
        "bold bright_cyan",
    )
    title.append(
        "  ██╔══╝  ██╔══╝  ██║╚██╔╝██║██╔═══╝ ██╔══╝  ██║   ██║\n",
        "bold #5599ff",
    )
    title.append(
        "  ██║     ██║     ██║ ╚═╝ ██║██║     ███████╗╚██████╔╝\n",
        "bold bright_blue",
    )
    title.append(
        "  ╚═╝     ╚═╝     ╚═╝     ╚═╝╚═╝     ╚══════╝ ╚═════╝ \n",
        "dim",
    )
    title.append("\n  C O N V E R T E R  —  powered by ffmpeg  ", "bold white")

    console.print()
    console.print(
        Panel(
            Align.center(title),
            box=box.DOUBLE,
            border_style="bright_blue",
            padding=(1, 6),
        )
    )
    console.print()


# ─────────────────────────────────────────────────────────────────
#  UI — FILE INFO
# ─────────────────────────────────────────────────────────────────
def print_file_info(path: Path, file_type: str, info: dict) -> None:
    icons = {"video": "🎬", "audio": "🎵", "image": "🖼️", "unknown": "📄"}
    icon  = icons.get(file_type, "📄")

    tbl = Table(box=None, show_header=False, padding=(0, 1), expand=False)
    tbl.add_column("k", style="dim", no_wrap=True, min_width=12)
    tbl.add_column("v", style="bright_white")

    tbl.add_row("Arquivo:", f"[bold cyan]{path.name}[/bold cyan]")
    tbl.add_row("Pasta:",   f"[dim]{path.parent}[/dim]")
    tbl.add_row("Tipo:",    f"{icon} [bold]{file_type.upper()}[/bold]")
    tbl.add_row("Tamanho:", format_size(info["size"]))
    if info["duration"]:
        tbl.add_row("Duracao:", format_duration(info["duration"]))
    if info["format_name"]:
        tbl.add_row("Container:", info["format_name"])

    for s in info["streams"]:
        ct = s.get("codec_type", "")
        if ct == "video":
            w, h   = s.get("width", "?"), s.get("height", "?")
            codec  = s.get("codec_name", "?").upper()
            fps_r  = s.get("r_frame_rate", "0/1")
            try:
                n, d = fps_r.split("/")
                fps_str = f" @ {int(int(n)/int(d))} FPS" if int(d) else ""
            except Exception:
                fps_str = ""
            tbl.add_row("Video:", f"[green]{codec}[/green]  {w}x{h}{fps_str}")
        elif ct == "audio":
            codec = s.get("codec_name", "?").upper()
            sr    = s.get("sample_rate", "")
            ch    = s.get("channels", 0)
            ch_s  = {1: "Mono", 2: "Estereo"}.get(ch, f"{ch}ch") if ch else ""
            tbl.add_row("Audio:", f"[green]{codec}[/green]  {sr}Hz  {ch_s}")

    console.print(
        Panel(
            tbl,
            title=f"  {icon} [bold]Arquivo de Entrada[/bold]  ",
            border_style="bright_blue",
            padding=(0, 2),
        )
    )


# ─────────────────────────────────────────────────────────────────
#  UI — SELEÇÃO DE FORMATOS
# ─────────────────────────────────────────────────────────────────
def select_formats(file_type: str) -> List[Tuple[str, Dict]]:
    choices: list = []

    if file_type == "video":
        choices.append(Separator("  ── 🎬  Formato de Vídeo ─────────────────────────────────"))
        for k, p in VIDEO_PRESETS.items():
            choices.append(Choice(k, name=f"  {p['emoji']}  {p['label']}"))
        choices.append(Separator("  ── 🎵  Extrair Áudio ────────────────────────────────────"))
        for k, p in EXTRACT_PRESETS.items():
            choices.append(Choice(k, name=f"  {p['emoji']}  {p['label']}"))

    elif file_type == "audio":
        choices.append(Separator("  ── 🎵  Formato de Áudio ─────────────────────────────────"))
        for k, p in AUDIO_PRESETS.items():
            choices.append(Choice(k, name=f"  {p['emoji']}  {p['label']}"))

    elif file_type == "image":
        choices.append(Separator("  ── 🖼️   Formato de Imagem ───────────────────────────────"))
        for k, p in IMAGE_PRESETS.items():
            choices.append(Choice(k, name=f"  {p['emoji']}  {p['label']}"))

    console.print()
    console.rule("[bold bright_blue]Selecione os formatos de destino[/bold bright_blue]")
    console.print("  [dim]Espaco = selecionar/desselecionar  |  Setas = navegar  |  Enter = confirmar[/dim]\n")

    selected_keys = inquirer.checkbox(
        message="Converter para:",
        choices=choices,
        validate=lambda x: bool(x),
        invalid_message="  Selecione pelo menos um formato.",
        transformer=lambda x: f"{len(x)} formato(s) selecionado(s)",
        cycle=True,
        qmark="🎯",
        amark="✅",
    ).execute()

    results = []
    for k in selected_keys:
        if k in ALL_PRESETS:
            results.append((k, ALL_PRESETS[k]))
    return results


# ─────────────────────────────────────────────────────────────────
#  UI — PARAMETROS EXTRAS
# ─────────────────────────────────────────────────────────────────
def ask_extra_params(file_type: str) -> List[str]:
    console.print()
    console.rule("[bold bright_blue]Parâmetros adicionais[/bold bright_blue]")

    want = inquirer.confirm(
        message="Configurar parametros adicionais? (resolucao, FPS, bitrate, recorte...)",
        default=False,
        qmark="⚙️",
    ).execute()

    if not want:
        console.print("  [dim]Usando configuracoes padrao dos presets.[/dim]")
        return []

    extra: List[str] = []

    # ── Vídeo: resolução
    if file_type == "video":
        scale = inquirer.select(
            message="📐 Redimensionar:",
            choices=[
                Choice("",              name="   [padrao] Manter resolucao original"),
                Choice("scale=3840:2160", name="   4K   —  3840x2160"),
                Choice("scale=1920:1080", name="   Full HD  —  1920x1080"),
                Choice("scale=1280:720",  name="   HD   —  1280x720"),
                Choice("scale=854:480",   name="   480p  —  854x480"),
                Choice("scale=640:360",   name="   360p  —  640x360"),
                Choice("__custom__",      name="   Personalizado..."),
            ],
            default="",
            qmark="📐",
        ).execute()
        if scale == "__custom__":
            scale = Prompt.ask(
                "  Filtro de escala ffmpeg (ex: scale=800:-1)",
                default=""
            ).strip()
        if scale:
            extra += ["-vf", scale]

        # FPS
        fps = inquirer.select(
            message="🎞️  FPS (frames por segundo):",
            choices=[
                Choice("",   name="   [padrao] Manter FPS original"),
                Choice("60", name="   60 FPS"),
                Choice("30", name="   30 FPS"),
                Choice("24", name="   24 FPS  (cinema)"),
                Choice("15", name="   15 FPS"),
                Choice("12", name="   12 FPS"),
            ],
            default="",
            qmark="🎞️",
        ).execute()
        if fps:
            extra += ["-r", fps]

    # ── Áudio: bitrate
    if file_type in ("video", "audio"):
        ab = inquirer.select(
            message="🔊 Bitrate de audio:",
            choices=[
                Choice("",     name="   [padrao] Bitrate do preset"),
                Choice("320k", name="   320 kbps  (maxima qualidade)"),
                Choice("192k", name="   192 kbps  (alta qualidade)"),
                Choice("128k", name="   128 kbps  (padrao)"),
                Choice("96k",  name="   96 kbps"),
                Choice("64k",  name="   64 kbps  (minimo)"),
            ],
            default="",
            qmark="🔊",
        ).execute()
        if ab:
            extra += ["-b:a", ab]

        # Volume
        vol = inquirer.select(
            message="🔉 Ajustar volume:",
            choices=[
                Choice("",     name="   [padrao] Volume original"),
                Choice("2.0",  name="   2x (dobrar)"),
                Choice("1.5",  name="   1.5x"),
                Choice("0.75", name="   0.75x"),
                Choice("0.5",  name="   0.5x (reduzir pela metade)"),
            ],
            default="",
            qmark="🔉",
        ).execute()
        if vol:
            extra += ["-af", f"volume={vol}"]

        # Trim
        trim = inquirer.select(
            message="✂️  Recortar trecho:",
            choices=[
                Choice("no",  name="   Sem recorte"),
                Choice("yes", name="   Definir inicio e fim..."),
            ],
            default="no",
            qmark="✂️",
        ).execute()
        if trim == "yes":
            start = Prompt.ask("  Inicio  (ex: 00:01:30 ou 90)", default="00:00:00")
            end   = Prompt.ask("  Fim     (ex: 00:02:00, vazio = ate o final)", default="")
            extra += ["-ss", start]
            if end.strip():
                extra += ["-to", end.strip()]

    # ── Parâmetros brutos
    add_raw = inquirer.confirm(
        message="🛠️  Adicionar parametros brutos do ffmpeg?",
        default=False,
        qmark="🛠️",
    ).execute()
    if add_raw:
        console.print("  [dim]Exemplo: -crf 18 -preset slow -tune film[/dim]")
        raw = Prompt.ask("  Parametros ffmpeg").strip()
        if raw:
            extra += raw.split()

    return extra


# ─────────────────────────────────────────────────────────────────
#  BUILD COMMANDS
# ─────────────────────────────────────────────────────────────────
def build_commands(
    input_path: Path,
    formats: List[Tuple[str, Dict]],
    extra: List[str],
) -> List[Tuple[Path, List[str]]]:
    cmds = []
    for _, preset in formats:
        out = build_output_path(input_path, preset["ext"])
        cmd = ["ffmpeg", "-hide_banner", "-y", "-i", str(input_path)]
        cmd += preset["args"]
        cmd += extra
        cmd.append(str(out))
        cmds.append((out, cmd))
    return cmds


# ─────────────────────────────────────────────────────────────────
#  UI — PREVIEW DOS COMANDOS
# ─────────────────────────────────────────────────────────────────
def preview_commands(commands: List[Tuple[Path, List[str]]]) -> None:
    console.print()
    console.rule("[bold bright_blue]Comandos que serao executados[/bold bright_blue]")
    for out, cmd in commands:
        console.print(f"\n  [dim]Saida →[/dim] [bold cyan]{out.name}[/bold cyan]")
        if sys.platform == "win32":
            cmd_str = subprocess.list2cmdline(cmd)
        else:
            cmd_str = " ".join(
                f'"{c}"' if " " in c and not c.startswith('"') else c for c in cmd
            )
        console.print(
            Syntax(cmd_str, "bash", theme="monokai", word_wrap=True, padding=1)
        )


# ─────────────────────────────────────────────────────────────────
#  CONVERSÃO COM BARRA DE PROGRESSO
# ─────────────────────────────────────────────────────────────────
def run_one_conversion(
    output: Path,
    cmd: List[str],
    duration: float,
) -> Tuple[bool, str]:
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        return False, "ffmpeg nao encontrado. Verifique a instalacao."
    except Exception as e:
        return False, str(e)

    is_image = (duration == 0)

    with Progress(
        SpinnerColumn(style="bright_cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=38, style="bright_blue", complete_style="bright_cyan"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task(
            f"  Convertendo [bold]{output.name}[/bold]...",
            total=None if is_image else 100,
        )

        last_err_lines: List[str] = []
        for line in proc.stderr:
            last_err_lines.append(line)
            if len(last_err_lines) > 20:
                last_err_lines.pop(0)
            if duration and "time=" in line:
                m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
                if m:
                    t = (float(m.group(1)) * 3600
                         + float(m.group(2)) * 60
                         + float(m.group(3)))
                    prog.update(task, completed=min(99.0, (t / duration) * 100))

        proc.wait()
        prog.update(task, completed=100)

    if proc.returncode == 0 and output.exists() and output.stat().st_size > 0:
        return True, ""
    # Grab last error line
    err = ""
    for ln in reversed(last_err_lines):
        ln = ln.strip()
        if ln and not ln.startswith("frame="):
            err = ln[:80]
            break
    return False, err or f"Codigo de saida {proc.returncode}"


# ─────────────────────────────────────────────────────────────────
#  UI — RESUMO
# ─────────────────────────────────────────────────────────────────
def print_summary(
    results: List[Tuple[str, Path, str]],
    input_path: Path,
    elapsed: float,
) -> None:
    console.print()
    console.rule("[bold bright_blue]Resumo[/bold bright_blue]")
    console.print()

    tbl = Table(
        box=box.ROUNDED,
        border_style="bright_blue",
        show_header=True,
        header_style="bold bright_white",
        padding=(0, 1),
    )
    tbl.add_column("",         justify="center", width=4)
    tbl.add_column("Arquivo",  style="bright_white")
    tbl.add_column("Tamanho",  justify="right",  width=11, style="cyan")
    tbl.add_column("Detalhe",  style="dim",      width=30)

    ok = 0
    for status, path, msg in results:
        if status == "ok":
            ok += 1
            sz = format_size(path.stat().st_size) if path.exists() else "—"
            tbl.add_row("✅", path.name, sz, "")
        else:
            tbl.add_row("❌", path.name, "—", msg[:30] if msg else "")

    console.print(tbl)
    console.print()
    if ok == len(results):
        console.print(
            f"  [bold green]🎉  {ok} arquivo(s) convertido(s) com sucesso! "
            f"({elapsed:.1f}s)[/bold green]"
        )
    else:
        console.print(
            f"  [bold yellow]⚠️   {ok}/{len(results)} conversoes bem-sucedidas "
            f"({elapsed:.1f}s)[/bold yellow]"
        )
    console.print(f"  [dim]Pasta de saida: {input_path.parent}[/dim]\n")


# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────
def main() -> None:
    if sys.platform == "win32":
        os.system("title FFmpeg Converter")
        # Enable UTF-8 on Windows
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # type: ignore
        except Exception:
            pass

    print_banner()

    # ── Verificar ffmpeg ────────────────────────────────────────
    if not shutil.which("ffmpeg"):
        console.print(
            Panel(
                "[bold red]❌  ffmpeg nao encontrado no PATH![/bold red]\n\n"
                "[white]Instale com um dos comandos:[/white]\n\n"
                "  [bold cyan]winget install FFmpeg[/bold cyan]"
                "  [dim](Windows 11+)[/dim]\n"
                "  [bold cyan]choco install ffmpeg[/bold cyan]"
                "  [dim](Chocolatey)[/dim]\n"
                "  [bold cyan]scoop install ffmpeg[/bold cyan]"
                "  [dim](Scoop)[/dim]\n\n"
                "[dim]Ou baixe em: [link]https://ffmpeg.org/download.html[/link][/dim]\n"
                "[dim]Apos instalar, [bold]reinicie o terminal[/bold].[/dim]",
                title="  ⚠️  Requisito nao encontrado  ",
                border_style="red",
                padding=(1, 2),
            )
        )
        input("\n  Pressione ENTER para fechar...")
        sys.exit(1)

    # ── Obter caminho do arquivo ────────────────────────────────
    file_path: Optional[Path] = None

    if len(sys.argv) > 1:
        raw = " ".join(sys.argv[1:]).strip().strip('"').strip("'")
        p   = Path(raw)
        if p.exists() and p.is_file():
            file_path = p
        else:
            console.print(f"\n  [red]Arquivo nao encontrado:[/red] {raw}\n")

    if file_path is None:
        console.print(
            "  [dim]Dica: arraste o arquivo para esta janela ou "
            "cole o caminho completo abaixo.[/dim]\n"
        )
        while True:
            raw = Prompt.ask("  📂  Caminho do arquivo").strip().strip('"').strip("'")
            p   = Path(raw)
            if p.exists() and p.is_file():
                file_path = p
                break
            console.print(f"  [red]Arquivo nao encontrado:[/red] {raw}")

    # ── Detectar tipo ───────────────────────────────────────────
    file_type = get_file_type(file_path)

    if file_type == "unknown":
        console.print(
            f"\n  [yellow]⚠️  Extensao desconhecida:[/yellow] {file_path.suffix}"
        )
        file_type = inquirer.select(
            message="Tratar arquivo como:",
            choices=[
                Choice("video", name="🎬 Video"),
                Choice("audio", name="🎵 Audio"),
                Choice("image", name="🖼️  Imagem"),
            ],
            qmark="❓",
        ).execute()

    # ── Informacoes do arquivo ──────────────────────────────────
    console.print("\n  [dim]Analisando arquivo...[/dim]")
    info = probe_file(file_path)
    print_file_info(file_path, file_type, info)

    # ── Selecao de formatos ─────────────────────────────────────
    try:
        formats = select_formats(file_type)
    except (KeyboardInterrupt, EOFError):
        console.print("\n  [yellow]Cancelado.[/yellow]")
        sys.exit(0)

    if not formats:
        console.print("  [yellow]Nenhum formato selecionado.[/yellow]")
        sys.exit(0)

    # ── Parametros extras ───────────────────────────────────────
    try:
        extra = ask_extra_params(file_type)
    except (KeyboardInterrupt, EOFError):
        extra = []
        console.print("\n  [dim]Parametros extras ignorados.[/dim]")

    # ── Montar comandos ─────────────────────────────────────────
    commands = build_commands(file_path, formats, extra)

    # ── Preview ─────────────────────────────────────────────────
    preview_commands(commands)

    # ── Confirmacao ─────────────────────────────────────────────
    console.print()
    try:
        go = inquirer.confirm(
            message=f"Iniciar {len(commands)} conversao(oes)?",
            default=True,
            qmark="🚀",
        ).execute()
    except (KeyboardInterrupt, EOFError):
        go = False

    if not go:
        console.print("  [yellow]Cancelado.[/yellow]")
        sys.exit(0)

    # ── Conversao ───────────────────────────────────────────────
    console.print()
    console.rule("[bold bright_blue]Convertendo[/bold bright_blue]")

    results = []
    t0 = time.time()

    for i, (out, cmd) in enumerate(commands, 1):
        console.print(f"\n  [bold]({i}/{len(commands)}) Gerando {out.name}[/bold]")
        ok, msg = run_one_conversion(out, cmd, info["duration"])
        if ok:
            sz = format_size(out.stat().st_size)
            console.print(f"  [green]✅  Concluido!  ({sz})[/green]")
            results.append(("ok", out, ""))
        else:
            console.print(f"  [red]❌  Falha: {msg}[/red]")
            results.append(("error", out, msg))

    elapsed = time.time() - t0

    # ── Resumo ──────────────────────────────────────────────────
    print_summary(results, file_path, elapsed)

    # ── Abrir pasta ─────────────────────────────────────────────
    try:
        open_dir = inquirer.confirm(
            message="Abrir pasta de destino no Explorer?",
            default=True,
            qmark="📂",
        ).execute()
        if open_dir:
            if sys.platform == "win32":
                os.startfile(str(file_path.parent))
            else:
                subprocess.Popen(["xdg-open", str(file_path.parent)])
    except Exception:
        pass

    console.print()
    input("  Pressione ENTER para fechar...")


if __name__ == "__main__":
    main()
