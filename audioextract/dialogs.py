"""Windows native file dialog bridge via PowerShell."""

import subprocess
import json
import tempfile
import os

CREATE_NO_WINDOW = 0x08000000

PS_SCRIPTS = {
    "files": """
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Multiselect = $true
$d.Filter = 'Media|*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm;*.m4v;*.mpg;*.mpeg;*.ts;*.rmvb;*.3gp;*.mp3;*.wav;*.aac;*.m4a;*.ogg;*.flac|All|*.*'
$d.Title = '选择文件'
if ($d.ShowDialog() -eq 'OK') { ConvertTo-Json @($d.FileNames) } else { '[]' }
""",
    "save": """
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.SaveFileDialog
$d.Filter = 'MP3|*.mp3|WAV|*.wav|AAC|*.aac|M4A|*.m4a|All|*.*'
$d.DefaultExt = '.mp3'
$d.Title = '保存文件'
if ($d.ShowDialog() -eq 'OK') { Write-Output $d.FileName } else { Write-Output '' }
""",
    "dir": """
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = '选择保存目录'
if ($d.ShowDialog() -eq 'OK') { Write-Output $d.SelectedPath } else { Write-Output '' }
"""
}


def request_dialog(action: str) -> str:
    script = PS_SCRIPTS.get(action, "")
    if not script:
        return ""

    ps_file = os.path.join(tempfile.gettempdir(), f"ae_dialog_{action}.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(script)

    try:
        r = subprocess.run(
            ["powershell", "-STA", "-NoProfile", "-WindowStyle", "Hidden", "-File", ps_file],
            capture_output=True, text=True, timeout=120,
            creationflags=CREATE_NO_WINDOW
        )
        raw = r.stdout.strip()
    finally:
        try:
            os.remove(ps_file)
        except Exception:
            pass

    if action in ("save", "dir"):
        return raw if raw else ""
    if action == "files":
        try:
            paths = json.loads(raw)
            return json.dumps(paths)
        except Exception:
            return "[]"
    return raw
