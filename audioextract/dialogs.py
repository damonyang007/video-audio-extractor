"""File dialog bridge via PowerShell with TopMost parent for foreground dialogs."""

import subprocess
import json
import tempfile
import os

CREATE_NO_WINDOW = 0x08000000

HEAD = """
Add-Type -AssemblyName System.Windows.Forms
$p = New-Object System.Windows.Forms.Form
$p.TopMost = $true
$p.Width = 1; $p.Height = 1
$p.StartPosition = 'CenterScreen'
$p.Show()
$p.Hide()
"""

FOOT = """
$p.Close()
"""

PS_SCRIPTS = {
    "files": HEAD + """
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Multiselect = $true
$d.Filter = 'Media|*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm;*.m4v;*.mpg;*.mpeg;*.ts;*.rmvb;*.3gp;*.mp3;*.wav;*.aac;*.m4a;*.ogg;*.flac|All|*.*'
$r = $d.ShowDialog($p)
if ($r -eq 'OK') { ConvertTo-Json @($d.FileNames) } else { '[]' }
""" + FOOT,
    "save": HEAD + """
$d = New-Object System.Windows.Forms.SaveFileDialog
$d.Filter = 'MP3|*.mp3|WAV|*.wav|AAC|*.aac|M4A|*.m4a|All|*.*'
$d.DefaultExt = '.mp3'
$r = $d.ShowDialog($p)
if ($r -eq 'OK') { Write-Output $d.FileName } else { Write-Output '' }
""" + FOOT,
    "dir": HEAD + """
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = 'Choose Folder'
$r = $d.ShowDialog($p)
if ($r -eq 'OK') { Write-Output $d.SelectedPath } else { Write-Output '' }
""" + FOOT,
}


def request_dialog(action: str) -> str:
    script = PS_SCRIPTS.get(action, "")
    ps_file = os.path.join(tempfile.gettempdir(), f"ae_{action}_{os.getpid()}.ps1")
    with open(ps_file, "w", encoding="utf-8") as f:
        f.write(script)

    r = subprocess.run(
        ["powershell", "-STA", "-NoProfile", "-WindowStyle", "Hidden",
         "-ExecutionPolicy", "Bypass", "-File", ps_file],
        capture_output=True, text=True, timeout=300,
        creationflags=CREATE_NO_WINDOW
    )

    try: os.unlink(ps_file)
    except Exception: pass

    raw = r.stdout.strip()
    if action == "files":
        try: return json.dumps(json.loads(raw))
        except: return "[]"
    return raw
