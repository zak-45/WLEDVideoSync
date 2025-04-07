"""
Overview
This Python file provides a mechanism to dynamically load and manage user-defined jobs from a specified Python file. 
It parses the file, extracts function definitions, wraps them into callable JobWrapper objects, and makes them 
accessible through a dynamically generated Jobs class. This allows users to define jobs in a separate file and 
easily access, execute, and manage them within the main application.

Key Components

    JobWrapper Class: This class encapsulates each user-defined function. 
    It stores the original function, its source code, and provides methods for execution (__call__), 
    viewing the source code (view), retrieving the docstring (doc), and accessing function metadata 
    (e.g., __name__, __doc__). This wrapper allows the functions to be treated as managed "jobs".

    load_jobs Function: This function is the core of the module. 
    It takes a filename and an optional class name as input. It reads the specified file, parses the 
    Abstract Syntax Tree (AST) to extract function definitions, compiles them into executable code, 
    and creates a Jobs class dynamically. The Jobs class instances provide access to the wrapped jobs.

    Dynamically Generated Jobs Class: This class is created at runtime by load_jobs. 
    It contains the loaded jobs as methods, allowing users to call them directly (e.g., jobs.job1()). 
    It also provides utility methods like list (to list available jobs), help (to display job docstrings), 
    and search (to find jobs by name).

    Configuration Integration (ConfigManager): The script uses ConfigManager to determine the path to the jobs file, 
    making it configurable. This allows the location of the jobs file to be managed outside of the code.

"""

import ast
from types import FunctionType
from configmanager import ConfigManager
import inspect
cfg_mgr = ConfigManager(logger_name='WLEDLogger.scheduler')


class JobWrapper:
    """Wraps a function and its source code.

    Provides a callable interface while retaining access to the original function's
    metadata (docstring, annotations, etc.).
    """
    def __init__(self, func: FunctionType, source: str):
        self._func = func
        self._source = source
        self._name = func.__name__
        self._doc = func.__doc__
        self._annotations = func.__annotations__
        self._module = func.__module__
        self._signature = inspect.signature(func)

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def view(self):
        return self._source

    def doc(self):
        return self._func.__doc__ or self._source.split('\n')[0]

    @property
    def name(self):
        return self._name

    @property
    def __name__(self):
        return self._name

    @property
    def docstring(self):
        return self._doc

    @property
    def annotations(self):
        return self._annotations

    @property
    def module(self):
        return self._module

    @property
    def signature(self):
        return self._signature

    def to_dict(self):
        return {
            "name": self._name,
            "doc": self.doc(),
            "signature": str(self._signature),
            "annotations": self._annotations,
            "module": self._module,
            "source": self._source,
        }

    def __repr__(self):
        return f"<Job {self.__name__}{self._signature}>"


def load_jobs(filename, class_name="Jobs"):
    """Loads user-defined jobs from a Python file.

    Parses the file, extracts function definitions, wraps them into callable JobWrapper objects,
    and makes them accessible through a dynamically generated Jobs class.
    """
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
        if isinstance(func, FunctionType)
    }

    class Jobs:
        """Provides access to loaded jobs.

        Instances of this class allow calling loaded jobs as methods and offer utility
        functions for listing, getting help, and searching jobs.
        """
        def __init__(self):
            for name, job in wrapped_jobs.items():
                setattr(self, name, job)

        @property
        def names(self):
            return list(wrapped_jobs.keys())

        def help(self):
            j_lines = []
            j_lines.extend(f"• {name}: {job.doc()}" for name, job in wrapped_jobs.items())
            return "\n".join(j_lines)

        def search(self, query):
            return [name for name in self.names if query.lower() in name.lower()]

        def __repr__(self):
            return f"<Jobs ({len(wrapped_jobs)} jobs): {', '.join(self.names)}>"

    return Jobs

if __name__ == '__main__':
    """ usage example """
    MyJobs=load_jobs(cfg_mgr.app_root_path('xtra/jobs/jobstosched.py'))
    mjobs=MyJobs()
    print(20*'-> ' + 'List all jobs defined in jobstosched.py')
    print(mjobs.names)
    print(20*'-> ' + 'provide some help')
    print(mjobs.help())
    print(20*'-> ' + 'view source file for job1')
    print(mjobs.job1.view())
    print(20*'-> ' + 'execute job1')
    mjobs.job1(name='test from main')
