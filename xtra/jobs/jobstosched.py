"""

JOBS

Instruction:

    create a function with params if necessary
    give it a friendly name
    put your code , no return as this will be executed by the scheduler
    you can use any python command, any WLEDVideoSync classes, methods, Desktop, Media, Text etc ...
    the job will run on its own thread to no block the main one, this mean parallel execution occur
    if you need sequential statement, put all commands into one job
    a defined job could not call another one, but you can define inside function
    pre-defined jobs are provided for Desktop, Media cast

    this provides lots of power, so take care....

"""

def cast_win_desktop(monitor:int = 0):
    """
    Cast entire desktop screen, this is for Win

        : param: monitor: int 0,1, by default use 0
    """
    # import
    from src.cst import desktop
    Desktop = desktop.CASTDesktop()
    # params
    Desktop.stopcast = False
    Desktop.viinput = 'desktop'
    Desktop.monitor_number = monitor
    # run
    Desktop.cast()


def job1(name='test'):
    """
    job1 documentation
    """
    import sys
    import time
    from src.cst import desktop
    Desktop=desktop.CASTDesktop()

    def inside():
        i=0
        for  i in range(10):
            print(i)

    print(f'job1 :{name} ')
    inside()
    print(sys.platform.lower())
    Desktop.stopcast=False
    Desktop.cast()
    time.sleep(10)
    Desktop.stopcast=True
    time.sleep(1)
    print('End of job1')

def job2():
    print('job2')

def job3():
    print('job3')

def job4():
    print('job4')

def job5():
    print('job5')

