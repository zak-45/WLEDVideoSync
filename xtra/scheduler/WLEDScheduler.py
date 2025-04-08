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
"""
end required import
"""
"""
scheduler example (assume job1 exist)
uncomment #WLEDScheduler to use
"""
#WLEDScheduler.every(10).seconds.do(sched.send_job_to_queue, jobs.job1).tag('Custom', 'job1')
"""
full schedule help : https://schedule.readthedocs.io/en/stable/examples.html 
"""

