"""Detect whether Microsoft Teams is currently using the microphone.

Windows records microphone use per app under
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\ConsentStore\\microphone.
An entry whose LastUsedTimeStop is 0 is using the mic right now. This needs no admin rights.
"""
import sys

KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"


def _mic_users():
    """Yield (app_key_name, in_use) for every app Windows has tracked."""
    if sys.platform != "win32":
        return
    import winreg

    def walk(root_path):
        try:
            root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_path)
        except OSError:
            return
        i = 0
        while True:
            try:
                name = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            sub_path = root_path + "\\" + name
            if name == "NonPackaged":
                yield from walk(sub_path)
                continue
            try:
                sub = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_path)
                stop, _ = winreg.QueryValueEx(sub, "LastUsedTimeStop")
                yield name, stop == 0
            except OSError:
                continue

    yield from walk(KEY)


def teams_call_active(markers=("teams",)) -> bool:
    for name, in_use in _mic_users():
        low = name.lower()
        if in_use and any(m in low for m in markers):
            return True
    return False


def apps_using_mic():
    return [name for name, in_use in _mic_users() if in_use]
