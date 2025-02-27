import pkgutil

for i in pkgutil.iter_modules(None): # returns a tuple (path, package_name, ispkg_flag)
    print(i[1]) #or you can append it to a list
