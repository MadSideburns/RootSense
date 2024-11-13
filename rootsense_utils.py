from dataclasses import dataclass
from pathlib import Path
from typing import List
import sys
import time
import subprocess

def bash_command(command: str) -> subprocess.CompletedProcess:
    '''
    Runs the `command` on the system bash

    Parameters
    ----------
    command: str
        The command you want to run

    Returns
    -------
    `subprocess.CompletedProcess` object containing the result of the command, as text with output captured
    '''
    #split command to conform to run routine syntax
    base_command = command.split()[0]
    options = command.replace(base_command + ' ', '')

    return subprocess.run([base_command, options], capture_output=True, text=True)

def is_ascii(file: str | Path) -> bool:
    '''
    Determines if a file `file` is plain text

    Parameters
    ----------
    file: str | Path
        file to test
    
    Returns
    -------
    is_ascii: bool
        `true` if file is plain text, `false` otherwhise
    '''
    if isinstance(file, Path):
        file = file.resolve()
    return 'ASCII' in bash_command(f'file {str(file)}').stdout

def timed(f: callable, *args, **kwargs) -> tuple:
    '''
    Times the execution of the function f

    Returns
    -------
    tuple: `(f(*args, **kwargs), exec_time)`
    '''
    t0 = time.time()
    result = f(*args, **kwargs)
    return result, time.time() - t0

class ProgressBar:
    '''
    Simple progress bar class
    '''
    def __init__(self, frac: float = 0., bar_length: int = 50):
        self.frac = frac
        self.bar_length = bar_length

    def update(self, frac: float = 0.):
        #if percentage does not change, (and if we're not on the first or last update) \
        #   save stdout writing time
        if abs(self.frac - frac) <= .001 and frac != 1. and frac != 0.:
            return
        
        #update frac member
        self.frac = frac

        #comopute bar
        fill_width = int(self.frac * self.bar_length)
        bar: str = '#' * fill_width + '-' * (self.bar_length - fill_width)

        #write to stdout and flush it right away
        sys.stdout.write(f'\r[{bar}] {self.frac * 100.:.2f}%')
        sys.stdout.flush()

    def initialize(self):
        #starts printing the bar
        self.update()

    def terminate(self):
        #to be called on last bar iteration to fill it all the way up and print a new line
        self.update(1.)
        print('')

@dataclass
class _RSItem:
    '''
    Rootsense tree item class
    '''
    file_name: str
    file_path: str = ''
    seen: bool = False

    #overload of ordering operators
    def __le__(self, other) -> bool:
        return self.file_name <= other.file_name
    def __lt__(self, other) -> bool:
        return self.file_name < other.file_name
    def __ge__(self, other) -> bool:
        return self.file_name >= other.file_name
    def __gt__(self, other) -> bool:
        return self.file_name > other.file_name
    def __eq__(self, other) -> bool:
        return self.file_name == other.file_name
    def __ne__(self, other) -> bool:
        return self.file_name != other.file_name
    
    @classmethod
    def to_RSItem(cls, input: str | Path):
        '''generate instance of _RSItem from str or path'''
        if isinstance(input, _RSItem):
            return input
        elif isinstance(input, str):
            return _RSItem(input)
        elif isinstance(input, Path):
            return _RSItem.from_path(input)

        raise TypeError(f'Cannot convert {type(input)} to {type(cls)}.')

    @classmethod
    def from_path(cls, path: str | Path):
        '''generate instance of _RSItem from path'''
        #cast to Path instance
        path = Path(path)
        #if path is not a file raise ValueError
        err = ValueError(f'Path {str(path)} is not a file.')
        if not path.is_file():
            raise err
        
        #return a class instance using cls constructor
        return cls(path.name, str(path.resolve()))

    def __str__(self):
        return f'Node {self.file_path}, seen state: {self.seen}'

class RSNode:
    '''
    RootSense node class
    '''

    def __init__(self):
        self._left = None
        self._right = None
        self.node = None

    def insert(self, item: Path | _RSItem) -> None:
        """
        Insert the element `item` in the tree

        Parameters
        ----------
        item: `Path` or `_RSItem` instance

        """
        #correct item type, raise error if unable to convert
        if not isinstance(item, _RSItem):
            err = ValueError(f'Cannot convert type{type(item)} to RootSense tree node.')
            if not isinstance(item, Path):
                raise err
            item = _RSItem.from_path(item)

        #base case: node is still none from initialization
        if self.node is None:
            self.node = item
            return
        
        #node is already full, but there's a duplicate: update
        if item == self.node:
            self.node = item
        #go onto children
        elif item < self.node:
            #instantiate child tree if not already present
            if self._left is None:
                self._left = RSNode()
            self._left.insert(item)
        else:
            if self._right is None:
                self._right = RSNode()
            self._right.insert(item)

    def insert_dir(self, dir: str | Path, ext: List[str] | str = ['.h', '.hh', ''], ascii_only: bool = True, progress: bool = False) -> None:
        '''
        Inserts all files in `dir` and all its subdirectories inside the tree

        Parameters
        ----------
        path: str or `Path` instance
            the path to be inserted
        ext: list of str, default=`['.h', '.hh', '']`
            the file extensions allowed, use just `['*']` to include all
        ascii_only: bool, default=`True`
            instructs to only include plain text files in case the file is extensionless
        progress: bool, default=`False`
            determines if a progressbar is printed to show generation progress
        '''

        #type check
        if not isinstance(dir, Path):
            err = ValueError(f'Input {dir} could not be converted to Path.')
            if not isinstance(dir, str):
                raise err    
            dir = Path(dir)

        #start printing progressbar if progress is enabled
        if progress:
            print(f'Generating file tree from {str(dir.resolve())}...')
            bar = ProgressBar()
            bar.initialize()

        #dump all path content, then only keep the files
        dir_content = dir.rglob('*')
        files = [file for file in dir_content if file.is_file()]

        #insert all files in tree, while checking against ext
        n = len(files)
        for i, file in enumerate(files):
            #extention check: file suffix must be contained in ext, or ext must be wildcard
            if '*' in ext or file.suffix in ext:
                #special case, file is extentionless. Check for plain text, and if not skip
                if file.suffix == '' and ascii_only and not is_ascii(file):
                    continue
                self.insert(file)
            #update progressbar
            if progress:
                bar.update(i / n)
        #at the end of the loop final update for progressbar
        if progress:
            bar.terminate()

    @classmethod
    def from_dir(cls, *directories: List[str | Path], **kwargs):
        '''
        Generates an `RSNode` object containing all files in the `directories`, \
        ordered by file name

        Parameters
        ----------
        *directories: any number of str or Path 
            the directories starting from which the tree is formed

        Keyword arguments (Same as `RSNode.insert_dir`)
        -----------------------------------------------
    
        ext: list of str, default=`['.h', '.hh', '']`
            the file extensions allowed, use just `['*']` to include all
        ascii_only: bool, default=`True`
            instructs to only include plain text files in case the file is extensionless
        progress: bool, default=`False`
            determines if a progressbar is printed to show generation progress
        
        Returns
        -------
        `RSNode` object
        '''
        #convert all to path
        directories = [Path(dir) for dir in directories]

        #generate empty tree
        tree_root = cls()
        #use `insert_dir` method for each input directory
        for dir in directories:
            tree_root.insert_dir(dir, **kwargs)

        return tree_root
    
    def __contains__(self, item: str | Path | _RSItem) -> bool:
        '''
        Returns `True` if `item` is found inside the tree, `False` otherwise

        Parameters
        ----------
        item: str | Path | _RSItem
            item to be checked. `_RSItem` is the base case for all three
        '''
        item = _RSItem.to_RSItem(item)
        
        #if self.node is None (empty tree), or item is (file does not exist), that means it's not in the treee
        if self.node is None or item is None:
            return False
        #other base case, item is found
        elif self.node == item:
            return True
        
        #check inside children
        if item < self.node and self._left is not None:
            return item in self._left
        elif item > self.node and self._right is not None:
            return item in self._right
        
        #if none of these if cases was executed, that means we reached a leaf without finding item
        return False
    
    def __getitem__(self, item: str | Path | _RSItem) -> _RSItem:
        '''
        Returns the `_RSItem` instance associated to the key `item`
        
        Parameters
        ----------
        item: str | Path | _RSItem
            item to be searched for. `_RSItem` is the base case for all three
        '''
        item = _RSItem.to_RSItem(item)

        #prepare exception to throw if item is not in the tree
        err = KeyError(f'File "{str(item.file_path)}" not present.')
        if self.node is None or item not in self:
            raise err

        #base case: item found
        if item == self.node:
            return self.node
        #don't need to check for existance of children since we know item must be in self
        elif item < self.node:
            return self._left[item]
        else:
            return self._right[item]

    def __or__(self, other):
        '''
        Returns a new tree with all elements from `self` and `other`
        '''
        if not isinstance(other, RSNode):
            raise TypeError(f'Cannot merge {type(other)} into {type(self)} object.')

        if other is None or other.node is None:
            return self    

        #start with self
        result = self

        result.insert(other.node)

        #merge with children
        if other._left is not None:
            result |= other._left
        if other._right is not None:
            result |= other._right

        return result

    @classmethod
    def merge(cls, *others: list):
        '''
        Returns a tree which is the merger of all trees in `others`
        '''

        new_tree = cls()
        #loop all over the other trees, and let the __or__ method handle errors
        for other in others:
            new_tree |= other

        return new_tree

    def printout(self) -> None:
        '''
        Prints the tree content in its ordered state
        '''
        if self.node is None:
            return

        if self._left is not None:
            self._left.printout()
        print(self.node)
        if self._right is not None:
            self._right.printout()

    def size(self) -> int:
        '''
        returns the number of elements in the tree
        '''
        if self.node is None:
            return 0

        size_l = self._left.size() if self._left is not None else 0
        size_r = self._right.size() if self._right is not None else 0
        return 1 + size_l + size_r

    def depth(self) -> int:
        '''
        Returns the depth of the tree
        '''
        if self.node is None:
            return 0
        
        depth_l = self._left.depth() if self._left is not None else 0
        depth_r = self._right.depth() if self._right is not None else 0
        return 1 + max(depth_l, depth_r)

    def get_seen_status(self, item: str | Path | _RSItem) -> bool:
        item = _RSItem.to_RSItem(item)

        #let __getitem__ figure out the eventual errors
        return self[item].seen

    def mark_as_seen(self, item: str | Path | _RSItem) -> None:
        self[item].seen = True
