"""
WLEDScheduler py file
"""
"""
required import
"""
# import scheduler
from src.gui.schedulergui import scheduler as sched
from src.gui.schedulergui import WLEDScheduler
# import defined jobs xtra/jobs/jobstosched.py
from src.gui.schedulergui import jobs
# import data from main app, Desktop & Media cast class, t_data_buffer queue class
from mainapp import Desktop, Media, t_data_buffer
"""
end required import
"""
"""
scheduler example (assume job1 exist)
uncomment #WLEDScheduler to use
"""
WLEDScheduler.every(10).seconds.do(sched.send_job_to_queue, jobs.job1).tag('Custom', 'job1')
"""
full schedule help : https://schedule.readthedocs.io/en/stable/examples.html 
"""
"""
Desktop cast with settings from main 
uncomment #Desktop to use
"""
# put stopcast false just to be sure
#Desktop.stopcast=False
# this will initiate the cast class
#Desktop.cast(shared_buffer=t_data_buffer)
"""
Media cast with settings from main 
uncomment #Media to use
"""
# put stopcast false just to be sure
#Media.stopcast=False
# this will initiate the cast class
#Media.cast(shared_buffer=t_data_buffer)
