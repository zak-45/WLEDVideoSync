"""

JOBS

Instruction:

    create a function with params if necessary
    give it a friendly name
    put your code , no return as this will be executed by the scheduler
    you can use any python command, any WLEDVideoSync classes, methods, Desktop, Media, Text etc ...
    the job will run on its own thread to no block the main one, this mean parallel execution occur
    if you need sequential statement, put all commands into one job
    pre-defined jobs are provided for Desktop, Media cast

    this give lots of power, so take care....

"""

def cast_win_main_desktop(monitor:int = 0):
    """
    Cast entire desktop screen, this is for Win
    This one take mainapp context

        : param: monitor: int 0,1, by default use 0
    """
    # import
    from mainapp import Desktop, t_data_buffer
    # params
    Desktop.stopcast = False
    Desktop.viinput = 'desktop'
    Desktop.monitor_number = monitor
    # run
    Desktop.cast(shared_buffer=t_data_buffer)

def cast_win_alone_desktop(monitor:int = 0):
    """
    Cast entire desktop screen, this is for Win
    This one run on its own context

        : param: monitor: int 0,1, by default use 0
    """
    # import
    from src.cst import desktop
    # import t_data_buffer to be able to get info from it
    from mainapp import t_data_buffer
    # instantiate
    Desktop=desktop.CASTDesktop()
    # params
    Desktop.stopcast = False
    Desktop.viinput = 'desktop'
    Desktop.monitor_number = monitor
    # run
    Desktop.cast(shared_buffer=t_data_buffer)


def cast_win_main_media(device_number:int = 0):
    """
    Cast data from device x, this is for Win
    This one take mainapp context
    Device depend on your OS configuration. 
    Win give 0 to default USB Webcam

    :param: device_number : int 0,xxx, by default use 0

    """
    # import
    from mainapp import Media, t_data_buffer
    # params
    Media.stopcast = False
    Media.viinput = device_number
    # run
    Media.cast(shared_buffer=t_data_buffer)


def job1(name='test'):
    """
    job1 documentation
    will run for 10 seconds and cast desktop
    """
    import sys
    import time
    from mainapp import Desktop, t_data_buffer

    def inside():
        i=0
        for  i in range(10):
            print(i)

    print(f'job1 :{name} ')
    # inside function
    inside()
    # call another job
    job3()
    # cast desktop
    print(sys.platform.lower())
    Desktop.stopcast=False
    Desktop.cast()
    time.sleep(10)
    Desktop.stopcast=True
    time.sleep(1)
    print('End of job1')

def job2(name='test'):
    """
    job2 documentation
    will run for 10 seconds and cast media
    """
    import sys
    import time
    from mainapp import Media, t_data_buffer    

    def inside():
        i=0
        for  i in range(10):
            print(i)

    print(f'job2 :{name} ')
    # inside function
    inside()
    # call another job
    job3()
    # cast desktop
    print(sys.platform.lower())
    Media.stopcast=False
    Media.cast()
    time.sleep(10)
    Media.stopcast=True
    time.sleep(1)
    print('End of job2')


def job3():
    print('Inside job3')

def job4():
    """
    will run already defined jobs in sequential order
    """
    from time import sleep
    cast_win_main_desktop()
    sleep(5)
    cast_win_main_media()
    sleep(5)
    job1()
    sleep(5)
    job2()

    
print('End of jobs files')
