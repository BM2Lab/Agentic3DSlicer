"""
Tool:        install-extension.py
Category:    automation
Tags:        extension, install, wizard, extensionsManagerModel, SlicerIGT, SlicerIGSIO, restart
Description: Install one or more Slicer extensions via the built-in extension manager wizard.
             Uses a flag file to prevent infinite restart loop. Must run in GUI mode (DISPLAY set).
Usage:       DISPLAY=:1 Slicer --python-script install-extension.py
             Edit EXTENSIONS_TO_INSTALL list before running.
Version:     1.1
Verified:    2026-03-04  (Slicer 5.10.0, SlicerIGT + SlicerIGSIO)

Notes:
- extensionsManagerModel() blocks in headless (--no-main-window) mode — must use GUI
- Extensions install to <slicer_dir>/slicer.org/Extensions-<revision>/
- slicer.app.restart() re-launches with the SAME --python-script argument — causes
  infinite loop if script calls restart() unconditionally. Fix: use a flag file.
- Dependencies (e.g. SlicerIGSIO for SlicerIGT) must be listed explicitly
"""
import os
import qt
import slicer

EXTENSIONS_TO_INSTALL = ["SlicerIGSIO", "SlicerIGT"]  # list dependencies first
FLAG_FILE = "/tmp/slicer_ext_install_done.flag"

def install():
    # Guard: if we're here after a restart triggered by this script, just exit
    if os.path.exists(FLAG_FILE):
        os.remove(FLAG_FILE)
        print("Post-restart: extensions now loaded. Installation complete.")
        return  # do NOT restart again

    em = slicer.app.extensionsManagerModel()
    pending = [n for n in EXTENSIONS_TO_INSTALL if not em.isExtensionInstalled(n)]

    if not pending:
        print("All extensions already installed — no restart needed.")
        return  # already installed on a previous run, no restart needed

    def on_installed(name):
        print(f"  Installed: {name}")

    em.extensionInstalled.connect(on_installed)

    print(f"Installing: {pending}")
    for name in pending:
        em.downloadAndInstallExtensionByName(name)

    def check_done():
        done = all(em.isExtensionInstalled(n) for n in EXTENSIONS_TO_INSTALL)
        if done:
            print("All extensions installed. Writing flag and restarting Slicer...")
            open(FLAG_FILE, "w").close()  # write flag BEFORE restart
            slicer.app.restart()
        else:
            status = {n: em.isExtensionInstalled(n) for n in EXTENSIONS_TO_INSTALL}
            print(f"  Waiting... {status}")
            qt.QTimer.singleShot(5000, check_done)

    qt.QTimer.singleShot(10000, check_done)

qt.QTimer.singleShot(3000, install)
