from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

def is_ascii(file):
    return 'ASCII' in subprocess.run(['file', str(file)], capture_output=True, text=True).stdout

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
            return cls(path.name, str(path))

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
        key = str(key)
        key_item = _RSItem(key)
        err = KeyError(f'File {key} not found.')

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
    
    def printout(self):
        if self._left is not None:
            self._left.printout()
        print(self._item)
        if self._right is not None:
            self._right.printout()

    def insert_path(self, path, ext=['.h', '.hh', ''], ascii=True):
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
        '''
        if not isinstance(path, Path):
            path = Path(path)

        #dump all path content, irregardless of file or directory
        path_content = path.glob('*')
        files = []
        subdirs = []
        #apparently, `path.glob()` returns a generator which is \
        # iterable only once and returns `PosixPath` objects
        for elem in path_content:
            if elem.is_file():
                files.append(elem)
            elif elem.is_dir():
                subdirs.append(elem)

        #insert first all files in the tree, as long as they are headers
        for file in files:
            #extension check
            if ext == '*' or file.suffix in ext:
                #in case of no extension, check for ascii and if not skip file
                if ascii and file.suffix == '' and not is_ascii(file):
                    continue
                self.insert(file)
        #recursive call on all subfolders
        for subdir in subdirs:
            self.insert_path(subdir, ext, ascii)

    @classmethod
    def from_dir(cls, *directories):
        '''
        Generates an `RSTree` object containing all files in the `directories`, \
        ordered by file name

        Parameters
        ----------
        *directories: any number of str or Path 
            the directories starting from which the tree is formed

        Returns
        -------
        `RSTree` object
        '''
        #use this instead of directories, now they are all paths (pay attention to the case where it's single str)
        if isinstance(directories, str):
            paths = [Path(directories)]
        else:
            paths = [Path(dir) for dir in directories if not isinstance(directories, str)]
        
        #generate final tree
        dir_tree = cls()
        #use class method to insert all paths
        for path in paths:
            dir_tree.insert_path(path)

        return dir_tree

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