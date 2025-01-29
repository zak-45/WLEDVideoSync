from nicegui import ui, app

app.add_static_files('/path_in_webserver', r'C:\Windows\Fonts')

ui.add_head_html(r'''
<style>
@font-face{
    font-family: "my font";
    src: url('/path_in_webserver/vladimir.ttf') format('truetype');
    font-weight: normal;
    font-style: normal;
}
</style>
''')

ui.label('hello').style('font-family: "my font"; font-size: 140px; font-weight: bold;')

with ui.button('world').style('font-family: "my font"; font-size: 40px; font-weight: bold;'):
    ui.badge("0", color='red').props('floating').style('font-family: "my font"; font-size: 1em; font-weight: bold;')

ui.run()