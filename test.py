from nicegui import ui, Client

@ui.page('/')
async def index(client: Client):
    ui.add_body_html('<script src="https://unpkg.com/@rive-app/canvas@2.1.0"></script>')
    ui.html('<canvas id="canvas" width="500" height="500"></canvas>')
    await client.connected()
    await ui.run_javascript(r'''
        const r = new rive.Rive({
            src: "https://cdn.rive.app/animations/vehicles.riv",
            canvas: document.getElementById("canvas"),
            autoplay: true,
            stateMachines: "bumpy",
            onLoad: () => {
            r.resizeDrawingSurfaceToCanvas();
            },
        });
        ''')

ui.run()