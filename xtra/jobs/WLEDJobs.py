"""
a:zak-45
d:01/08/2025
v:1.0.0.0

The WLEDJobs.py file is a user-extendable module designed to define custom, schedulable tasks (jobs) for the
WLEDVideoSync application. It acts as a powerful scripting interface where users can write their own Python functions
to automate complex sequences of actions, such as starting and stopping casts, applying presets, or interacting with
the application's core components at specific times or intervals.The scheduler, configured in schedulergui.py, reads
this file and allows the user to trigger these defined functions (jobs) on a schedule. Each job is executed in its
own thread to ensure it doesn't block the main application's UI.

1. Job Definition

Each Python function defined in this file is treated as a distinct "job" that the scheduler can execute.
The file comes with several pre-defined examples (cast_win_main_desktop, job1, etc.) that serve as templates for users
to create their own.

2. Accessing Application Components

The jobs demonstrate two primary ways to interact with the main application's casting objects (Desktop, Media):
 •Using the Main Application Context:
  •Functions like cast_win_main_desktop import Desktop and Media directly from mainapp.
  •Example: from mainapp import Desktop, t_data_buffer
  •Effect: This approach modifies the live, existing instance of the Desktop or Media class that the main GUI is also
  using. This is the most common and recommended way to control casts that are already configured in the UI.

 •Running in an Independent Context:
  •Functions like cast_win_alone_desktop import the class definition from its source file (src.cst.desktop) and create
  a new, independent instance of it.
  •Example: from src.cst import desktop; Desktop=desktop.CASTDesktop()
  •Effect: This creates a completely separate casting process with its own default parameters.
  It will not affect the state of the Desktop object shown in the main UI. This is useful for running isolated,
  background tasks that shouldn't interfere with the user's current settings.

3. Job Orchestration
The file demonstrates how to create simple, single-action jobs as well as more complex ones that can call other jobs.

 •Simple Jobs: cast_win_main_desktop is a simple job that performs one primary action: starting a desktop cast.
 •Complex Jobs: job1 shows a multi-step process: it prints messages, calls another job (job3), and then starts and stops
  a cast with a time.sleep() delay in between.
 •Sequential Execution: job4 illustrates how to create a "master" job that runs several other jobs in a specific
 sequence, with delays. This is powerful for creating automated shows or test sequences.

4. Parameterization
Jobs can be defined with parameters and default values (e.g., def cast_win_main_desktop(monitor:int = 0):). This makes
them highly reusable. When setting up a schedule in the GUI, the user can provide specific values for these parameters.


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

def my_complex_job():
    """
    A more robust job with error handling.
    """
    from mainapp import Desktop, main_logger
    import time
    try:
        main_logger.info("Starting my complex job...")
        # ... code that might fail ...
        Desktop.stopcast = False
        Desktop.cast()
        time.sleep(20)
        Desktop.stopcast = True
        main_logger.info("Complex job finished successfully.")
    except Exception as e:
        # Log the error so it appears in the main application log
        main_logger.error(f"An error occurred in my_complex_job: {e}", exc_info=True)
    finally:
        # Ensure cleanup happens even if there's an error
        Desktop.stopcast = True
        main_logger.info("my_complex_job cleanup complete.")


print('End of jobs files')
