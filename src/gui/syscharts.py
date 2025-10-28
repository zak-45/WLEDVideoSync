"""
a: zak-45
d: 27/10/2025
v: 1.0.0

Overview:
This script provides a set of standalone, real-time monitoring dashboards for the WLEDVideoSync application,
built using the NiceGUI framework. It is designed to be launched as a separate process, creating native
windows to display various system and device statistics without interfering with the main application's
event loop.

The script contains three main classes, each responsible for a specific type of dashboard:

1.  NetCharts:
    -   Monitors and displays real-time network utilization.
    -   Charts bytes sent and received in megabytes (MB).
    -   Uses the `psutil` library to gather network I/O counters.

2.  SysCharts:
    -   Provides a comprehensive overview of system performance.
    -   Displays charts for CPU usage (%), memory utilization (%), and disk space usage (pie chart).
    -   Includes a gauge chart for system load averages (1, 5, and 15 minutes).
    -   Uses `psutil` to collect system-wide performance metrics.

3.  DevCharts:
    -   A dynamic dashboard for monitoring the status of specific network devices, particularly WLED controllers.
    -   Displays real-time charts for ping latency (ms) and WLED signal strength (%).
    -   Features expandable sections for each device, which, upon opening, dynamically generate
        and display detailed charts for WLED-specific data like FPS and RSSI.
    -   Uses `ping3` for latency checks and `aiohttp` for asynchronous requests to the WLED JSON API.
    -   Includes a "Refresh Devices" feature to dynamically update the list of monitored devices from
      an inter-process file, allowing for live updates without restarting the window.

Common Features Across All Charts:
-   **Interactive Controls**: Each chart window includes controls to pause/resume live updates, clear
    chart data, toggle notifications, and switch between light and dark modes.
-   **Logging**: A dedicated log panel in each window provides real-time feedback and error messages.
-   **Standalone Execution**: Designed to be launched from a main application (like `runcharts.py`),
    receiving necessary configuration (e.g., device IPs, dark mode state) via command-line arguments.
"""
import os

import psutil
import aiohttp

from datetime import datetime
from ping3 import ping
from nicegui import ui, run


class NetCharts:
    """
    Create charts from network utilization
    Bytes in / out
    """

    def __init__(self, dark: bool = False):
        self.multi_net = None
        self.chart_refresh_s = 2

        self.net_data_timer = []
        self.net_interval = 2
        self.timestamps = []
        self.last_rec = psutil.net_io_counters().bytes_recv
        self.last_sent = psutil.net_io_counters().bytes_sent
        self.is_paused = False
        self.pause_button = None

        """ ui design """
        with ui.header(bordered=True, elevated=True).classes('items-center justify-between'):
            ui.label('Network Stats').classes('text-2xl font-bold')
            with ui.row():
                self.notify = ui.switch('Notification', value=True).props('color=cyan')
                self.dark_switch = ui.switch('Dark Mode', value=dark).bind_value_to(ui.dark_mode(), 'value').props('color=cyan')
                self.dark_mode = ui.dark_mode()
                if dark:
                    self.dark_switch.value = True

        self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            self.pause_button = ui.button('Pause', icon='pause', on_click=self.toggle_pause_chart)
        self.log.push(f"Auto refresh time: {self.chart_refresh_s}sec")

        """ timers """
        self.net_data_timer.append(ui.timer(self.net_interval, lambda: self.net_datas()))
        self.chart_net_timer = ui.timer(self.chart_refresh_s, lambda: self.multi_net.update())

    def create_charts(self):
        self.multi_net = ui.echart(
            {
                'title': {'text': 'Net (MB)', 'left': 'center'},
                'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
                'legend': {
                    'data': [],
                    'top': '20%',
                    'orient': 'horizontal',
                    'textStyle': {'fontWeight': 'bold'}
                },
                'grid': {'left': '5%', 'right': '5%', 'bottom': '10%', 'containLabel': True},
                'toolbox': {
                    'feature': {
                        'dataZoom': {'yAxisIndex': 'none'},
                        'restore': {},
                        'saveAsImage': {}
                    }
                },
                'xAxis': {
                    'type': 'category',
                    'data': []
                },
                'yAxis': {
                    'type': 'value',
                    'min': 0,
                    'axisLabel': {':formatter': 'value => value + " MB"'},
                    'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}
                },
                'series': []
            }
        ).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

        self.multi_net.options['legend']['data'].append('bytes_in')
        series_data = {'name': 'bytes_in', 'type': 'line', 'data': []}
        self.multi_net.options['series'].append(series_data)

        self.multi_net.options['legend']['data'].append('bytes_out')
        series_data = {'name': 'bytes_out', 'type': 'line', 'data': []}
        self.multi_net.options['series'].append(series_data)

    def toggle_pause_chart(self):
        """Toggles the pause state of the chart updates."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            ui.notify('Chart refresh paused.')
            self.log.push('Chart refresh paused.')
            self.chart_net_timer.deactivate()
            for timer in self.net_data_timer:
                timer.deactivate()
            self.pause_button.props('icon=play_arrow').set_text('Resume')
        else:
            ui.notify('Chart refresh resumed.')
            self.log.push('Chart refresh resumed.')
            self.chart_net_timer.activate()
            for timer in self.net_data_timer:
                timer.activate()
            self.pause_button.props('icon=pause').set_text('Pause')

    def clear(self):
        self.multi_net.options['series'][0]['data'].clear()
        self.multi_net.options['series'][1]['data'].clear()
        self.multi_net.options['xAxis']['data'] = []
        self.log.clear()
        self.log.push(f"Auto refresh time: {str(self.chart_refresh_s)}sec")

    async def net_datas(self):
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        # global last_rec, last_sent
        bytes_rec = psutil.net_io_counters().bytes_recv
        bytes_sent = psutil.net_io_counters().bytes_sent

        new_rec = (bytes_rec - self.last_rec) / 1024 / 1024
        new_sent = (bytes_sent - self.last_sent) / 1024 / 1024

        self.multi_net.options['series'][0]['data'].append(new_rec)
        self.multi_net.options['series'][1]['data'].append(new_sent)
        self.multi_net.options['xAxis']['data'].append(date_time_str)

        self.last_rec = psutil.net_io_counters().bytes_recv
        self.last_sent = psutil.net_io_counters().bytes_sent

        if self.dark_switch.value is True:
            self.dark_mode.enable()
        else:
            self.dark_mode.disable()


class SysCharts:
    """
    Create charts from system datas
    CPU, RAM, ...
    """
    cpu_warning: int = 60
    memory_warning: int = 85
    free_warning: int = 10

    def __init__(self, dark: bool = False):
        self.chart_sys_timer = None
        self.log = None
        self.dark_mode = None
        self.in_dark = dark
        self.dark_switch = None
        self.notify = None
        self.cpu_chart = None
        self.load_chart = None
        self.memory_chart = None
        self.disk_chart = None
        self.chart_refresh_s = 2
        self.sys_data_timer = []
        self.cpu_data_timer = []
        self.sys_interval = 5
        self.cpu_interval = 2
        self.timestamps = []
        self.is_paused = False
        self.pause_button = None

        self.gauge_data = [
            {
                'value': 20,
                'name': 'One Minute',
                'title': {
                    'offsetCenter': ['0%', '-70%']
                },
                'detail': {
                    'valueAnimation': 'true',
                    'offsetCenter': ['0%', '-50%']
                }
            },
            {
                'value': 40,
                'name': 'Five Minutes',
                'title': {
                    'offsetCenter': ['0%', '-10%']
                },
                'detail': {
                    'valueAnimation': 'true',
                    'offsetCenter': ['0%', '10%']
                }
            },
            {
                'value': 60,
                'name': 'Fifteen Minutes',
                'title': {
                    'offsetCenter': ['0%', '50%']
                },
                'detail': {
                    'valueAnimation': 'true',
                    'offsetCenter': ['0%', '70%']
                }
            }
        ]

    async def setup_ui(self):
        """ ui design """
        with ui.header(bordered=True, elevated=True).classes('items-center justify-between'):
            ui.label('System Stats').classes('text-2xl font-bold')
            with ui.row():
                self.notify = ui.switch('Notification', value=True).props('color=cyan')
                self.dark_switch = ui.switch('Dark Mode', value=self.in_dark).bind_value_to(ui.dark_mode(), 'value').props('color=cyan')
                self.dark_mode = ui.dark_mode(on_change=self.change_chart_mode)
                if self.in_dark:
                    self.dark_switch.value = True

        await self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            self.pause_button = ui.button('Pause', icon='pause', on_click=self.toggle_pause_chart)

        self.log.push(f"Auto refresh time: {self.chart_refresh_s}sec")

        """ timers """
        self.cpu_data_timer.append(ui.timer(self.cpu_interval, lambda: self.cpu_datas()))
        self.sys_data_timer.append(ui.timer(self.sys_interval, lambda: self.sys_datas()))
        self.chart_sys_timer = ui.timer(self.chart_refresh_s, lambda: self.update_charts())

    async def create_charts(self):
        self.cpu_chart = ui.echart({
            'darkMode': 'false',
            'legend': {
                'show': True,
                'data': ['CPU %'],
                'top': '20%',
                'textStyle': {'fontWeight': 'bold', 'fontSize': 13}
            },
            'title': {
                'text': "CPU Usage",
                'left': 'center',
                'textStyle': {'fontSize': 18, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'backgroundColor': '#222',
                'borderColor': '#aaa',
                'textStyle': {'color': '#fff'}
            },
            'grid': {'left': '5%', 'right': '5%', 'bottom': '10%', 'containLabel': True},
            'toolbox': {
                'feature': {
                    'dataZoom': {'yAxisIndex': 'none'},
                    'restore': {},
                    'saveAsImage': {}
                }
            },
            'xAxis': {
                'type': 'category',
                'data': [],
                'axisLabel': {'fontSize': 12, 'color': '#333'}
            },
            'yAxis': {
                'type': 'value',
                'min': 0,
                'max': 100,
                'axisLabel': {':formatter': 'value => value + " %"'},
                'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}
            },
            'series': [{
                'data': [],
                'name': 'CPU %',
                'type': 'line',
                'smooth': True,
                'areaStyle': {'color': '#535894', 'opacity': 0.3},
                'lineStyle': {'width': 3, 'color': '#535894'},
                'symbol': 'circle',
                'symbolSize': 7,
                'emphasis': {'focus': 'series'}
            }]
        }).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

        self.memory_chart = ui.echart({
            'darkMode': 'false',
            'title': {
                'text': "Memory Utilization (%)",
                'left': 'center',
                'textStyle': {'fontSize': 18, 'fontWeight': 'bold'}
            },
            'tooltip': {
                'trigger': 'axis',
                'backgroundColor': '#222',
                'borderColor': '#aaa',
                'textStyle': {'color': '#fff'}
            },
            'grid': {'left': '5%', 'right': '5%', 'bottom': '10%', 'containLabel': True},
            'toolbox': {
                'feature': {
                    'dataZoom': {'yAxisIndex': 'none'},
                    'restore': {},
                    'saveAsImage': {}
                }
            },
            'xAxis': {
                'type': 'category',
                'data': [],
                'axisLabel': {'fontSize': 12, 'color': '#333'}
            },
            'yAxis': {
                'type': 'value',
                'min': 0,
                'max': 100,
                'axisLabel': {':formatter': 'value => value + " %"'},
                'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}
            },
            'series': [{
                'data': [],
                'name': 'Memory %',
                'type': 'bar',
                'showBackground': True,
                'backgroundStyle': {
                    'color': 'rgba(220, 220, 220, 0.8)'
                },
                'itemStyle': {
                    'color': '#4caf50',
                    'borderRadius': [6, 6, 0, 0]
                },
                'emphasis': {
                    'itemStyle': {
                        'color': '#388e3c'
                    }
                }
            }]
        }).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

        with ui.row().classes('w-full no-wrap'):
            with ui.card().classes('w-1/2'):
                self.disk_chart = ui.echart({
                    'darkMode': 'false',
                    'title': {
                        'text': "Disk Space Utilization",
                        'left': 'center'
                    },
                    'legend': {
                        'orient': 'vertical',
                        'left': 'left'
                    },
                    'tooltip': {
                        'trigger': 'item'
                    },
                    'series': [{
                        'name': 'Disk Space',
                        'data': [
                            {'name': '% used', 'value': 0},
                            {'name': '% free', 'value': 100}
                        ],
                        'emphasis': {
                            'itemStyle': {
                                'shadowBlur': 10,
                                'shadowOffsetX': 0,
                                'shadowColor': 'rgba(0, 0, 0, 0.5)'
                            }},
                        'type': 'pie',
                        'radius': '50%',
                        'showBackground': 'true',
                        'backgroundStyle': {
                            'color': 'rgba(220, 220, 220, 0.8)'
                        }
                    }]
                }).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

            with ui.card().classes('w-1/2'):
                self.load_chart = ui.echart(
                    {
                        'title': {
                            'text': "Load Averages"
                        },
                        'series': [
                            {
                                'type': 'gauge',
                                'startAngle': 180,
                                'endAngle': -270,
                                'pointer': {
                                    'show': 'false',
                                    'width': 0
                                },
                                'progress': {
                                    'show': 'true',
                                    'overlap': 'false',
                                    'roundCap': 'true',
                                    'clip': 'false',
                                    'itemStyle': {
                                        'borderWidth': 1,
                                        'borderColor': '#464646'
                                    }
                                },
                                'axisLine': {
                                    'lineStyle': {
                                        'width': 10
                                    }
                                },
                                'splitLine': {
                                    'show': 'false',
                                    'distance': 0,
                                    'length': 0
                                },
                                'axisTick': {
                                    'show': 'false',
                                    'length': 0
                                },
                                'axisLabel': {
                                    'show': 'false',
                                    'distance': 0,
                                    'fontSize': 8
                                },
                                'data': self.gauge_data,
                                'title': {
                                    'fontSize': 14
                                },
                                'detail': {
                                    'width': 50,
                                    'height': 14,
                                    'fontSize': 14,
                                    'color': 'inherit',
                                    'borderColor': 'inherit',
                                    'borderRadius': 20,
                                    'borderWidth': 1,
                                    'formatter': '{value}%'
                                }
                            }
                        ]
                    }).classes('min-w-full min-h-80')

    async def toggle_pause_chart(self):
        """Toggles the pause state of the chart updates."""
        self.is_paused = not self.is_paused
        if self.is_paused:
            ui.notify('Chart refresh paused.')
            self.log.push('Chart refresh paused.')
            self.chart_sys_timer.deactivate()
            for timer in self.cpu_data_timer:
                timer.deactivate()
            for timer in self.sys_data_timer:
                timer.deactivate()
            self.pause_button.props('icon=play_arrow').set_text('Resume')
        else:
            ui.notify('Chart refresh resumed.')
            self.log.push('Chart refresh resumed.')
            self.chart_sys_timer.activate()
            for timer in self.cpu_data_timer:
                timer.activate()
            for timer in self.sys_data_timer:
                timer.activate()
            self.pause_button.props('icon=pause').set_text('Pause')

    async def update_charts(self):
        self.memory_chart.update()
        self.cpu_chart.update()
        self.disk_chart.update()
        self.load_chart.update()

        if self.dark_switch.value is True:
            self.dark_mode.enable()
        else:
            self.dark_mode.disable()

    async def clear(self):
        self.memory_chart.options['series'][0]['data'].clear()
        self.cpu_chart.options['series'][0]['data'].clear()
        self.disk_chart.options['series'][0]['data'][0]['value'] = 0
        self.disk_chart.options['series'][0]['data'][1]['value'] = 0

        self.memory_chart.options['xAxis']['data'] = []
        self.cpu_chart.options['xAxis']['data'] = []

        self.log.clear()
        self.log.push(f"Auto refresh time: {str(self.chart_refresh_s)}sec")

    async def sys_datas(self):
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")
        load = await self.get_load_averages()

        memory_data = await self.get_memory()
        disk_free_data = round(100 - await self.get_disk(), 2)
        disk_used_data = round(await self.get_disk(), 2)

        self.memory_chart.options['series'][0]['data'].append(memory_data)
        self.disk_chart.options['series'][0]['data'][0]['value'] = disk_used_data
        self.disk_chart.options['series'][0]['data'][1]['value'] = disk_free_data
        self.gauge_data[0]['value'] = int(round(load['one_min'], 2))
        self.gauge_data[1]['value'] = int(round(load['five_min'], 2))
        self.gauge_data[2]['value'] = int(round(load['fifteen_min'], 2))
        self.load_chart.options['series'][0]['data'] = self.gauge_data

        self.memory_chart.options['xAxis']['data'].append(date_time_str)

        if memory_data >= SysCharts.memory_warning and self.notify.value is True:
            ui.notify('High memory utilization', type='negative')
        if disk_free_data <= SysCharts.free_warning and self.notify.value is True:
            ui.notify('High disk utilization', type='negative')

    async def cpu_datas(self):
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        cpu_data = await self.get_cpu()

        self.cpu_chart.options['series'][0]['data'].append(cpu_data)
        self.cpu_chart.options['xAxis']['data'].append(date_time_str)

        if cpu_data >= SysCharts.cpu_warning and self.notify.value is True:
            ui.notify('High CPU utilization', type='negative')

    @staticmethod
    async def get_cpu():
        return psutil.cpu_percent(interval=1, percpu=False)

    @staticmethod
    async def get_load_averages():
        load_avg = [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()]
        return {
            "one_min": load_avg[0],
            "five_min": load_avg[1],
            "fifteen_min": load_avg[2],
        }

    @staticmethod
    async def get_memory():
        mem = psutil.virtual_memory()
        return mem[2]

    @staticmethod
    async def get_disk():
        disk = psutil.disk_usage('/')
        return disk[3]

    async def change_chart_mode(self):
        """toggle dark mode on chart"""
        self.cpu_chart.options.update({'darkMode': not self.cpu_chart.options['darkMode']})
        self.disk_chart.options.update({'darkMode': not self.cpu_chart.options['darkMode']})
        self.cpu_chart.update()  # render on client
        self.disk_chart.update()  # render on client


class DevCharts:
    """Creates a dynamic dashboard for monitoring network devices.

    This class provides a user interface for monitoring the status of multiple
    network devices. It displays real-time charts for ping latency and, for
    WLED devices, signal strength, FPS, and RSSI.

    Key Features:
    - **Concurrent Device Probing**: Uses `asyncio.gather` to fetch initial
      device information concurrently, ensuring a fast page load even with
      many offline devices.
    - **Dynamic Chart Generation**: Detailed charts for WLED devices (FPS, RSSI)
      are created on-demand when the user expands that device's section,
      reducing initial load and network traffic.
    - **Live Refresh**: A "Refresh Devices" button allows the user to update the
      list of monitored devices from the main application without restarting
      the chart window.
    - **Interactive Controls**: Provides controls to pause/resume all chart
      updates, clear chart data, and toggle notifications and dark mode.
    - **Robust Error Handling**: Gracefully handles offline or non-WLED devices,
      clearly marking them in the UI.
    """

    def __init__(self, dark: bool = False, inter_proc_file: str = ''):
        """Initializes the DevCharts instance.

        Args:
            dark: Whether to start in dark mode.
            inter_proc_file: The path to the shelve file for inter-process communication.
        """
        self.in_dark = dark
        self.log = None
        self.dark_mode = None
        self.chart_wled_timer = None
        self.chart_ping_timer = None
        self.dark_switch = None
        self.notify = None
        self.ips = None
        self.maxTimeSec = 600
        self.pingAlertLimitMs = 100
        self.maxPingResponseTimeS = 0.3
        self.chart_refresh_s = 2
        self.wled_chart_refresh_s = 5
        self.ip_chart = []
        self.wled_chart_fps = []
        self.wled_chart_rsi = []
        self.wled_ips = []
        self.wled_data_timer = []
        self.wled_interval = 5
        self.ping_data_timer = []
        self.pingIntervalS = 2
        self.multi_ping = None
        self.multi_signal = None
        self.is_paused = False
        self.refresh_button = None
        self.pause_button = None
        self.inter_proc_file = inter_proc_file

    async def setup_ui(self, dev_ips: list = None):
        """ ui design """

        if dev_ips is None:
            dev_ips = ['127.0.0.1']
        self.ips = dev_ips

        with ui.header(bordered=True, elevated=True).classes('items-center justify-between'):
            ui.label('Device Stats').classes('text-2xl font-bold')
            with ui.row():
                self.notify = ui.switch('Notification', value=True).props('color=cyan')
                self.dark_switch = ui.switch('Dark Mode', value=self.in_dark).bind_value_to(ui.dark_mode(), 'value').props('color=cyan')
                self.dark_mode = ui.dark_mode(on_change=self.change_chart_mode)
                if self.in_dark:
                    self.dark_switch.value = True

        await self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            self.refresh_button = ui.button('Refresh Devices', icon='refresh', on_click=self.refresh_devices)
            self.pause_button = ui.button('Pause', icon='pause', on_click=self.toggle_pause_chart)

        self.log.push(f"Auto refresh time: {self.chart_refresh_s}sec")

        self.ping_data_timer.append(ui.timer(self.pingIntervalS, lambda: self.ping_datas()))

        for i, _ in enumerate(self.wled_ips):
            self.wled_data_timer.append(
                ui.timer(self.wled_interval, lambda chart_number=i: self.wled_datas(chart_number)))

        self.chart_ping_timer = ui.timer(self.chart_refresh_s, lambda: self.multi_ping.update())
        self.chart_wled_timer = ui.timer(self.wled_chart_refresh_s, lambda: self.update_wled_charts())

    async def refresh_devices(self):
        """Refreshes the list of devices from the inter-process file and reloads the charts."""
        import shelve
        import runcharts  # Import the runcharts module to access its globals
        import sys
        proc_file = self.inter_proc_file

        self.log.push("Refreshing device list...")
        ui.notify("Refreshing device list...")

        # Shelve file extension handling can differ between Python versions.
        # Conditionally check for the .dat file for better compatibility.
        file_to_check = proc_file
        if sys.version_info < (3, 13):
            file_to_check = f'{proc_file}.dat'

        if os.path.exists(file_to_check):
            with shelve.open(proc_file, 'r') as proc_file:
                new_ips = proc_file.get("all_hosts", [])
        else:
            new_ips = ['127.0.0.1']
            self.log.push(f"Warning: Inter-process file '{proc_file}' not found. Defaulting to localhost.")

        if new_ips != self.ips:
            self.ips = new_ips
            # Update the global DEV_LIST in the runcharts module
            runcharts.DEV_LIST = new_ips

            self.log.push(f"Device list updated to: {self.ips}")

            # Deactivate and clear all existing timers before reloading
            for timer in self.ping_data_timer:
                timer.deactivate()
            for timer in self.wled_data_timer:
                timer.deactivate()
            self.ping_data_timer.clear()
            self.wled_data_timer.clear()

            # Clear existing chart data
            self.clear()
            self.wled_ips.clear()
            self.wled_chart_fps.clear()
            self.wled_chart_rsi.clear()

            # Reload the page to recreate all UI elements and timers
            ui.navigate.reload()
            ui.notify("Device charts refreshed.", type='positive')
        else:
            ui.notify("Device list is already up-to-date.", type='info')

    async def create_charts(self):
        self.multi_ping = ui.echart(
            {
                'darkMode': 'false',
                'title': {'text': 'Ping (ms)', 'left': 'center'},
                'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
                'legend': {
                    'data': [],
                    'top': '20%',
                    'orient': 'horizontal',
                    'textStyle': {'fontWeight': 'bold'}
                },
                'grid': {'left': '5%', 'right': '5%', 'bottom': '10%', 'containLabel': True},
                'toolbox': {
                    'feature': {
                        'dataZoom': {'yAxisIndex': 'none'},
                        'restore': {},
                        'saveAsImage': {}
                    }
                },
                'xAxis': {
                    'type': 'category',
                    'data': []
                },
                'yAxis': {
                    'type': 'value',
                    'min': 0,
                    'axisLabel': {':formatter': 'value => value + " ms"'},
                    'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}
                },
                'series': []
            }
        ).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

        self.multi_signal = ui.echart(
            {
                'darkMode': 'false',
                'title': {'text': 'WLED Signal (%)', 'left': 'center'},
                'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'cross'}},
                'legend': {
                    'data': [],
                    'top': '20%',
                    'orient': 'horizontal',
                    'textStyle': {'fontWeight': 'bold'}
                },
                'grid': {'left': '5%', 'right': '5%', 'bottom': '10%', 'containLabel': True},
                'toolbox': {
                    'feature': {
                        'dataZoom': {'yAxisIndex': 'none'},
                        'restore': {},
                        'saveAsImage': {}
                    }
                },
                'xAxis': {
                    'type': 'category',
                    'data': []
                },
                'yAxis': {
                    'type': 'value',
                    'min': 0,
                    'max': 100,
                    'axisLabel': {':formatter': 'value => value + " %"'},
                    'splitLine': {'show': True, 'lineStyle': {'type': 'dashed'}}
                },
                'series': []
            }
        ).on('dblclick', lambda: self.toggle_pause_chart()).classes('w-full h-45')

        # Fetch all WLED info concurrently to speed up page load
        import asyncio
        tasks = [self.get_wled_info(ip) for ip in self.ips]
        all_wled_data = await asyncio.gather(*tasks)

        with ui.row():
            for i, cast_ip in enumerate(self.ips):
                wled_data = all_wled_data[i]

                ip_exp = ui.expansion(cast_ip, icon='lightbulb') \
                    .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]') \
                    .on('update:model-value', lambda e, ip=cast_ip: self._refresh_single_wled_chart(e, ip, wled_grid))

                self.multi_ping.options['legend']['data'].append(cast_ip)
                series_data = {'name': cast_ip, 'type': 'line', 'data': []}
                self.multi_ping.options['series'].append(series_data)

                self.multi_signal.options['legend']['data'].append(cast_ip)
                series_data = {'name': cast_ip, 'type': 'line', 'areaStyle': {'color': '#32a84c', 'opacity': 0.5},
                               'data': []}
                self.multi_signal.options['series'].append(series_data)

                with ip_exp:
                    # Use a responsive grid to center the charts and adapt to screen size
                    with ui.grid(columns=1).classes('w-full justify-center') as wled_grid:
                        if not wled_data:
                            ui.label('NOT WLED device').style('background: red')
                        else:
                            self.wled_ips.append(cast_ip)
                            with ui.card().style('min-width: 480px'):
                                self.wled_chart_fps.append(
                                    ui.echart({
                                        'darkMode': 'false',
                                        'title': {'text': 'WLED FPS', 'left': 'center'},
                                        'tooltip': {
                                            'formatter': '{a} <br/>{b} : {c}',
                                            'backgroundColor': '#222',
                                            'borderColor': '#aaa',
                                            'textStyle': {'color': '#fff'}
                                        },
                                        'series': [
                                            {
                                                'name': 'FramePerSecond',
                                                'type': 'gauge',
                                                'min': 0,
                                                'max': 120,
                                                'splitNumber': 6,
                                                'axisLine': {
                                                    'lineStyle': {
                                                        'width': 10,
                                                        'color': [
                                                            [0.5, '#91cc75'],
                                                            [0.8, '#fac858'],
                                                            [1, '#ee6666']
                                                        ]
                                                    }
                                                },
                                                'progress': {'show': True, 'width': 10},
                                                'pointer': {'show': True, 'length': '70%', 'width': 4},
                                                'detail': {
                                                    'valueAnimation': True,
                                                    'formatter': '{value} FPS',
                                                    'fontSize': 18,
                                                    'color': '#333'
                                                },
                                                'title': {
                                                    'fontSize': 1,
                                                    'offsetCenter': [0, '-35%']
                                                },
                                                'data': [{'value': 0, 'name': 'FPS'}]
                                            }
                                        ]
                                    }).on('dblclick', lambda: self.toggle_pause_chart())
                                )
                            with ui.card().style('min-width: 480px'):
                                self.wled_chart_rsi.append(
                                    ui.echart({
                                        'darkMode': 'false',
                                        'tooltip': {'trigger': 'axis'},
                                        'xAxis': {'type': 'category', 'data': []},
                                        'yAxis': {'type': 'value',
                                                  'axisLabel': {':formatter': 'value =>  "dBm " + value'}},
                                        'legend': {'formatter': 'RSSI', 'textStyle': {'color': 'red'}},
                                        'series': [
                                            {'type': 'line', 'name': cast_ip,
                                             'areaStyle': {'color': '#535894', 'opacity': 0.5}, 'data': []}
                                        ]
                                    }).on('dblclick', lambda: self.toggle_pause_chart())
                                )

                    wled_card = ui.card()
                    with ui.row():
                        add_icon = ui.icon('add', size='sm').style('cursor: pointer')
                        add_icon.on('click', lambda i_wled_card=wled_card: i_wled_card.set_visibility(True))
                        remove_icon = ui.icon('remove', size='sm').style('cursor: pointer')
                        remove_icon.on('click', lambda i_wled_card=wled_card: i_wled_card.set_visibility(False))
                    with wled_card:
                        editor = ui.json_editor({'content': {'json': wled_data}})
                        editor.run_editor_method('updateProps', {'readOnly': True})
                        wled_card.set_visibility(False)

    async def toggle_pause_chart(self):
        """Toggles the pause state of the chart updates."""
        self.is_paused = not self.is_paused
        if self.notify.value:
            ui.notify(f'Chart refresh {"paused" if self.is_paused else "resumed"}.')
        self.log.push(f'Chart refresh {"paused" if self.is_paused else "resumed"}.')

        if self.is_paused:
            self.chart_ping_timer.deactivate()
            self.chart_wled_timer.deactivate()
            for timer in self.ping_data_timer: timer.deactivate()
            for timer in self.wled_data_timer: timer.deactivate()
            self.pause_button.props('icon=play_arrow').set_text('Resume')
        else:
            self.chart_ping_timer.activate()
            self.chart_wled_timer.activate()
            for timer in self.ping_data_timer: timer.activate()
            for timer in self.wled_data_timer: timer.activate()
            self.pause_button.props('icon=pause').set_text('Pause')

    def clear(self):
        for n, _ in enumerate(self.ips):
            self.multi_ping.options['series'][n]['data'].clear()
            self.multi_signal.options['series'][n]['data'].clear()
        self.multi_ping.options['xAxis']['data'] = []
        self.multi_signal.options['xAxis']['data'] = []

        self.log.clear()
        self.log.push(f"Auto refresh time: {str(self.chart_refresh_s)}sec")
        self.log.push(f"Auto wled refresh time: {str(self.wled_chart_refresh_s)}sec")

    async def ping_datas(self):
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        for cast_ip in self.ips:
            response_time = await run.io_bound(lambda: ping(cast_ip, timeout=self.maxPingResponseTimeS, unit='ms'))
            if response_time is None or response_time is False:
                self.log.push(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip)
                if self.notify.value:
                    ui.notify(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip, type='negative')

                # Find the correct series for the IP that failed and append 0
                series_found = False
                for series in self.multi_ping.options['series']:
                    if series['name'] == cast_ip:
                        series['data'].append(0)
                        series_found = True
                        break
                if not series_found:
                    self.log.push(f"Error: Could not find chart series for IP {cast_ip}")
            else:
                k = 0
                for _ in self.multi_ping.options['series']:
                    if self.multi_ping.options['series'][k]['name'] == cast_ip:
                        self.multi_ping.options['series'][k]['data'].append(round(response_time, 2))
                        break
                    k += 1

                if response_time > self.pingAlertLimitMs:
                    self.log.push(
                        datetime.now().strftime('%H:%M:%S') + " high ping reply time from " + cast_ip + " > " + str(
                            response_time) + " ms")

        self.multi_ping.options['xAxis']['data'].append(date_time_str)

        if self.dark_switch.value is True:
            self.dark_mode.enable()
        else:
            self.dark_mode.disable()

    async def wled_datas(self, i):
        cast_ip = self.wled_ips[i]

        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        wled_data = await self.get_wled_info(cast_ip)

        if wled_data == {}:
            self.log.push(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip)
            if self.notify.value:
                ui.notify(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip, type='negative')

            self.wled_chart_fps[i].options['series'][0]['data'].append(0)
            self.wled_chart_rsi[i].options['series'][0]['data'].append(0)

            for j, item in enumerate(self.multi_signal.options['series']):
                self.multi_signal.options['series'][j]['data'].append(0)
        else:
            self.wled_chart_rsi[i].options['series'][0]['data'].append(wled_data['wifi']['rssi'])
            self.wled_chart_rsi[i].options['xAxis']['data'].append(date_time_str)

            self.wled_chart_fps[i].options['series'][0]['data'][0]['value'] = wled_data['leds']['fps']

            k = 0
            for _ in self.multi_signal.options['series']:
                if self.multi_signal.options['series'][k]['name'] == cast_ip:
                    self.multi_signal.options['series'][k]['data'].append(wled_data['wifi']['signal'])
                    break
                k += 1

        if i == 0:
            self.multi_signal.options['xAxis']['data'].append(date_time_str)

    async def update_wled_charts(self):
        for i, _ in enumerate(self.wled_ips):
            self.wled_chart_rsi[i].update()
            self.wled_chart_fps[i].update()
        self.multi_signal.update()

    @staticmethod
    async def get_wled_info(host, timeout: int = 2):
        """
        Take matrix information from WLED device
        :param host:
        :param timeout:
        :return:
        """
        url = f'http://{host}/json/info'
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(url) as response:
                    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                    return await response.json()
        except Exception as error:
            print(f'Not able to get WLED info for {host}: {error}')
            return {}

    async def _refresh_single_wled_chart(self, event, ip_address, wled_grid):
        """Refreshes the data for a single WLED device when its expansion is opened."""
        if event.args:  # Only refresh when the expansion is opened (event.args is True)
            wled = await self.get_wled_info(ip_address)
            if not wled:
                return  # Not a WLED device or offline, do nothing.

            # If this is the first time we see this IP as a WLED device, create its charts.
            if ip_address not in self.wled_ips:
                self.log.push(f"Device {ip_address} is now a WLED device. Creating charts...")
                self.wled_ips.append(ip_address)
                wled_grid.clear()  # Clear the "NOT WLED device" label
                with wled_grid:
                    with ui.card().style('min-width: 480px'):
                        self.wled_chart_fps.append(
                            ui.echart({
                                'title': {'text': 'WLED FPS', 'left': 'center'},
                                'tooltip': {'formatter': '{a} <br/>{b} : {c}',
                                            'backgroundColor': '#222',
                                            'borderColor': '#aaa',
                                            'textStyle': {'color': '#fff'}},
                                'series': [{'name': 'FramePerSecond',
                                            'type': 'gauge',
                                            'min': 0,
                                            'max': 120,
                                            'splitNumber': 6,
                                            'axisLine': {'lineStyle': {'width': 10,
                                                                       'color': [[0.5, '#91cc75'],
                                                                                 [0.8, '#fac858'],
                                                                                 [1, '#ee6666']]}},
                                            'progress': {'show': True, 'width': 10},
                                            'pointer': {'show': True, 'length': '70%', 'width': 4},
                                            'detail': {'valueAnimation': True,
                                                       'formatter': '{value} FPS',
                                                       'fontSize': 18,
                                                       'color': '#333'},
                                            'title': {'fontSize': 14, 'offsetCenter': [0, '-30%']},
                                            'data': [{'value': 0, 'name': 'FPS'}]
                                            }]
                            }).on('dblclick', lambda: self.toggle_pause_chart())
                        )
                    with ui.card().style('min-width: 480px'):
                        self.wled_chart_rsi.append(
                            ui.echart({
                                'tooltip': {'trigger': 'axis'},
                                'xAxis': {'type': 'category', 'data': []},
                                'yAxis': {'type': 'value', 'axisLabel': {':formatter': 'value =>  "dBm " + value'}},
                                'legend': {'formatter': 'RSSI', 'textStyle': {'color': 'red'}},
                                'series': [{'type': 'line',
                                            'name': ip_address,
                                            'areaStyle': {'color': '#535894', 'opacity': 0.5},
                                            'data': []}]
                            }).on('dblclick', lambda: self.toggle_pause_chart())
                        )
                # Add a new timer for the newly created charts
                wled_index = self.wled_ips.index(ip_address)
                self.wled_data_timer.append(
                    ui.timer(self.wled_interval, lambda chart_number=wled_index: self.wled_datas(chart_number)))
                if self.is_paused:  # If paused, keep the new timer paused
                    self.wled_data_timer[-1].deactivate()

            # Now, refresh the data for the device
            try:
                wled_index = self.wled_ips.index(ip_address)
                await self.wled_datas(wled_index)
                self.wled_chart_fps[wled_index].update()
                self.wled_chart_rsi[wled_index].update()
                self.log.push(f"Refreshed data for {ip_address}")
            except (ValueError, IndexError) as e:
                self.log.push(f"Error refreshing chart for {ip_address}: {e}")

    async def change_chart_mode(self):
        """toggle dark mode on chart """
        self.multi_ping.options.update({'darkMode': not self.multi_ping.options['darkMode']})
        self.multi_signal.options.update({'darkMode': not self.multi_signal.options['darkMode']})
        self.multi_signal.update()  # render on client
        self.multi_ping.update()  # render on client
