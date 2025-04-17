"""
WLEDScheduler py file

full schedule help : https://schedule.readthedocs.io/en/stable/examples.html

"""
#required import
#scheduler
from src.gui.schedulergui import WLEDScheduler, scheduler
#defined jobs xtra/jobs/WLEDJobs.py
from src.gui.schedulergui import jobs
#end required import

"""
scheduler examples (assume job2 exist)
uncomment #WLEDScheduler to use
"""
# Run job every 3 second/minute/hour/day/week,
# Starting 3 second/minute/hour/day/week from now
#WLEDScheduler.every(3).seconds.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every(3).minutes.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every(3).hours.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every(3).days.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every(3).weeks.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

# Run job every minute at the 23rd second
#WLEDScheduler.every().minute.at(":23").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

# Run job every hour at the 42nd minute
#WLEDScheduler.every().hour.at(":42").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

# Run jobs every 5th hour, 20 minutes and 30 seconds in.
# If current time is 02:00, first execution is at 06:20:30
#WLEDScheduler.every(5).hours.at("20:30").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

# Run job every day at specific HH:MM and next HH:MM:SS
#WLEDScheduler.every().day.at("10:30").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every().day.at("10:30:42").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every().day.at("12:42", "Europe/Amsterdam").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

# Run job on a specific day of the week
#WLEDScheduler.every().monday.do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')
#WLEDScheduler.every().wednesday.at("13:15").do(scheduler.send_job_to_queue, jobs.job2).tag('Custom', 'job2')

print('End of custom schedules file')
