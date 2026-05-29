import subprocess
import json

CREATE_NO_WINDOW = 0x08000000


def _ps_dialog(action: str) -> str:
    ps = {
        "files": r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Multiselect = $true
$d.Filter = 'Media|*.mp4;*.mkv;*.avi;*.mov;*.wmv;*.flv;*.webm;*.m4v;*.mpg;*.mpeg;*.ts;*.rmvb;*.3gp;*.mp3;*.wav;*.aac;*.m4a;*.ogg;*.flac|All|*.*'
$d.Title = '选择文件'
if ($d.ShowDialog() -eq 'OK') { ConvertTo-Json @($d.FileNames) } else { '[]' }
""",
        "save": r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.SaveFileDialog
$d.Filter = 'MP3|*.mp3|WAV|*.wav|AAC|*.aac|M4A|*.m4a|All|*.*'
$d.DefaultExt = '.mp3'
$d.Title = '保存文件'
if ($d.ShowDialog() -eq 'OK') { Write-Output ($d.FileName -replace '\\','\\') } else { Write-Output '' }
""",
        "dir": r"""
Add-Type -AssemblyName System.Windows.Forms
$d = New-Object System.Windows.Forms.FolderBrowserDialog
$d.Description = '选择保存目录'
if ($d.ShowDialog() -eq 'OK') { Write-Output ($d.SelectedPath -replace '\\','\\') } else { Write-Output '' }
"""
    }
    r = subprocess.run(["powershell", "-STA", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps[action]],
                       capture_output=True, text=True, timeout=120, creationflags=CREATE_NO_WINDOW)
    return r.stdout.strip()


def request_dialog(action: str) -> str:
    raw = _ps_dialog(action)
    if action in ("save", "dir"):
        return raw.strip() if raw.strip() else ""
    if action == "files":
        try:
            paths = json.loads(raw)
            return json.dumps(paths)
        except Exception:
            return "[]"
    return raw
