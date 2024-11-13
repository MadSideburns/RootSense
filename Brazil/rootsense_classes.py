from dataclasses import dataclass
from pathlib import Path
import sys
import subprocess
import time

def is_ascii(file):
    return 'ASCII' in subprocess.run(['file', str(file)], capture_output=True, text=True).stdout

class ProgressBar:
    def __init__(self, frac: float = 0.0, bar_length: int = 50):
        self.frac = frac
        self.bar_length = bar_length

    def initialize(self):
        self.update()

    def update(self, frac = None):
        #if percentage does not change, don't do anything 'cause it's a waste of print time
        if frac is not None and abs(self.frac - frac) <= .001 and frac != 1.:
            return

        #updates the progress bar and prints it in place
        if frac is not None:
            self.frac = frac
        else:
            self.frac = 0.

        fill_width = int(self.frac * self.bar_length)
        bar = '#' * fill_width + '-' * (self.bar_length - fill_width)
        
        sys.stdout.write(f'\r[{bar}] {self.frac*100.:.2f}%')
        sys.stdout.flush()

        if frac == 1.:
            print('')

    def terminate(self):
        self.update(1.)

@dataclass
class _RSItem:
    file_name: str
    file_path: str = ''
    seen: bool = False

    #overload of operation <= in order to make _RSItem an orderable class
    def __le__(self, other):
        return (self.file_name <= other.file_name)
    
    def __lt__(self, other):
        return (self.file_name < other.file_name)
    
    def __ge__(self, other):
        return (self.file_name >= other.file_name)
    
    def __gt__(self, other):
        return (self.file_name > other.file_name)

    def __eq__(self, other):
        return (self.file_name == other.file_name)

    def __ne__(self, other):
        return (self.file_name != other.file_name)

    @classmethod
    def from_path(cls, path):
        #if this path is a file, returns the instance, otherwise None
        if path.is_file():
            return cls(path.name, str(path.resolve()))

class RSTree:
    def __init__(self):
        self._item = None
        self._left = None
        self._right = None

    def insert(self, item):
        """
        Insert the element `item` in the tree

        Parameters
        ----------
        item: list[str] or `Path` or `_RSItem` instance
            if list, must be in the form `[item_name, item_path]`

        """
        #if the item to be inserted isn't already an instance of _RSItem, cast it
        if not isinstance(item, _RSItem):
            if isinstance(item, list):
                item = _RSItem(*item)
            elif isinstance(item, Path) and item.is_file():
                item = _RSItem(item.name, str(item))

        #base case - element is not initialized, just instantiate
        if self._item is None:
            self._item = item
            return

        #self._item is present: go to left child if item < self, go to right otherwhise
        #equality check to avoid duplicate keys
        if item == self._item:
            self._item = item
        elif item < self._item:
            #if left child is None, instantiate a new child RSTree
            if self._left is None:
                self._left = RSTree()
            self._left.insert(item)
        else:
            if self._right is None:
                self._right = RSTree()
            self._right.insert(item)
        
    def __getitem__(self, key):
        '''
        Returns the element associated to the file `key`
        '''
        if isinstance(key, str):
            key_item = _RSItem(key)
        elif isinstance(key, Path):
            key_item = _RSItem.from_path(key)
        else:
            key_item = key
        
        err = KeyError(f'File "{str(key)}" not found.')

        if self._item is None or key not in self:
            raise err
        
        if key_item == self._item:
            return self._item
        elif key_item <= self._item:
            return self._left[key]
        else:
            return self._right[key]

    def __contains__(self, item):
        '''
        Implements the `elem in tree` syntax. 
        
        `elem` can be:
        --------------
        str:
            in the format `file_name`
        `Path` instance:
            checks if it's a file, then unpacks it
        `_RSItem` instance:
            native tree element type, ultimately all cases are converted to this
        '''
        if not isinstance(item, _RSItem):
            if isinstance(item, str):
                item = _RSItem(item)
            elif isinstance(item, Path):
                item = _RSItem.from_path(item)

        #base case - tree item is None, item isn't in this tree
        #also applies if the item to be searched for is None, that means the path doesn't exist
        if self._item is None or item is None:
            return False
        #other base case - the item is found
        elif self._item == item:
            return True

        
        if item <= self._item:
            if self._left is None:
                return False
            return item in self._left
        else:
            if self._right is None:
                return False
            return item in self._right
    
    def __or__(self, other):
        '''
        Merge other tree into self
        '''
        if not isinstance(other, RSTree):
            raise TypeError(f'Cannot merge {type(other)} into {type(self)} object.')

        if other is None:
            return self
        
        if other._item is not None:
            self.insert(other._item)
        if other._left is not None:
            self |= other._left
        if other._right is not None:
            self |= other._right 

        return self

    def merge(self, *others):
        if not isinstance(others, list):
            self |= others
        else:
            for other in others:
                self |= other

    def printout(self):
        if self._left is not None:
            self._left.printout()
        print(self._item)
        if self._right is not None:
            self._right.printout()

    def insert_path(self, path, ext=['.h', '.hh', ''], ascii=True, progress=False):
        '''
        Inserts all files in `path` and all its subdirectories inside the tree

        Parameters
        ----------
        path: str or `Path` instance
            the path to be inserted
        ext: list of str, default=`['.h', '.hh', '']`
            the file extensions allowed, use just `'*'` to include all
        ascii: bool, default=`True`
            instructs to only include plain text files in case the file is extensionless
        progress: bool, default=`False`
            determines if a progressbar is printed to show generation progress
        '''
        if not isinstance(path, Path):
            path = Path(path)
        if progress:
            print(f'Generating file tree from {str(path)}...')
        if progress:
            bar = ProgressBar()
            bar.update()

        #dump all path content, irregardless of file or directory in all subfolders
        path_content = path.rglob('*')
        files = [file for file in path_content if file.is_file()]
        
        #insert first all files in the tree, as long as they are headers
        n = len(files)
        for i, file in enumerate(files):
            if progress:
                bar.update(i / n)
            #extension check
            if ext == '*' or file.suffix in ext:
                #in case of no extension, check for ascii and if not skip file
                if ascii and file.suffix == '' and not is_ascii(file):
                    continue
                self.insert(file)
        if progress:
            bar.update(1.)

    @classmethod
    def from_dir(cls, *directories, progress=False, ext=['.h', '.hh', '']):
        '''
        Generates an `RSTree` object containing all files in the `directories`, \
        ordered by file name

        Parameters
        ----------
        *directories: any number of str or Path 
            the directories starting from which the tree is formed
        ext: list of str, default=`['.h', '.hh', '']`
            the file extensions allowed, use just `'*'` to include all
        progress: bool, default = `False`
            determines if a progressbar is printed to show generation progress
        Returns
        -------
        `RSTree` object
        '''
        #use this instead of directories, now they are all paths (pay attention to the case where it's single str)
        if isinstance(directories, str) or isinstance(directories, Path):
            paths = [Path(directories)]
        else:
            paths = [Path(dir) for dir in directories if not isinstance(directories, str)]
        
        #generate final tree
        dir_tree = cls()
        #use class method to insert all paths
        for path in paths:
            dir_tree.insert_path(path, ext=ext,progress=progress)

        return dir_tree

    @classmethod
    def from_tree_list(cls, list):
        tree = cls()
        for item in list:
            tree |= item

        return tree

    def size(self):
        if self._item is None:
            return 0
        
        size_r = self._right.size() if self._right is not None else 0
        size_l = self._left.size() if self._left is not None else 0
        return 1 + size_r + size_l

    def depth(self):
        if self._item is None:
            return 0
        
        depth_r = self._right.depth() if self._right is not None else 0
        depth_l = self._left.depth() if self._left is not None else 0
        return 1 + max(depth_l, depth_r)
    
    def has_been_seen(self, item):
        return item in self and self[item].seen
    
    def mark_as_seen(self, item):
        self[item].seen = True