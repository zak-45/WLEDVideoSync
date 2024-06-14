#!/usr/bin/env python3
import time
from datetime import datetime
import psutil
from nicegui import app, ui


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
            if dark is True:
                self.dark_switch.value = True

        self.create_charts()
        self.log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')
        with ui.row():
            ui.button('Clear all', on_click=self.clear)
            ui.button('Pause 5s', on_click=self.pause_chart)
        self.log.push("Auto refresh time: " + str(self.chart_refresh_s) + "sec")

        """ timers """
        self.net_data_timer.append(ui.timer(self.net_interval, lambda: self.net_datas()))
        self.chart_net_timer = ui.timer(self.chart_refresh_s, lambda: self.multi_net.update())

        app.native.window_args['resizable'] = True
        app.native.start_args['debug'] = False
        app.native.settings['ALLOW_DOWNLOADS'] = True

        ui.run(native=True, window_size=(800, 600), fullscreen=False, reload=False)

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
        time.sleep(5)

    def clear(self):
        self.multi_net.options['series'][0]['data'].clear()
        self.multi_net.options['series'][1]['data'].clear()
        self.multi_net.options['xAxis']['data'] = []
        self.log.clear()
        self.log.push("Auto refresh time: " + str(self.chart_refresh_s) + "sec")

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


if __name__ == "__main__":
    NetCharts()
