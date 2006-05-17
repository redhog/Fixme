#! /usr/bin/env python
import os, os.path, re

class Fixmes(object):
    # Files and directories to exclude from searching. Notice that the
    # basepath given to load() is not in itself affected by these.
    excludeDirs = re.compile('\{arch\}|.arch-ids', re.UNICODE | re.LOCALE)
    excludeFiles = re.compile('.*(~|\.(old|bak|pyc))', re.UNICODE | re.LOCALE)
    # These are the files that are gonna be added to self.files, and
    # thus rewritten (updated) when save() is called.
    generalFiles = re.compile('.*\.bugs', re.UNICODE | re.LOCALE)

    class Fixme(object):
        class Item(object):
            def __init__(self, fields = None):
                self.fields = fields or {}
            def __sub__(self, other):
                result = self.__class__()
                for key in self.fields:
                    if key not in other.fields or self.fields[key] != other.fields[key]:
                        result.fields[key] = self.fields[key]
                return result
        def __init__(self, fields = None, items = None):
            self.fields = fields or {}
            self.items = items or {}
        def __sub__(self, other):
            result = self.__class__()
            for key in self.fields:
                if key not in other.fields or self.fields[key] != other.fields[key]:
                    result.fields[key] = self.fields[key]
            for key in self.items:
                if key not in other.items:
                    result.items[key] = self.items[key]
                else:
                    diff = self.items[key] - other.items[key]
                    if diff.fields:
                        result.items[key] = diff
            return result

    def __init__(self, path = None):
        self.root = os.path.realpath(path or '.')
        file = '.'
        if not os.path.isdir(self.root):
            self.root, file = os.path.split(self.root)
        self.rootlen = len(os.path.join(self.root, ''))
        self.fixmes = {}
        self.files = set()
        if path is not None:
            self.load(file)

    def insertFixme(self, fields):
        name = fields.get('name', "%s:%s" % fields['location'])
        if name in self.fixmes:
            fixme = self.fixmes[name]
        else:
            fixme = self.Fixme()
            fixme.id = name
            self.fixmes[name] = fixme
            if 'name' in fields:
                fixme.fields['name'] = name
        if 'general' in fields:
            general = fields['general']
            del fields['general']
            if general == True:
                fixme.fields.update(fields)
                return
            else:
                fixme.fields.update(general)
        item = self.Fixme.Item(fields)
        item.id = name
        fixme.items[fields['location']] = item
        
        
    def parseFixme(self, path, linenr, fixme, *arg, **kw):
        fixme_dict = {'__builtins__':{}, 'True':True, 'False':False, 'None':None, 'location':(path,linenr)}
        try:
            exec fixme in fixme_dict
        except Exception, e:
            print e
            return
        del fixme_dict['__builtins__']
        del fixme_dict['True']
        del fixme_dict['False']
        del fixme_dict['None']
        self.insertFixme(fixme_dict, *arg, **kw)

    def loadFile(self, path = ''):
        if self.generalFiles.search(os.path.basename(path)):
            self.files.add(path)
        if path == '-':
            file = sys.stdin
        else:
            file = open(os.path.join(self.root, path))
        fixme = None
        fixmeprefix = ''
        fixmeLinenr = 0
        linenr = 0
        for line in file:
            linenr += 1
            if '#' in line:
                line = line.split('#', 1)[1]
            line = line.strip()
            if line.startswith('FIXME: '):
                description = line.split(':', 1)[1].strip()
                self.insertFixme({'location':(path,linenr), 'type':'fixme', 'name':description, 'description':description})
                continue
            elif line.startswith('TODO: '):
                description = line.split(':', 1)[1].strip()
                self.insertFixme({'location':(path,linenr), 'type':'todo', 'name':description, 'description':description})
                continue
            elif line.startswith('WHISH: '):
                description = line.split(':', 1)[1].strip()
                self.insertFixme({'location':(path,linenr), 'type':'whish', 'name':description, 'description':description})
                continue
            elif line == "### fi" + "xme ####":
                fixme = ''
                fixmeLinenr = linenr
                continue
            elif line.startswith("### e" + "nd ####"):
                if fixme is None:
                    print "End of fixme without corresponding start in %s:%s" % (path, linenr)
                    continue
                self.parseFixme(path, fixmeLinenr, fixme)
                fixme = None
                continue
            if fixme is not None:
                if fixme == '':
                    # Remove a common indentation from all lines
                    fixmeprefix = len(line) - len(line.lstrip())
                fixme += line[fixmeprefix:] + '\n'

    def load(self, path = '.'):
        fullpath = os.path.realpath(os.path.join(self.root, path))
        if os.path.isdir(fullpath):
            for (dirpath, dirnames, filenames) in os.walk(fullpath, topdown=True):
                for index in xrange(len(dirnames) - 1, -1, -1):
                    if self.excludeDirs.search(dirnames[index]):
                        del dirnames[index]
                # Remove the root prefix
                dirpath = dirpath[self.rootlen:]
                for filename in filenames:
                    if not self.excludeFiles.search(filename):
                        self.loadFile(os.path.join(dirpath, filename))
        else:
            self.loadFile(path)

    def save(self):
        files = dict([(file, []) for file in self.files])
        for fixmeName, fixme in self.fixmes.iteritems():
            if 'location' in fixme.fields and fixme.fields['location'][0] in files:
                files[fixme.fields['location'][0]].append(fixme)
        for file, fixmes in files.iteritems():
            fh = open(file, "w")
            fixmes.sort(lambda a, b: cmp(a.id, b.id))
            for fixme in fixmes:
                fh.write("#### fi" + "xme ####\ngeneral = True\n")
                keys = fixme.fields.keys()
                keys.sort()
                for key in keys:
                    if key != 'location':
                        fh.write('%s = %s\n' % (key, repr(fixme.fields[key])))
                fh.write("#### e" + "nd ####\n")
            fh.close()

    def evalFilter(self, filter, env):
        nenv = {'__builtins__':{}, 'reduce':reduce}
        nenv.update(env)
        return eval(filter, nenv, {})

    def display(self, keyDisplayFilter = None, itemDisplayFilter = None, fixmeFilter = None, itemFilter = None, foldFiles = True, foldFirstLine = True):
        """Pretty-print fixmes to stdout as a nice tree, optionally
        filtering which fixmes, items, fixme-fields and item-fields to
        show..."""
        for fixmeName, fixme in self.fixmes.iteritems():
            if fixmeFilter and not self.evalFilter(fixmeFilter, {'fixme':fixme}):
                continue
            fields = [(key, value)
                      for key, value in fixme.fields.iteritems()
                      if key != 'name' and (keyDisplayFilter is None or key in keyDisplayFilter)]
            items = [((file, line),
                      [(key, value)
                        for key, value in item.fields.iteritems()
                        if key not in ('name', 'location') and (itemDisplayFilter is None or key in itemDisplayFilter)])
                      for (file, line), item in fixme.items.iteritems()
                      if not itemFilter or self.evalFilter(itemFilter, {'item':item})]
            if foldFiles and not fields and len(items) == 1:
                if 'name' in fixme.fields:
                    fixmeName = "%s//%s:%s" % (fixmeName, items[0][0][0], items[0][0][1])
                fields = items[0][1]
                items = []
            if foldFirstLine and len(fields) == 1:
                print "%s//%s: %s" % (fixmeName, fields[0][0], repr(fields[0][1]))
            else:
                print fixmeName
                for key, value in fields:
                    print "    %s: %s" % (key, repr(value))
            for (file, line), item in items:
                if foldFirstLine and len(item) == 1:
                    print "    %s:%s//%s: %s" % (file, line, item[0][0], repr(item[0][1]))
                else:
                    print "    %s:%s" % (file, line)
                    for key, value in item:
                        print "        %s: %s" % (key, repr(value))
            if len(fields) > 1 or items:
                print

    def __sub__(self, other):
        added = self.__class__()
        modified = self.__class__()
        deleted = self.__class__()
        for key in self.fixmes:
            if key not in other.fixmes:
                added.fixmes[key] = self.fixmes[key]
            else:
                diff = self.fixmes[key] - other.fixmes[key]
                if diff.fields or diff.items:
                    modified.fixmes[key] = diff
        for key in other.fixmes:
            if key not in self.fixmes:
                deleted.fixmes[key] = other.fixmes[key]
        return (added, modified, deleted)

if __name__ == '__main__':
    import sys

    def safe_eval(s, locals = {}):
        # unwrap quotes, safely
        return eval(s, {'__builtins__':{}}, locals)

    if len(sys.argv) < 2:
        print "Usage:"
        print """fixme list PATH [names] [KEY...] [items|items.KEY...] [filter:FIXME-FILTER] [item-filter:ITEM-FILTER]
fixme diff PATH1 PATH2 [names] [KEY...] [items|items.KEY...] [filter:FIXME-FILTER] [item-filter:ITEM-FILTER]
fixme desplay [//|NAME//|NAME//KEY|NAME////|NAME//FILE:LINE//|NAME//FILE:LINE//KEY]...
fixme modify PATH [delete:NAME//KEY|NAME//KEY=VALUE]...]
"""
        sys.exit(1)
    args = sys.argv[1:]
    cmd = args[0]
    del args[0]
    #### fixme ####
    # type='todo'
    # description='Add support for CVS and other version control systems'
    #### end ####
    if cmd == 'archdiff':
        def pread(cmd): f = os.popen(cmd); res = f.read(); f.close(); return res[:-1]
        os.chdir(args[0])
        del args[0]
        fullversion = pread('echo $(tla tree-version)--$(tla logs | tail -1)')
        repo, version = fullversion.split('/')
        cat, branch, ver, patch = version.split('--')
        os.system('tla add-pristine %s' % fullversion)
        new = pread('tla tree-root')
        old = os.path.join(new, "{arch}/++pristine-trees/unlocked/%(cat)s/%(cat)s--%(branch)s/%(cat)s--%(branch)s--%(ver)s/%(repo)s/%(cat)s--%(branch)s--%(ver)s--%(patch)s" % {
        'repo': repo, 'cat': cat, 'branch': branch, 'ver': ver, 'patch': patch
        })
        cmd = 'diff'
        args[0:0] = [old, new]
    fixmes = Fixmes(args[0])
    del args[0]
    if cmd in ('list', 'diff'):
        restargs = args[:]
        if cmd == 'diff': del restargs[0]
        fixmeFilter = itemFilter = None
        keyDisplayFilter = set()
        itemDisplayFilter = set()
        nofilter = True
        for arg in restargs:
            if arg.startswith('filter:'):
                fixmeFilter = arg.split(':', 1)[1]
            elif arg.startswith('item-filter:'):
                itemFilter = arg.split(':', 1)[1]
            elif arg == 'names':
                nofilter = False
            elif arg == 'items':
                nofilter = False
                itemDisplayFilter = None
            elif arg.startswith('items//'):
                nofilter = False
                itemDisplayFilter.add(arg.split('//',1)[1])
            else:
                nofilter = False
                keyDisplayFilter.add(arg)
        if nofilter:
            keyDisplayFilter = itemDisplayFilter = None
    if cmd in ('diff'):
        fixmes2 = Fixmes(args[0])
        (added, modified, deleted) = fixmes2 - fixmes
        args = args[1:]
        print "New fixmes:"
        added.display(keyDisplayFilter, itemDisplayFilter, fixmeFilter, itemFilter)
        print
        print "Modified fixmes:"
        modified.display(keyDisplayFilter, itemDisplayFilter, fixmeFilter, itemFilter)
        print
        print "Deleted fixmes:"
        deleted.display(keyDisplayFilter, itemDisplayFilter, fixmeFilter, itemFilter)
    elif cmd in ('list',):
        fixmes.display(keyDisplayFilter, itemDisplayFilter, fixmeFilter, itemFilter)
    elif cmd in ('display',):
        for arg in args:
            arg = arg.split('//')
            if arg[0] == '':
                print ' '.join(fixmes.fixmes.keys())
            else:
                fixme = fixmes.fixmes[arg[0]]
                if len(arg) == 3:
                    if arg[1] == '':
                        print ' '.join(["%s:%s" % item for item in fixme.items.keys()])
                    else:
                        file, line = arg[1].split(':')
                        line = int(line)
                        item = fixme.items[(file, line)]
                        if arg[2] == '':
                            print ' '.join(item.fields.keys())
                        else:
                            print item.fields[arg[2]]
                else:
                    if arg[1] == '':
                        print ' '.join(fixme.fields.keys())
                    else:
                        print fixme.fields[arg[1]]
    elif cmd == 'modify':
        for arg in args:
            if arg.startswith('delete:'):
                name = arg.split(':', 1)[1]
                if '//' in name:
                    name, key = name.split('//')
                    del fixmes.fixmes[name].fields[key]
                else:
                    fixmes.fixmes[name].fields = {}
            else:
                name, value = arg.split('=', 1)
                name, key = name.split('//')
                fixmes.fixmes[name].fields[key] = safe_eval(value)
        fixmes.save()
    else:
        print "Unknown command."
        sys.exit(1)
