import importlib
import os
import pkgutil
import sys


def yield_one(path):
    try:
        spec = importlib.util.find_spec(path)
    except ModuleNotFoundError:
        yield None
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[path] = module
        spec.loader.exec_module(module)
        yield module
    except AttributeError:
        yield None


def load_one(path):
    return list(yield_one(path))[0]


def load_from_dir(directory):
    if not os.path.isdir(directory):
        return
    for moduleinfo in pkgutil.iter_modules([directory]):
        if moduleinfo.name.startswith("_"):
            continue
        try:
            spec = moduleinfo.module_finder.find_spec(moduleinfo.name)
            if spec is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[moduleinfo.name] = module
            spec.loader.exec_module(module)
            yield module
        except Exception:
            continue


def load_many(path):
    parts = path.split(".")
    this_path = os.path.realpath(os.path.dirname(__file__))
    # Remove the first part ("plugins") since we're already in the plugins directory
    search_path = os.path.join(this_path, *parts[1:])
    for moduleinfo in pkgutil.iter_modules([search_path]):
        # Skip modules starting with underscore
        if moduleinfo.name.startswith("_"):
            continue
        spec = moduleinfo.module_finder.find_spec(moduleinfo.name)
        module = importlib.util.module_from_spec(spec)
        sys.modules[moduleinfo.name] = module
        spec.loader.exec_module(module)
        yield module
