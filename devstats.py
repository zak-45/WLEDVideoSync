#!/usr/bin/env python3
import time
from datetime import datetime
from nicegui import ui
from utils import CASTUtils as Utils
import asyncio
from ping3 import ping


class DevCharts:
    def __init__(self, dev_ips=None):
        if dev_ips is None:
            dev_ips = []
        self.ips = dev_ips.split(',')
        self.maxTimeSec = 600
        self.pingAlertLimitMs = 100
        self.maxPingResponseTimeS = 0.3
        self.chartRefreshS = 2
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
        self.notify = ui.switch('Notification')
        self.notify.value = True

        print(self.ips)
        self.create_charts()

        self.ping_data_timer.append(ui.timer(self.pingIntervalS, lambda: self.ping_datas()))

        i = 0
        for ip in self.wled_ips:
            self.wled_data_timer.append(
                ui.timer(self.wled_interval, lambda chart_number=i: self.wled_datas(chart_number)))
            i += 1

        self.chart_ping_timer = ui.timer(self.chartRefreshS, lambda: self.multi_ping.update())
        self.chart_wled_timer = ui.timer(self.chartRefreshS, lambda: self.update_wled_charts())

        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            ui.button('Pause 5s', on_click=self.pause_chart)
        self.log.push("Auto refresh time: " + str(self.chartRefreshS) + "sec")

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
                wled_data = asyncio.run(Utils.get_wled_info(cast_ip))
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
                            wled_card = ui.card()
                            wled_card.set_visibility(False)
                            with wled_card:
                                editor = ui.json_editor({'content': {'json': wled_data}})
                                editor.run_editor_method('updateProps', {'readOnly': True})

                            add_icon = ui.icon('add', size='md').style('cursor: pointer')
                            add_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(True))
                            remove_icon = ui.icon('remove', size='md').style('cursor: pointer')
                            remove_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(False))

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

                            self.wled_chart_rsi.append(
                                ui.echart({
                                    'tooltip': {'trigger': 'axis'},
                                    'xAxis': {'type': 'category', 'data': []},
                                    'yAxis': {'type': 'value',
                                              'axisLabel': {':formatter': 'value =>  value + " dBm " '}},
                                    'legend': {'formatter': 'RSSI', 'textStyle': {'color': 'red'}},
                                    'series': [
                                        {'type': 'line', 'name': cast_ip,
                                         'areaStyle': {'color': '#535894', 'opacity': 0.5}, 'data': []}
                                    ]
                                }).on('dblclick', lambda: self.pause_chart())
                            )

    def pause_chart(self):
        if self.notify.value:
            ui.notify('Refresh has been paused for 5s ')
        self.log.push('Pause for 5 seconds')
        time.sleep(5)

    def clear(self):
        n = 0
        for cast_ip in self.ips:
            self.multi_ping.options['series'][n]['data'].clear()
            self.multi_signal.options['series'][n]['data'].clear()
            n += 1

        self.multi_ping.options['xAxis']['data'] = []
        self.multi_signal.options['xAxis']['data'] = []

        self.log.clear()
        self.log.push("Auto refresh time: " + str(self.chartRefreshS) + "sec")

    async def ping_datas(self):
        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        for cast_ip in self.ips:
            response_time = ping(cast_ip, timeout=self.maxPingResponseTimeS, unit='ms')
            if response_time is None:
                self.log.push(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip)
                if self.notify.value:
                    ui.notify(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip, type='negative')

                j = 0
                for item in self.multi_ping.options['series']:
                    self.multi_ping.options['series'][j]['data'].append(0)
                    j += 1
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

    async def wled_datas(self, i):
        cast_ip = self.wled_ips[i]

        now = datetime.now()
        date_time_str = now.strftime("%H:%M:%S")

        wled_data = await Utils.get_wled_info(cast_ip)

        if wled_data == {}:
            self.log.push(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip)
            if self.notify.value:
                ui.notify(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip, type='negative')

            self.wled_chart_fps[i].options['series'][0]['data'].append(0)
            self.wled_chart_rsi[i].options['series'][0]['data'].append(0)

            j = 0
            for item in self.multi_signal.options['series']:
                self.multi_signal.options['series'][j]['data'].append(0)
                j += 1
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

    def update_wled_charts(self):
        i = 0
        for cast_ip in self.wled_ips:
            self.wled_chart_rsi[i].update()
            self.wled_chart_fps[i].update()
            i += 1

        self.multi_signal.update()
