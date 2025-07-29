"""
a: zak-45
d: 01/04/2025
v: 1.0.0

Overview
This Python code implements a Scheduler class for managing and running jobs asynchronously using a queue and
multiple worker threads. It leverages the schedule library for scheduling tasks and a queue to handle job execution.
The scheduler supports multiple worker threads to process jobs concurrently.
The ConfigManager is used for logging purposes.

Key Components
    Scheduler Class: This class is the core of the code, providing methods for starting, stopping, and managing the
    job queue and worker threads.

    __init__: Initializes the scheduler with a specified number of worker threads and queue size.

    main_worker: The function executed by each worker thread.
    It retrieves jobs from the queue and executes them in separate daemon threads.

    start: Starts the scheduler, creating and launching worker threads and a background thread to process scheduled jobs.

    stop: Stops the scheduler, gracefully terminating worker threads and the background scheduling thread.

    send_job_to_queue: Adds a job (a callable function with its arguments) to the job queue.

schedule Library: Used for scheduling jobs at specific intervals or times. The every method is used to define
recurring jobs.

queue.Queue: Used to store jobs waiting to be executed by worker threads. This ensures that jobs are processed in an
orderly manner.

ConfigManager: Handles logging operations, providing a consistent way to record events and errors within the scheduler.

Worker Threads: Multiple worker threads are created to process jobs concurrently, improving performance.
Each worker thread runs the main_worker function.

"""

from typing import Callable
import threading
import time
import queue
import schedule

from configmanager import LoggerManager

logger_manager = LoggerManager(logger_name='WLEDLogger.scheduler')
scheduler_logger = logger_manager.logger


class Scheduler:
    """
    Manages and runs jobs asynchronously using a queue and multiple worker threads.

    This class uses the `schedule` library for scheduling tasks and a queue to handle job execution.
    It supports multiple worker threads to process jobs concurrently.
    """

    def __init__(self, num_workers=1, queue_size: int = 99):
        """
        Initializes the scheduler with a specified number of worker threads and queue size.

        Creates a job queue, a scheduler instance, and sets the number of worker threads.
        """
        self.bg_thread = None
        self.worker_threads = []  # List to store worker threads
        self.bg_stop = None
        self.is_running = False
        self.job_queue = queue.Queue(maxsize=queue_size)
        self.scheduler = schedule.Scheduler()
        self.num_workers = num_workers  # Number of worker threads

    def main_worker(self):
        """
        Worker thread function to process jobs from the queue.

        Retrieves jobs from the queue and executes them in separate daemon threads.
        """
        while not self.bg_stop.is_set():
            try:
                job_func, args, kwargs = self.job_queue.get(timeout=.1)
                job_thread = threading.Thread(target=job_func, args=args, kwargs=kwargs)
                job_thread.daemon = True
                job_thread.start()
                scheduler_logger.info(f'Scheduler run function: {job_func.__name__} in thread: {job_thread} '
                                    f'from worker: {threading.current_thread()}')
                self.job_queue.task_done()
            except queue.Empty:
                pass
            except Exception as er:
                scheduler_logger.error(f'Error to run job in thread : {er}')

    def stop(self):
        """
        Stops the scheduler, gracefully terminating worker threads and the background scheduling thread.

        Sets the stop event, joins worker threads and the background thread, and logs relevant information.
        """
        self.is_running = False
        if self.bg_stop:
            self.bg_stop.set()
        # Stop all worker threads
        for worker_thread in self.worker_threads:
            worker_thread.join()
        # stop main thread
        if self.bg_thread:
            self.bg_thread.join()
        #
        scheduler_logger.info(f'stop worker(s): {self.worker_threads}')
        scheduler_logger.info(f'stop scheduler: {self.bg_thread}')
        jobs = self.scheduler.get_jobs()
        scheduler_logger.info(f'Number of job(s) submitted : {len(jobs)}')
        scheduler_logger.info(f'Name   of job(s) to run    : {jobs}')

    def start(self, delay=.1):
        """
        Starts the scheduler, creating and launching worker threads and a background thread to process scheduled jobs.

        Initializes worker threads and a background thread to run scheduled jobs.
        If the scheduler is already running, logs an error and returns.

        params:
        :delay : time to sleep before checking new jobs
        """

        if self.is_running:
            scheduler_logger.error('Scheduler is already running')
            return

        self.bg_stop = threading.Event()
        self.is_running = True

        # Create and start multiple worker threads
        self.worker_threads = []
        for _ in range(self.num_workers):
            worker_thread = threading.Thread(target=self.main_worker)
            worker_thread.daemon = True
            self.worker_threads.append(worker_thread)
            worker_thread.start()

        class ScheduleThread(threading.Thread):
            def __init__(self, scheduler, bg_stop, s_delay):
                super().__init__()
                self.scheduler = scheduler
                self.bg_stop = bg_stop
                self.delay = s_delay
                self.daemon = True

            def run(self):
                while not self.bg_stop.is_set():
                    self.scheduler.run_pending()
                    time.sleep(self.delay)

        self.bg_thread = ScheduleThread(self.scheduler, self.bg_stop, delay)
        self.bg_thread.start()
        scheduler_logger.info(f'start scheduler: {self.bg_thread}')

    def send_job_to_queue(self, job: Callable, *args, **kwargs):
        """
        Adds a job to the job queue.

        Puts the specified job function and its arguments into the queue for asynchronous execution by a worker thread.
        in case of queue error, no retry so job is lost.
        """
        try:
            self.job_queue.put((job, args, kwargs), block=False)  # block=False to prevent blocking if the queue is full
        except queue.Full:
            scheduler_logger.error(f'Schedule not executed, queue is full : {self.job_queue.qsize()}, no more entries accepted')


if __name__ == "__main__":
    def my_test(name: str = 'default'):
        scheduler_logger.info(f'this is a test function using this value : {name}, '
                            f'running on : {threading.current_thread()}')


    scheduler_logger.info('start main')
    # limit queue to 2 entries
    my_scheduler = Scheduler(num_workers=2, queue_size=2)
    # add some jobs
    my_scheduler.scheduler.every(4).seconds.do(my_scheduler.send_job_to_queue, my_test, name='test1')
    my_scheduler.scheduler.every(4).seconds.do(my_scheduler.send_job_to_queue, my_test, name='test2')
    my_scheduler.scheduler.every(4).seconds.do(my_scheduler.send_job_to_queue, my_test, name='test3')
    my_scheduler.scheduler.every(4).seconds.do(my_scheduler.send_job_to_queue, my_test, name='test4')
    my_scheduler.scheduler.every(4).seconds.do(my_scheduler.send_job_to_queue, my_test)
    # start scheduler
    scheduler_logger.info('start scheduler')
    my_scheduler.start()
    # some sleep to let it do some work
    time.sleep(8)
    # stop scheduler
    scheduler_logger.info('stop scheduler')
    my_scheduler.stop()
    time.sleep(1)
    # clear jobs
    scheduler_logger.info('we clean all jobs')
    my_scheduler.scheduler.clear()
    my_scheduler.stop()
    time.sleep(1)
    scheduler_logger.info('stop main')
