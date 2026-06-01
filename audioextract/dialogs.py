"""Windows native file dialog bridge via PowerShell."""

import subprocess
import json

CREATE_NO_WINDOW = 0x08000000
