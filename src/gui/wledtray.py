"""
a: zak-45
d: 07/03/2025
v: 1.0.0.1

Overview

This Python file manages the system tray icon and menu for the WLEDVideoSync application.
It uses the pystray library to create the tray icon and define its associated menu options.
The menu provides quick access to various functionalities of the application, such as opening the main interface,
accessing API documentation, and viewing system information. It also offers the option to open these functionalities in
the default web browser or in a native window using a webview.

Compatibility fixes applied for macOS/Linux:
- Added a macOS-safe `_safe_close` helper and used it to ensure Tk dialogs always close on macOS.
- Moved the charts call out of the pystray callback thread into a separate process to avoid asyncio.run() inside tray thread.
- Left WebviewManager usage unchanged (it already spawns webviews in separate processes).

"""
import webbrowser
import multiprocessing
import tkinter as tk
from tkinter import messagebox

from PIL import Image
from pystray import Icon, Menu, MenuItem

from mainapp import check_server, CastAPI
from src.utl.utils import CASTUtils as Utils
from src.utl.webviewmanager import WebviewManager

from configmanager import cfg_mgr, LoggerManager, SYS_TRAY_NATIVE_UI, WLED_PID_TMP_FILE

logger_manager = LoggerManager(logger_name='WLEDLogger.systray')
systray_logger = logger_manager.logger

_, server_port = check_server()
server_ip = 'localhost'

WLEDVideoSync_gui = WebviewManager()


def select_win(url, title, width=800, height=600):
    """Open a URL in either a native webview or the default browser.

    Opens the specified URL in a native webview window if native_ui
    is True, otherwise opens it in the default web browser.
    """

    if SYS_TRAY_NATIVE_UI:
        # WebviewManager already runs webviews in separate processes, so just call it
        try:
            WLEDVideoSync_gui.open_webview(url=url, title=title, width=width, height=height)
        except Exception as e:
            systray_logger.error(f"Failed to open native webview: {e}")
            # fallback to browser
            webbrowser.open(url=url, new=0, autoraise=True)
    else:
        webbrowser.open(url=url, new=0, autoraise=True)


"""
Pystray menu
"""

def on_open_main():
    select_win(f"http://{server_ip}:{server_port}", f'WLEDVideoSync Main Window : {server_port}',
               1200, 720)


def on_open_main_browser():
    webbrowser.open(f"http://{server_ip}:{server_port}", new=0, autoraise=True)


def on_blackout():
    select_win(f"http://{server_ip}:{server_port}/api/util/blackout",f'WLEDVideoSync BLACKOUT : {server_port}',
               400, 150)


def on_player():
    select_win(f"http://{server_ip}:{server_port}/Player", f'WLEDVideoSync Player: {server_port}',
               1200, 720)


def on_api():
    select_win(f"http://{server_ip}:{server_port}/docs", f'WLEDVideoSync API: {server_port}')


def on_center():
    select_win(f"http://{server_ip}:{server_port}/Center", f'WLEDVideoSync Cast Center: {server_port}')


def on_py():
    select_win(f"http://{server_ip}:{server_port}/Pyeditor", f'WLEDVideoSync Python Editor: {server_port}')


def on_info():
    select_win(f"http://{server_ip}:{server_port}/info", f'WLEDVideoSync Infos: {server_port}',
               480, 220)


def on_charts():
    """
    Menu Charts option : run charts in a separate process to avoid calling asyncio.run() in pystray thread
    """
    try:
        proc, _ = Utils.mp_setup()
        p = proc(target=Utils.run_sys_charts, args=(WLED_PID_TMP_FILE, CastAPI.dark_mode))
        p.daemon = True
        p.start()
    except Exception as e:
        systray_logger.error(f"Failed to launch charts process: {e}")


def on_details():
    select_win(f"http://{server_ip}:{server_port}/DetailsInfo",f'WLEDVideoSync Cast(s) Details: {server_port}')


def on_control_panel():
    select_win(f"http://{server_ip}:{server_port}/control_panel",f'WLEDVideoSync Control Panel: {server_port}',
               width=1200, height=520)


def on_exit():
    select_win(f"http://{server_ip}:{server_port}/ShutDown",f'WLEDVideoSync SHUTDOWN: {server_port}',
               width=380, height=150)


def _safe_close(root: tk.Tk):
    """macOS-safe forced window close: flush events, quit, destroy."""
    try:
        root.update_idletasks()
        root.update()
    except Exception:
        pass
    try:
        root.quit()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass


def _show_tk_confirm_and_kill(pid):
    """
    This function runs in a separate process to show a tkinter confirmation dialog.
    This is the robust way to avoid conflicts between pystray's thread and tkinter's mainloop.
    """
    import psutil
    # Create an isolated Tk instance in this process
    root = tk.Tk()
    root.withdraw()  # Hide the root window

    # Bring the dialog to the front (may not be honored on all window managers)
    try:
        root.attributes('-topmost', True)
    except Exception:
        # attributes may not be available on some platforms
        pass

    try:
        if messagebox.askyesno("Confirm Force Exit",
                               "Are you sure you want to force exit WLEDVideoSync?\nThis may cause data loss and is not recommended."):
            systray_logger.warning("User confirmed force exit. Terminating process.")
            try:
                p = psutil.Process(pid)
                p.kill()
            except psutil.NoSuchProcess:
                systray_logger.error(f"Process with PID {pid} not found. Cannot force kill.")
            except Exception as e:
                systray_logger.error(f"An error occurred during force kill: {e}")
            finally:
                try:
                    WLEDVideoSync_systray.stop()
                except Exception:
                    pass
        else:
            systray_logger.info("User cancelled force exit.")
    except Exception as e:
        systray_logger.error(f"Error showing confirmation dialog: {e}")
    finally:
        _safe_close(root)


def on_force_exit():
    """
    Menu Force Exit option : kill main process
    Launches the confirmation dialog in a separate process.
    """
    # Launch the tkinter confirmation dialog in a separate process
    try:
        proc, _ = Utils.mp_setup()
        p = proc(target=_show_tk_confirm_and_kill, args=(cfg_mgr.pid,))
        p.daemon = True
        p.start()
    except Exception as e:
        systray_logger.error(f"Failed to start force-exit dialog process: {e}")


"""
Pystray definition
"""

pystray_image = Image.open(cfg_mgr.app_root_path('favicon.ico'))

pystray_menu = Menu(
    MenuItem('Open', on_open_main, visible=True,default=True),
    MenuItem('Open in Browser: Force', on_open_main_browser),
    Menu.SEPARATOR,
    MenuItem('BLACKOUT', on_blackout),
    Menu.SEPARATOR,
    MenuItem('Player', on_player),
    MenuItem('Control Panel', on_control_panel),
    Menu.SEPARATOR,
    MenuItem('API', on_api),
    Menu.SEPARATOR,
    MenuItem('Center', on_center),
    Menu.SEPARATOR,
    MenuItem('Cast details', on_details),
    MenuItem('Info', on_info),
    MenuItem('Charts', on_charts),
    MenuItem('PyEditor', on_py),
    Menu.SEPARATOR,
    MenuItem(f'FORCE Exit - server :  {server_port}', on_force_exit),
    Menu.SEPARATOR,
    MenuItem(f'Exit - server :  {server_port}', on_exit)
)

WLEDVideoSync_systray = Icon('WLEDVideoSync', icon=pystray_image, menu=pystray_menu)

# example use
if __name__ == "__main__":
    import time

    WLEDVideoSync_systray.run_detached()
    print('look on systray, this will shutdown in 10s...')
    while True:
        time.sleep(10)
        break
    WLEDVideoSync_systray.stop()
    print('end  of systray')
