import asyncio
from datetime import datetime

import requests
from ping3 import ping

import psutil
from nicegui import ui


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

        """ ui design """
        with ui.row().classes('no-wrap'):
            self.notify = ui.switch('Notification')
            self.notify.value = True
            self.dark_switch = ui.switch('Dark Mode')
            self.dark_mode = ui.dark_mode()
            if dark:
                self.dark_switch.value = True

        self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            ui.button('Pause 5s', on_click=self.pause_chart)
        self.log.push(f"Auto refresh time: {self.chart_refresh_s}sec")

        """ timers """
        self.net_data_timer.append(ui.timer(self.net_interval, lambda: self.net_datas()))
        self.chart_net_timer = ui.timer(self.chart_refresh_s, lambda: self.multi_net.update())

    def create_charts(self):
        self.multi_net = ui.echart(
            {
                'title': {'text': 'Net (MB)'},
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': []},
                'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': 'true'},
                'toolbox': {'feature': {'dataZoom': {'yAxisIndex': 'none'}, 'restore': {}, 'saveAsImage': {}}},
                'xAxis': {'type': 'category', 'data': []},
                'yAxis': {'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " " '}},
                'series': []
            }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

        self.multi_net.options['legend']['data'].append('bytes_in')
        series_data = {'name': 'bytes_in', 'type': 'line', 'data': []}
        self.multi_net.options['series'].append(series_data)

        self.multi_net.options['legend']['data'].append('bytes_out')
        series_data = {'name': 'bytes_out', 'type': 'line', 'data': []}
        self.multi_net.options['series'].append(series_data)

    def pause_chart(self):
        ui.notify('Refresh has been paused for 5s ')
        self.log.push('Pause for 5 seconds')

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
        with ui.row().classes('no-wrap'):
            self.notify = ui.switch('Notification')
            self.notify.value = True
            self.dark_switch = ui.switch('Dark Mode')
            self.dark_mode = ui.dark_mode(on_change=self.change_chart_mode)
            if self.in_dark:
                self.dark_switch.value = True

        await self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            ui.button('Pause 5s', on_click=self.pause_chart)

        self.log.push(f"Auto refresh time: {self.chart_refresh_s}sec")

        """ timers """
        self.cpu_data_timer.append(ui.timer(self.cpu_interval, lambda: self.cpu_datas()))
        self.sys_data_timer.append(ui.timer(self.sys_interval, lambda: self.sys_datas()))
        self.chart_sys_timer = ui.timer(self.chart_refresh_s, lambda: self.update_charts())

    async def  create_charts(self):
        self.cpu_chart = ui.echart({
            'darkMode': 'false',
            'legend': {
                'show': 'true',
                'data': []
            },
            'title': {
                'text': "CPU"
            },
            'tooltip': {
                'trigger': 'axis'
            },
            'xAxis': {
                'type': 'category',
                'data': []
            },
            'yAxis': {
                'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " % " '}
            },
            'series': [{
                'data': [],
                'name': 'CPU %',
                'areaStyle': {'color': '#535894', 'opacity': 0.5},
                'type': 'line'
            }]
        }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

        self.memory_chart = ui.echart({
            'title': {
                'text': "Memory Utilization"
            },
            'xAxis': {
                'type': 'category',
                'data': []
            },
            'tooltip': {
                'trigger': 'axis'
            },
            'yAxis': {
                'min': 0,
                'max': 100,
                'type': 'value'
            },
            'series': [{
                'data': [],
                'type': 'bar',
                'showBackground': 'true',
                'backgroundStyle': {
                    'color': 'rgba(220, 220, 220, 0.8)'
                }
            }]
        }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

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
                }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

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

    async def pause_chart(self):
        ui.notify('Refresh has been paused for 5s ')
        self.log.push('Pause for 5 seconds')
        await asyncio.sleep(5)

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
    """
    Create charts from IPs list
    Detect if WLED device or not
    param: IPs list e.g. '192.168.1.1,192.168.1.5, ...'
    """

    def __init__(self, dev_ips=None, dark: bool = False):
        if dev_ips is None:
            dev_ips = '127.0.0.1'
        self.ips = dev_ips.split(',')
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

        """ ui design """

        with ui.row().classes('no-wrap'):
            self.notify = ui.switch('Notification')
            self.notify.value = True
            self.dark_switch = ui.switch('Dark Mode')
            self.dark_mode = ui.dark_mode()
            if dark:
                self.dark_switch.value = True

        self.create_charts()

        self.ping_data_timer.append(ui.timer(self.pingIntervalS, lambda: self.ping_datas()))

        i = 0
        for ip in self.wled_ips:
            self.wled_data_timer.append(
                ui.timer(self.wled_interval, lambda chart_number=i: self.wled_datas(chart_number)))
            i += 1

        self.chart_ping_timer = ui.timer(self.chart_refresh_s, lambda: self.multi_ping.update())
        self.chart_wled_timer = ui.timer(self.wled_chart_refresh_s, lambda: self.update_wled_charts())

    def create_charts(self):
        self.multi_ping = ui.echart(
            {
                'title': {'text': 'Ping (ms)'},
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': []},
                'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': 'true'},
                'toolbox': {'feature': {'saveAsImage': {}}},
                'xAxis': {'type': 'category', 'data': []},
                'yAxis': {'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " ms " '}},
                'series': []
            }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

        self.multi_signal = ui.echart(
            {
                'title': {'text': 'WLED Signal (%)'},
                'tooltip': {'trigger': 'axis'},
                'legend': {'data': []},
                'grid': {'left': '3%', 'right': '4%', 'bottom': '3%', 'containLabel': 'true'},
                'toolbox': {'feature': {'saveAsImage': {}}},
                'xAxis': {'type': 'category', 'data': []},
                'yAxis': {'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " % " '}},
                'series': []
            }).on('dblclick', lambda: self.pause_chart()).classes('w-full h-45')

        with ui.row():
            for cast_ip in self.ips:
                wled_data = self.get_wled_info(cast_ip)
                ip_exp = ui.expansion(cast_ip, icon='cast') \
                    .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')

                self.multi_ping.options['legend']['data'].append(cast_ip)
                series_data = {'name': cast_ip, 'type': 'line', 'data': []}
                self.multi_ping.options['series'].append(series_data)

                self.multi_signal.options['legend']['data'].append(cast_ip)
                series_data = {'name': cast_ip, 'type': 'line', 'areaStyle': {'color': '#32a84c', 'opacity': 0.5},
                               'data': []}
                self.multi_signal.options['series'].append(series_data)

                with ip_exp:
                    with ui.row():
                        if wled_data == {}:
                            ui.label('Not WLED device').style('background: red')
                        else:
                            self.wled_ips.append(cast_ip)
                            with ui.card().classes('w-full'):
                                self.wled_chart_fps.append(
                                    ui.echart({
                                        'tooltip': {'formatter': '{a} <br/>{b} : {c}'},
                                        'series': [
                                            {'name': 'FramePerSecond',
                                             'type': 'gauge',
                                             'progress': {'show': 'true'},
                                             'detail': {
                                                 'valueAnimation': 'true',
                                                 'formatter': '{value}'
                                             },
                                             'data': [{'value': 0, 'name': 'FPS'}]
                                             }
                                        ]
                                    }).on('dblclick', lambda: self.pause_chart())
                                )
                            with ui.card().classes('w-full'):
                                self.wled_chart_rsi.append(
                                    ui.echart({
                                        'tooltip': {'trigger': 'axis'},
                                        'xAxis': {'type': 'category', 'data': []},
                                        'yAxis': {'type': 'value',
                                                  'axisLabel': {':formatter': 'value =>  "dBm " + value'}},
                                        'legend': {'formatter': 'RSSI', 'textStyle': {'color': 'red'}},
                                        'series': [
                                            {'type': 'line', 'name': cast_ip,
                                             'areaStyle': {'color': '#535894', 'opacity': 0.5}, 'data': []}
                                        ]
                                    }).on('dblclick', lambda: self.pause_chart())
                                )

                    wled_card = ui.card()
                    with ui.row():
                        add_icon = ui.icon('add', size='md').style('cursor: pointer')
                        add_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(True))
                        remove_icon = ui.icon('remove', size='md').style('cursor: pointer')
                        remove_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(False))
                    with wled_card:
                        editor = ui.json_editor({'content': {'json': wled_data}})
                        editor.run_editor_method('updateProps', {'readOnly': True})
                        wled_card.set_visibility(False)

    def pause_chart(self):
        if self.notify.value:
            ui.notify('Refresh has been paused for 5s ')
        self.log.push('Pause for 5 seconds')


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
            response_time = ping(cast_ip, timeout=int(self.maxPingResponseTimeS), unit='ms')
            if response_time is None:
                self.log.push(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip)
                if self.notify.value:
                    ui.notify(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip, type='negative')

                for j, item in enumerate(self.multi_ping.options['series']):
                    self.multi_ping.options['series'][j]['data'].append(0)
            else:
                k = 0
                for item in self.multi_ping.options['series']:
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

        wled_data = self.get_wled_info(cast_ip)

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
            for item in self.multi_signal.options['series']:
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
    def get_wled_info(host, timeout: int = 1):
        """
        Take matrix information from WLED device
        :param host:
        :param timeout:
        :return:
        """
        try:
            url = f'http://{host}/json/info'
            result = requests.get(url, timeout=timeout)
            result = result.json()
        except Exception as error:
            print(f'Not able to get WLED info : {error}')
            result = {}

        return result
