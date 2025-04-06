
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

