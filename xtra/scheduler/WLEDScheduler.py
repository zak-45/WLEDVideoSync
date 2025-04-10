"""
WLEDScheduler py file
"""
"""
required import
"""
# import scheduler
from src.gui.schedulergui import scheduler as sched
# import defined jobs xtra/jobs/jobstosched.py
from src.gui.schedulergui import jobs
"""
end required import
"""
"""
scheduler example (assume job1 exist)
uncomment #sched.scheduler to use
"""

#sched.scheduler.every(10).seconds.do(sched.send_job_to_queue, jobs.job1).tag('Custom', 'job1')

"""
full schedule help : https://schedule.readthedocs.io/en/stable/examples.html 
"""

