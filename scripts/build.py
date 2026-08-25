import os
import sys
import time
import shutil
import struct
import io
import subprocess
from pathlib import Path
from PIL import Image

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def generate_windows_ico(png_path: Path, ico_path: Path):
    """Generates standard Windows multi-resolution icon with DIB for <=64 and PNG for >=128."""
    if not png_path.exists():
        return
    src = Image.open(png_path).convert("RGBA")
    sizes = [16, 24, 32, 48, 64, 256]
    entries = []
    image_datas = []
    offset = 6 + len(sizes) * 16

    for s in sizes:
        resized = src.resize((s, s), Image.Resampling.LANCZOS)
        if s == 256:
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            data = buf.getvalue()
            bWidth = 0
            bHeight = 0
        else:
            biSize = 40
            biWidth = s
            biHeight = s * 2
            biPlanes = 1
            biBitCount = 32
            biCompression = 0
            biSizeImage = s * s * 4
            header = struct.pack("<IIIHHIIIIII", biSize, biWidth, biHeight, biPlanes, biBitCount, biCompression, biSizeImage, 0, 0, 0, 0)
            pixels = bytearray()
            for y in reversed(range(s)):
                for x in range(s):
                    r, g, b, a = resized.getpixel((x, y))
                    pixels.extend([b, g, r, a])
            mask_row_bytes = ((s + 31) // 32) * 4
            mask = bytearray(mask_row_bytes * s)
            data = header + bytes(pixels) + bytes(mask)
            bWidth = s
            bHeight = s

        entry = struct.pack("<BBBBHHII", bWidth, bHeight, 0, 0, 1, 32, len(data), offset)
        entries.append(entry)
        image_datas.append(data)
        offset += len(data)

    ico_header = struct.pack("<HHH", 0, 1, len(sizes))
    with open(ico_path, "wb") as f:
        f.write(ico_header)
        for e in entries:
            f.write(e)
        for d in image_datas:
            f.write(d)

def generate_windows_version_info(version_file: Path):
    """Generates standard Windows PE version resource for PyInstaller."""
    content = '''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '041604b0',
          [
            StringStruct('CompanyName', 'Indexo Team'),
            StringStruct('FileDescription', 'Indexo - Organizador Semantico de Arquivos'),
            StringStruct('FileVersion', '1.0.0.0'),
            StringStruct('InternalName', 'Indexo'),
            StringStruct('LegalCopyright', 'Copyright (C) 2026 Indexo Team. Todos os direitos reservados.'),
            StringStruct('OriginalFilename', 'Indexo.exe'),
            StringStruct('ProductName', 'Indexo Semantic File Organizer'),
            StringStruct('ProductVersion', '1.0.0.0')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
'''
    version_file.parent.mkdir(parents=True, exist_ok=True)
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(content)

def build():
    root = Path(__file__).resolve().parent.parent
    portable_dir = root / "Portable-EXE"
    portable_dir.mkdir(parents=True, exist_ok=True)

    # 0. Generate / Ensure Windows Compliant Icon
    generate_windows_ico(root / "resources" / "icon.png", root / "resources" / "icon.ico")
    generate_windows_ico(root / "resources" / "icon.png", root / "python-app" / "app" / "resources" / "icon.ico")

    print("=== 1. Compiling Rust Core with Maturin ===")
    env = os.environ.copy()
    env["PYO3_USE_ABI3_FORWARD_COMPATIBILITY"] = "1"
    res = subprocess.run(
        [sys.executable, "-m", "maturin", "build", "-m", "rust-core/Cargo.toml", "--release"],
        cwd=root,
        env=env
    )
    if res.returncode != 0:
        print("Maturin build failed!")
        sys.exit(res.returncode)

    # Install the built wheel into current environment
    wheel_dir = root / "target" / "wheels"
    wheels = list(wheel_dir.glob("*.whl"))
    if wheels:
        latest_wheel = max(wheels, key=lambda p: p.stat().st_mtime)
        print(f"Installing {latest_wheel.name}...")
        subprocess.run([sys.executable, "-m", "pip", "install", str(latest_wheel), "--force-reinstall"], check=True)

    print("=== 2. Packaging 100% Standalone Portable App with PyInstaller (--onefile) ===")
    main_py = root / "python-app" / "main.py"
    dist_temp = root / "build_dist"
    version_file = dist_temp / "version_info.txt"
    generate_windows_version_info(version_file)
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Indexo",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--collect-all=indexo_core",
        "--collect-all=llama_cpp",
        "--collect-all=onnxruntime",
        "--collect-all=tokenizers",
        f"--icon={root / 'resources' / 'icon.ico'}",
        f"--version-file={version_file}",
        f"--distpath={dist_temp}",
        f"--workpath={dist_temp / 'build'}",
        f"--specpath={dist_temp}",
        f"--add-data={root / 'resources' / 'system_rules.json'};resources",
        f"--add-data={root / 'resources' / 'i18n'};resources/i18n",
        f"--add-data={root / 'resources' / 'icon.png'};resources",
        f"--add-data={root / 'resources' / 'icon.ico'};resources",
        f"--add-data={root / 'resources' / 'models'};resources/models",
        f"--add-data={root / 'python-app' / 'app' / 'resources' / 'styles'};app/resources/styles",
        str(main_py)
    ]
    subprocess.run(cmd, cwd=root, check=True)

    # Move standalone executable to Portable-EXE/Indexo.exe
    compiled_exe = dist_temp / "Indexo.exe"
    if compiled_exe.exists():
        standalone_dest = portable_dir / "Indexo.exe"
        print(f"Copying standalone executable to {standalone_dest}...")
        try:
            shutil.copy2(compiled_exe, standalone_dest)
        except PermissionError:
            print("Target locked, terminating lingering Indexo processes...")
            subprocess.run(["taskkill", "/f", "/im", "Indexo.exe"], capture_output=True)
            import time
            time.sleep(1)
            shutil.copy2(compiled_exe, standalone_dest)
        shutil.rmtree(dist_temp, ignore_errors=True)

    # Clean build/ artifacts
    shutil.rmtree(root / "build", ignore_errors=True)
    if (root / "indexo.spec").exists():
        (root / "indexo.spec").unlink(missing_ok=True)

    # 3. Notify Windows Explorer to refresh icon cache immediately
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass

    print("\n=======================================================")
    print("[OK] BUILD CONCLUIDO COM SUCESSO!")
    print(f"Executável Único 100% Portátil:")
    print(f"   -> {portable_dir / 'Indexo.exe'}")
    print("=======================================================\n")

if __name__ == "__main__":
    build()
