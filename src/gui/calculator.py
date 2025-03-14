# thanks to  : https://github.com/suspiciousRaccoon/NiceGUI-Calculator

from math import sqrt
from nicegui import ui
from simpleeval import simple_eval


class Calculator:
    def __init__(self):
        self.data = '0'
        self.memory = ''
        self.default = True
        self.setup_gui()

    def add_data(self, data_to_add) -> None:
        if all(x in ['*', '/', '%'] for x in [self.data[-1], data_to_add]):
            return
        elif self.default:
            self.data = self.data.replace('0', data_to_add)
            self.default = False
        else:
            self.data += data_to_add

    def remove_data(self, remove_all) -> None:
        if remove_all or len(self.data) <= 1:
            self.data = '0'
            self.default = True
        else:
            self.data = self.data[:-1]

    def calculate(self):
        try:
            self.data = str(round(simple_eval(self.data), 7))
        except SyntaxError:
            ui.notify('The operation is not possible')
        except Exception as error:
            ui.notify(f'error {error}')

    def calculate_sqrt(self):
        self.calculate()
        self.data = str(round(sqrt(self.data), 7))

    def memory_clear(self):
        self.memory = ''

    def memory_recall(self):
        if self.memory:
            self.add_data(self.memory)

    def memory_modify(self, operation):
        print(self.memory)
        if self.memory:
            self.memory = str(simple_eval(
                f'{self.memory} {operation} {self.data}'))
        else:
            self.memory = str(simple_eval(f'0 {operation} {self.data}'))
        if self.memory == '0':
            self.memory = ''

    def setup_gui(self) -> None:

        with ui.card().classes('flex mx-auto mt-40'):
            ui.icon('sim_card', color='primary').bind_visibility_from(
                self, 'memory')
            ui.input().bind_value(self, 'data').props(
                'outlined input-style="text-align:right"').tailwind('min-w-full')
            with ui.grid(columns=5):
                ui.button('\u221A', on_click=self.calculate_sqrt)
                ui.button('MC', on_click=self.memory_clear)
                ui.button('MR', on_click=self.memory_recall)
                ui.button('M-', on_click=lambda: self.memory_modify('-'))
                ui.button('M+', on_click=lambda: self.memory_modify('+'))
                # ///////////////
                ui.button('%', on_click=lambda: self.add_data('%'))
                ui.button('7', on_click=lambda: self.add_data('7'))
                ui.button('8', on_click=lambda: self.add_data('8'))
                ui.button('9', on_click=lambda: self.add_data('9'))
                ui.button('/', on_click=lambda: self.add_data('/'))
                # ////////////
                # im not sure what is the purpose of this, it doesn't seem to change functionality in a normal calculator
                ui.button('\u00B1', on_click=lambda: self.add_data('-'))
                ui.button('4', on_click=lambda: self.add_data('4'))
                ui.button('5', on_click=lambda: self.add_data('5'))
                ui.button('6', on_click=lambda: self.add_data('6'))
                ui.button('*', on_click=lambda: self.add_data('*'))
                # ////////////
                ui.button('C', on_click=lambda: self.remove_data(False))
                ui.button('1', on_click=lambda: self.add_data('1'))
                ui.button('2', on_click=lambda: self.add_data('2'))
                ui.button('3', on_click=lambda: self.add_data('3'))
                ui.button('-', on_click=lambda: self.add_data('-'))
                # ////////////
                ui.button('CE', on_click=lambda: self.remove_data(True))
                ui.button('0', on_click=lambda: self.add_data('0'))
                ui.button('\u00B7', on_click=lambda: self.add_data('.'))
                ui.button('=', on_click=self.calculate)
                ui.button('+', on_click=lambda: self.add_data('+'))

# example usage
if __name__ in {"__main__", "__mp_main__"}:
    from nicegui import app

    ui.label('Calculator Example').classes('self-center text-2xl font-bold')
    calculator = Calculator()
    ui.button('shutdown', on_click=app.shutdown).classes('self-center')
    ui.run(reload=False)