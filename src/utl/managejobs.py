import ast
from types import FunctionType
from configmanager import ConfigManager
cfg_mgr = ConfigManager(logger_name='WLEDLogger.scheduler')

class JobWrapper:
    def __init__(self, func: FunctionType, source: str):
        self._func = func
        self._source = source

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def view(self):
        return self._source

    def doc(self):
        return self._func.__doc__ or self._source.split('\n')[0]


def load_jobs_with_view(filename, class_name="Jobs"):
    with open(filename, 'r') as f:
        source = f.read()

    tree = ast.parse(source, filename)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

    module_ast = ast.Module(body=functions, type_ignores=[])
    compiled = compile(module_ast, filename="<ast>", mode="exec")

    namespace = {}
    exec(compiled, namespace)

    lines = source.splitlines()
    func_sources = {}
    for func in functions:
        start = func.lineno - 1
        end = func.end_lineno
        func_source = "\n".join(lines[start:end])
        func_sources[func.name] = func_source

    # Create wrapped jobs
    wrapped_jobs = {
        name: JobWrapper(func, func_sources[name])
        for name, func in namespace.items()
        if callable(func)
    }

    # Define the class
    class Jobs:
        def __init__(self):
            for name, job in wrapped_jobs.items():
                setattr(self, name, job)

        @property
        def list(self):
            return list(wrapped_jobs.keys())

        def help(self):
            for name, job in wrapped_jobs.items():
                print(f"• {name}: {job.doc()}")

        def search(self, query):
            return [name for name in self.list if query.lower() in name.lower()]

    return Jobs

if __name__ == '__main__':
    Jobs=load_jobs_with_view(cfg_mgr.app_root_path('xtra/jobs/jobstosched.py'))
    jobs=Jobs()
    print(20*'-> ' + 'List all jobs defined in jobstosched.py')
    print(jobs.list)
    print(20*'-> ' + 'provide some help')
    print(jobs.help())
    print(20*'-> ' + 'view source file for job1')
    print(jobs.job1.view())
    print(20*'-> ' + 'execute job1')
    jobs.job1(name='test from main')
