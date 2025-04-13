"""
WLEDScheduler py file
"""
"""
required import
"""
# import scheduler
from src.gui.schedulergui import WLEDScheduler, scheduler
# import defined jobs xtra/jobs/jobstosched.py
from src.gui.schedulergui import jobs
"""
end required import
"""
"""
scheduler example (assume job2 exist)
uncomment #WLEDScheduler to use
"""

#WLEDScheduler.every(10).seconds.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

"""
full schedule help : https://schedule.readthedocs.io/en/stable/examples.html 
"""

print('End of custom schedules file')
