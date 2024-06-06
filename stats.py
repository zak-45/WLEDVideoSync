#!/usr/bin/env python3
import time
from datetime import datetime
from nicegui import ui
from utils import CASTUtils as Utils
import asyncio

from ping3 import ping

ips = ['192.168.1.170', '192.168.1.2', '192.168.1.254', '192.168.1.161', '192.168.1.167', '192.168.1.51']

maxTimeSec = 600
pingAlertLimitMs = 100
maxPingResponseTimeS = 0.3
chartRefreshS = 2
ip_chart = []
wled_chart_fps = []
wled_chart_rsi = []
wled_ips = []
wled_data_timer = []
wled_interval = 5
ping_data_timer = []
pingIntervalS = 2
multi_ping = None
multi_signal = None


def create_charts():
    global multi_ping, multi_signal

    multi_ping = ui.echart(
        {
            'title': {
                'text': 'Ping (ms)'
            },
            'tooltip': {
                'trigger': 'axis'
            },
            'legend': {
                'data': []
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': 'true'
            },
            'toolbox': {
                'feature': {
                    'saveAsImage': {}
                }
            },
            'xAxis': {
                'type': 'category',
                'data': []
            },
            'yAxis': {
                'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " ms " '}
            },
            'series': [
            ]
        }).on('dblclick', lambda: pause_chart()).classes('w-full h-45')

    multi_signal = ui.echart(
        {
            'title': {
                'text': 'WLED Signal (%)'
            },
            'tooltip': {
                'trigger': 'axis'
            },
            'legend': {
                'data': []
            },
            'grid': {
                'left': '3%',
                'right': '4%',
                'bottom': '3%',
                'containLabel': 'true'
            },
            'toolbox': {
                'feature': {
                    'saveAsImage': {}
                }
            },
            'xAxis': {
                'type': 'category',
                'data': []
            },
            'yAxis': {
                'type': 'value', 'axisLabel': {':formatter': 'value =>  value + " % " '}
            },
            'series': [
            ]
        }).on('dblclick', lambda: pause_chart()).classes('w-full h-45')

    with ui.row():
        for cast_ip in ips:
            wled_data = asyncio.run(Utils.get_wled_info(cast_ip))
            ip_exp = ui.expansion(cast_ip, icon='cast') \
                .classes('shadow-[0px_1px_4px_0px_rgba(0,0,0,0.5)_inset]')

            """ multi line IP Ping """

            multi_ping.options['legend']['data'].append(cast_ip)
            series_data = {
                'name': cast_ip,
                'type': 'line',
                'data': []
            }
            multi_ping.options['series'].append(series_data)

            """ multi line Signal """

            multi_signal.options['legend']['data'].append(cast_ip)
            series_data = {
                'name': cast_ip,
                'type': 'line',
                'areaStyle': {'color': '#32a84c', 'opacity': 0.5},
                'data': []
            }
            multi_signal.options['series'].append(series_data)

            """ additional WLED Graphs """
            with ip_exp:
                with ui.row():
                    if wled_data == {}:
                        ui.label('Not WLED device').style('background: red')

                    else:
                        wled_ips.append(cast_ip)

                        wled_card = ui.card()
                        wled_card.set_visibility(False)
                        with wled_card:
                            editor = ui.json_editor({'content': {'json': wled_data}})
                            editor.run_editor_method('updateProps', {'readOnly': True})

                        add_icon = ui.icon('add', size='md').style('cursor: pointer')
                        add_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(True))
                        remove_icon = ui.icon('remove', size='md').style('cursor: pointer')
                        remove_icon.on('click', lambda wled_card=wled_card: wled_card.set_visibility(False))

                        """ wled FPS """
                        wled_chart_fps.append(
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
                            }).on('dblclick', lambda: pause_chart())
                        )

                        """ wled rssi """
                        wled_chart_rsi.append(
                            ui.echart({
                                'tooltip': {'trigger': 'axis'},
                                'xAxis': {'type': 'category',
                                          'data': []},
                                'yAxis': {'type': 'value',
                                          'axisLabel': {':formatter': 'value =>  value + " dBm " '}},
                                'legend': {'formatter': 'RSSI', 'textStyle': {'color': 'red'}},
                                'series': [
                                    {'type': 'line',
                                     'name': cast_ip,
                                     'areaStyle': {'color': '#535894', 'opacity': 0.5},
                                     'data': []}
                                ]}).on('dblclick', lambda: pause_chart())
                        )


def pause_chart():
    ui.notify('Refresh has been paused for 5s ')
    log.push('Pause for 5 seconds')
    time.sleep(5)


def clear():
    n = 0
    for cast_ip in ips:
        multi_ping.options['series'][n]['data'].clear()
        multi_signal.options['series'][n]['data'].clear()
        n += 1

    multi_ping.options['xAxis']['data'] = []
    multi_signal.options['xAxis']['data'] = []

    log.clear()
    log.push("Auto refresh time: " + str(chartRefreshS) + "sec")


async def ping_datas():
    global ips, conn, c, maxTimeSec, maxResponseTimeMs

    now = datetime.now()
    date_time_str = now.strftime("%H:%M:%S")

    for cast_ip in ips:
        response_time = ping(cast_ip, timeout=maxPingResponseTimeS, unit='ms')
        if response_time is None:
            log.push(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip)
            ui.notify(datetime.now().strftime('%H:%M:%S') + " no ping reply from " + cast_ip, type='negative')

            j = 0
            for item in multi_ping.options['series']:
                multi_ping.options['series'][j]['data'].append(0)
                j += 1

        else:

            k = 0
            for item in multi_ping.options['series']:
                if multi_ping.options['series'][k]['name'] == cast_ip:
                    multi_ping.options['series'][k]['data'].append(round(response_time, 2))
                    break
                k += 1

            """
            if len(ip_chart[i].options['series'][0]['data']) > maxTimeSec:
                ip_chart[i].options['series'][0]['data'].pop(0)
            """

            if response_time > pingAlertLimitMs:
                log.push(datetime.now().strftime('%H:%M:%S') + " high ping reply time from " + cast_ip + " > " + str(
                    response_time) + " ms")

    multi_ping.options['xAxis']['data'].append(date_time_str)


async def wled_datas(i):
    global wled_ips, conn, c, maxTimeSec, maxResponseTimeMs

    cast_ip = wled_ips[i]

    now = datetime.now()
    date_time_str = now.strftime("%H:%M:%S")

    wled_data = await Utils.get_wled_info(cast_ip)

    if wled_data == {}:
        log.push(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip)
        ui.notify(datetime.now().strftime('%H:%M:%S') + " no data from " + cast_ip, type='negative')

        wled_chart_fps[i].options['series'][0]['data'].append(0)
        wled_chart_rsi[i].options['series'][0]['data'].append(0)

        j = 0
        for item in multi_signal.options['series']:
            multi_signal.options['series'][j]['data'].append(0)
            j += 1


    else:
        wled_chart_rsi[i].options['series'][0]['data'].append(wled_data['wifi']['rssi'])
        wled_chart_rsi[i].options['xAxis']['data'].append(date_time_str)

        wled_chart_fps[i].options['series'][0]['data'][0]['value'] = wled_data['leds']['fps']

        k = 0
        for item in multi_signal.options['series']:
            if multi_signal.options['series'][k]['name'] == cast_ip:
                multi_signal.options['series'][k]['data'].append(wled_data['wifi']['signal'])
                break
            k += 1

    if i == 0:
        multi_signal.options['xAxis']['data'].append(date_time_str)


def update_wled_charts():
    global ips, conn, c, maxTimeSec, maxResponseTimeMs, fps

    i = 0
    for cast_ip in wled_ips:
        wled_chart_rsi[i].update()
        wled_chart_fps[i].update()
        i += 1

    multi_signal.update()


# Create all charts
create_charts()

# log info
log = ui.log(max_lines=30).classes('w-full h-20 bg-black text-white')

# buttons
with ui.row():
    ui.button('Clear all', on_click=clear)
    ui.button('Pause 5s', on_click=pause_chart)

# create timers to grab data & refresh charts
ping_data_timer.append(ui.timer(pingIntervalS, lambda: ping_datas()))

i = 0
for ip in wled_ips:
    wled_data_timer.append(ui.timer(wled_interval, lambda chart_number=i: wled_datas(chart_number)))
    i += 1

chart_ping_timer = ui.timer(chartRefreshS, lambda: multi_ping.update())
chart_wled_timer = ui.timer(chartRefreshS, lambda: update_wled_charts())

# start
log.push("Auto refresh time: " + str(chartRefreshS) + "sec")

ui.run(title="Stats Charts", show="False", favicon="📶")
