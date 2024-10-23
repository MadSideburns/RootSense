from dataclasses import dataclass
from pathlib import Path

@dataclass
class _RSItem:
    file_name: str
    file_path: str = ''
    seen: bool = False

    #overload of operation <= in order to make _RSItem an orderable class
    def __le__(self, other):
        return (self.file_name <= other.file_name)
    
    def __eq__(self, other):
        return (self.file_name == other.file_name)

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

        #self._item is present: go to left child if item <= self, go to right otherwhise
        if item <= self._item:
            #if left child is None, instantiate a new child RSTree
            if self._left is None:
                self._left = RSTree()
            self._left.insert(item)
        else:
            if self._right is None:
                self._right = RSTree()
            self._right.insert(item)
        
    def __contains__(self, item):
        if not isinstance(item, _RSItem):
            item = _RSItem(*item)

        #base case - item is None, item isn't in this tree
        if self._item is None:
            return False
        #other base case - the item is found
        elif self._item == item:
            return True

        
        if item <= self._item:
            return item in self._left
        else:
            return item in self._right
    
    def printout(self):
        if self._left is not None:
            self._left.printout()
        print(self._item)
        if self._right is not None:
            self._right.printout()

    def insert_path(self, path):
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
            if file.suffix in ['.h', '.hh', '']:
                self.insert(file)
        #recursive call on all subfolders
        for subdir in subdirs:
            self.insert_path(subdir)
        

        

    @staticmethod
    def from_root_dir(*directories):
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
        dir_tree = RSTree()
        #use class method to insert all paths
        for path in paths:
            dir_tree.insert_path(path)

        return dir_tree

