from loguru import logger
from pathlib import Path
from typing import List
from rootsense_utils import RSNode, ProgressBar, bash_command, timed, andl
import time
import subprocess

def get_includes(file: Path) -> List[str]:
    with open(file) as f:
        file_lines = f.readlines()

    includes = []

    for line in file_lines:
        #strip line from leading and trailing whitespaces
        line = line.strip()
        #determine if it's an include statement and skip if not
        if not (line.startswith('#include') and ('<' in line or '\"' in line)):
            continue
        # #include <...> case (too problematic to check)
        """ if '<' in line and '>' in line:
            included_file = line.split('<', 1)[1].split('>', 1)[0].strip() """
        # #include "..." case
        if '\"' in line:
            included_file = line.split('\"', 2)[1].strip()
            #sometimes i've found some comments that get picked up by this code. Check for whitespaces to fix
            if ' ' in included_file:
                continue

            includes.append(included_file)

    return includes

def main():
    #some system paths where to locate included files
    """ sys_include_paths = ['/usr/include', '/usr/local/include', '/usr/lib', '/lib/modules'] """
    """ sys_include_paths = ['/usr/modules', '/usr/include'] """
    sys_include_paths = []
    sys_include_paths = [Path(p) for p in sys_include_paths]

    logger.info('Gathering root install path...')
    #this generates something like '/home/{user}/root/bin/root'
    root_exec_path_result = bash_command('which root')
    if root_exec_path_result.returncode != 0:
        raise OSError('Root installation not found. Make sure root is installed and set in your PATH variable.')

    root_exec_path = Path(root_exec_path_result.stdout)
    #this will be the root base folder '/home/{user}/root'
    root_base_path = root_exec_path.parents[1]
    root_include_path = root_base_path / 'include'
    logger.info(f'Found root include path {root_include_path}')

    #generate root tree
    logger.info(f'Generating file trees. This may take a while...')
    root_tree, root_time = timed(RSNode.from_dir, root_include_path, progress=True)
    logger.success(f'root tree created in {root_time:.4f} seconds: {root_tree.size()} elements with depth {root_tree.depth()}')
    
    #generate system tree
    sys_tree, sys_time = timed(RSNode.from_dir, *sys_include_paths, progress=True)
    logger.success(f'sys tree created in {sys_time:.4f} seconds: {sys_tree.size()} elements with depth {sys_tree.depth()}')

    rootsense_lines, include_path_set = generate_rootsense(root_include_path, [root_tree, sys_tree])
    write_rootsense(rootsense_lines, root_include_path)
    print(f'Paths to setup:')
    print(include_path_set)
    
def generate_rootsense(include_path: Path, trees: List[RSNode]) -> List[str]:
    #this tree is the merger of all the others
    global_tree = RSNode.merge(*trees)

    #find all header files in root's include path
    include_files = include_path.rglob('*')
    include_files = [file for file in include_files if file.is_file() and file.suffix in ['.h', '.hh']]
    
    #this list will contain all files to be included in rootsense.h
    files_to_be_written = []
    #this set will contain all paths which will need to be added to VScode's include paths
    VS_includes = set()

    #test code
    """ print(dependency_ok(include_files[234], global_tree, VS_includes))
    print(f'List of paths in include_path: {str(VS_includes)}') """
    #ACTUAL GENERATION
    bar = ProgressBar()
    n = len(include_files)
    logger.info(f'Parsing {n} header files found in {include_path}...')
    bar.initialize()
    for i, file in enumerate(include_files):
        bar.update(i/n)
        if global_tree.has_been_seen(file):
            continue
        if dependency_ok(file, global_tree, VS_includes):
            files_to_be_written.append(str(file))
    bar.terminate()

    logger.success(f'{len(files_to_be_written)} files will be written in rootsense.h')
    return files_to_be_written, VS_includes

def dependency_ok(file: Path, tree: RSNode, VS_includes: set) -> bool:
    #base negative case: file is not in the trees
    if file not in tree:
        return False
    
    #check if already seen. If that's the case, we already know if we can include it
    if tree.has_been_seen(file):
        #if has been seen but the `ok_to_include` attribute is not present, that means it's a circular include
        try:
            ok_to_include = tree.is_ok_to_include(file)
            return ok_to_include
        #catch the AttributeError, and in that case return True to close the loop
        except AttributeError:
            return True

    #first, mark this file as seen regardless of what will happen later
    tree.mark_as_seen(file)

    file_path = tree.get_item_path(file)
    #gather file parent directory, will be used later
    file_parent_directory = file_path.parent

    #build a list of included files
    included_files = get_includes(file_path)
    #get just the names in the case of a #include "dir/file" case
    included_files_names = [inc_file.split(sep='/')[-1] for inc_file in included_files]

    #along with this list, keep track of the directories from which all the files are included
    include_parent_directories = set()
    for inc_file, inc_file_name in zip(included_files, included_files_names):
        #beware that we haven't checked if all these included files are in the tree
        if inc_file_name not in tree:
            continue
        #if file_parent_directory/included_file != tree.get_item_path(included_file_name) that means this path isn't reachable by simple inclusion
        if Path(file_parent_directory) / inc_file != tree.get_item_path(inc_file_name):
        
            include_parent_directories.add(Path(tree.get_item_path(inc_file_name)).parent)

    ok_to_include = andl([dependency_ok(inc_file, tree, include_parent_directories) for inc_file in included_files_names])
    tree.set_ok_to_include(file, status=ok_to_include)

    #only if this file is ok to include, update the path dictionary with all the paths
    if ok_to_include:
        VS_includes |= include_parent_directories

    return ok_to_include

def write_rootsense(lines: List[str], base_directory: Path) -> None:
    with open(base_directory / 'RootSense.h', 'w') as f:
        f.write(f'#ifndef ROOTSENSE\n')
        f.write(f'#define ROOTSENSE\n\n')
        for line in lines:
            f.write(f'#include "{line}"\n')
        f.write(f'\n#endif\n')
        


if __name__ == '__main__':
    main()