import os

from robot.utils import is_string


class ListenImports(object):
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, imports):
        self.imports = open(imports, 'w')

    def library_import(self, name, attrs):
        self._imported("Library", name, attrs)

    def resource_import(self, name, attrs):
        self._imported("Resource", name, attrs)

    def variables_import(self, name, attrs):
        self._imported("Variables", name, attrs)

    def _imported(self, import_type, name, attrs):
        self.imports.write("Imported %s\n\tname: %s\n" % (import_type, name))
        for name in sorted(attrs):
            self.imports.write("\t%s: %s\n" % (name, self._pretty(attrs[name])))

    def _pretty(self, entry):
        if isinstance(entry, list):
            return '[%s]' % ', '.join(entry)
        if is_string(entry) and os.path.isabs(entry):
            entry = entry.replace('$py.class', '.py').replace('.pyc', '.py')
            tokens = entry.split(os.sep)
            index = -1 if tokens[-1] != '__init__.py' else -2
            return '//' + '/'.join(tokens[index:])
        return entry

    def close(self):
        self.imports.close()
